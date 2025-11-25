"""
Background jobs service for async document generation
Uses FastAPI BackgroundTasks for async processing
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from sqlalchemy import select, update

from app.core import database
from app.core.exceptions import NotFoundError
from app.models.document import AIGenerationJob, Document, DocumentSection
from app.services.ai_pipeline.citation_formatter import CitationStyle
from app.services.ai_pipeline.generator import SectionGenerator
from app.services.ai_pipeline.humanizer import Humanizer
from app.services.ai_service import AIService
from app.services.document_service import DocumentService
from app.services.websocket_manager import manager

logger = logging.getLogger(__name__)

# Type variable for background task functions
F = TypeVar("F", bound=Callable[..., Any])


def background_task_error_handler(task_name: str):
    """
    Decorator for background tasks to provide consistent error handling

    Wraps background tasks with:
    - Exception catching and logging
    - Error tracking
    - Graceful failure handling

    Args:
        task_name: Name of the task for logging purposes
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                logger.info(f"Starting background task: {task_name}")
                result = await func(*args, **kwargs)
                logger.info(f"Background task completed: {task_name}")
                return result
            except Exception as e:
                logger.error(
                    f"Background task failed: {task_name}",
                    exc_info=True,
                    extra={
                        "task_name": task_name,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "args": str(args)[:200],  # Limit log size
                        "kwargs_keys": list(kwargs.keys()),
                    },
                )
                # Re-raise to allow upstream handlers to process
                raise

        return wrapper  # type: ignore

    return decorator


class BackgroundJobService:
    """Service for background document generation tasks"""

    @staticmethod
    @background_task_error_handler("generate_full_document")
    async def generate_full_document(
        document_id: int, user_id: int, additional_requirements: str | None = None
    ) -> None:
        """
        Background task to generate a complete document

        This function:
        1. Generates document outline
        2. Generates all sections sequentially
        3. Humanizes all content (mandatory)
        4. Exports to DOCX
        5. Updates document status

        Args:
            document_id: ID of the document to generate
            user_id: ID of the user owning the document
            additional_requirements: Optional additional requirements
        """
        async with database.AsyncSessionLocal() as db:
            try:
                logger.info(
                    f"Starting full document generation for document {document_id}"
                )

                # Get document
                result = await db.execute(
                    select(Document).where(
                        Document.id == document_id, Document.user_id == user_id
                    )
                )
                document = result.scalar_one_or_none()

                if not document:
                    logger.error(f"Document {document_id} not found for user {user_id}")
                    return

                # Update status to generating
                await db.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(status="generating")
                )
                await db.commit()

                # Step 1: Generate outline if not exists
                if not document.outline:
                    logger.info(f"Generating outline for document {document_id}")
                    ai_service = AIService(db)
                    try:
                        await ai_service.generate_outline(
                            document_id=document_id,
                            user_id=user_id,
                            additional_requirements=additional_requirements,
                        )
                        logger.info(
                            f"Outline generated successfully for document {document_id}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to generate outline: {e}")
                        await db.execute(
                            update(Document)
                            .where(Document.id == document_id)
                            .values(status="failed")
                        )
                        await db.commit()
                        return

                # Reload document to get outline
                await db.refresh(document)

                if not document.outline or "sections" not in document.outline:
                    logger.error(
                        f"No outline sections found for document {document_id}"
                    )
                    await db.execute(
                        update(Document)
                        .where(Document.id == document_id)
                        .values(status="failed")
                    )
                    await db.commit()
                    return

                # Step 2: Generate all sections
                sections = document.outline.get("sections", [])
                section_generator = SectionGenerator()
                humanizer = Humanizer()

                logger.info(
                    f"Generating {len(sections)} sections for document {document_id}"
                )

                for idx, section_data in enumerate(sections):
                    section_title = section_data.get("title", f"Section {idx + 1}")
                    section_index = idx + 1

                    try:
                        # Update section status to generating
                        await db.execute(
                            update(DocumentSection)
                            .where(
                                DocumentSection.document_id == document_id,
                                DocumentSection.section_index == section_index,
                            )
                            .values(status="generating")
                        )
                        await db.commit()

                        # Get previously generated sections for context
                        context_result = await db.execute(
                            select(DocumentSection)
                            .where(
                                DocumentSection.document_id == document_id,
                                DocumentSection.section_index < section_index,
                                DocumentSection.status == "completed",
                            )
                            .order_by(DocumentSection.section_index)
                        )
                        context_sections = context_result.scalars().all()
                        context_list = (
                            [
                                {"title": s.title, "content": s.content}
                                for s in context_sections
                            ]
                            if context_sections
                            else None
                        )

                        logger.info(
                            f"Generating section {section_index}: {section_title}"
                        )

                        # Generate section with RAG
                        section_result = await section_generator.generate_section(
                            document=document,
                            section_title=section_title,
                            section_index=section_index,
                            provider=document.ai_provider,
                            model=document.ai_model,
                            citation_style=CitationStyle.APA,  # Default to APA
                            humanize=False,  # Will humanize in next step
                            context_sections=context_list,
                            additional_requirements=additional_requirements,
                        )

                        # Step 3: Humanize content (mandatory)
                        logger.info(
                            f"Humanizing section {section_index}: {section_title}"
                        )
                        humanized_content = await humanizer.humanize(
                            text=section_result.get("content", ""),
                            provider=document.ai_provider,
                            model=document.ai_model,
                            preserve_citations=True,
                        )

                        # Save or update section
                        section_result_db = await db.execute(
                            select(DocumentSection).where(
                                DocumentSection.document_id == document_id,
                                DocumentSection.section_index == section_index,
                            )
                        )
                        section = section_result_db.scalar_one_or_none()

                        word_count = len(humanized_content.split())

                        if section:
                            section.content = humanized_content
                            section.status = "completed"
                            section.word_count = word_count
                            section.completed_at = datetime.utcnow()
                        else:
                            section = DocumentSection(
                                document_id=document_id,
                                title=section_title,
                                section_index=section_index,
                                content=humanized_content,
                                status="completed",
                                word_count=word_count,
                                completed_at=datetime.utcnow(),
                            )
                            db.add(section)

                        await db.commit()
                        logger.info(f"Section {section_index} completed and humanized")

                    except Exception as e:
                        logger.error(f"Error generating section {section_index}: {e}")
                        await db.execute(
                            update(DocumentSection)
                            .where(
                                DocumentSection.document_id == document_id,
                                DocumentSection.section_index == section_index,
                            )
                            .values(status="failed")
                        )
                        await db.commit()
                        # Continue with next section instead of failing completely
                        continue

                # Step 4: Check if all sections completed
                sections_result = await db.execute(
                    select(DocumentSection).where(
                        DocumentSection.document_id == document_id,
                        DocumentSection.status == "completed",
                    )
                )
                completed_sections = sections_result.scalars().all()

                if len(completed_sections) == 0:
                    logger.error(f"No sections completed for document {document_id}")
                    await db.execute(
                        update(Document)
                        .where(Document.id == document_id)
                        .values(status="failed")
                    )
                    await db.commit()
                    return

                # Step 5: Export to DOCX
                logger.info(f"Exporting document {document_id} to DOCX")
                try:
                    document_service = DocumentService(db)
                    export_result = await document_service.export_document(
                        document_id=document_id, format="docx", user_id=user_id
                    )
                    logger.info(
                        f"Document {document_id} exported successfully: {export_result.get('download_url')}"
                    )
                except Exception as e:
                    logger.error(f"Failed to export document {document_id}: {e}")
                    # Export failure doesn't fail the entire job, but log it

                # Step 6: Update document status to completed
                await db.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(status="completed", completed_at=datetime.utcnow())
                )
                await db.commit()

                logger.info(f"Document {document_id} generation completed successfully")

                # Step 7: Send email notification to user
                try:
                    from app.models.auth import User
                    from app.services.notification_service import notification_service

                    user_result = await db.execute(
                        select(User).where(User.id == user_id)
                    )
                    user = user_result.scalar_one_or_none()

                    if user and user.email:
                        await notification_service.send_document_ready_notification(
                            email=user.email,
                            document_title=document.title,
                            document_id=document_id,
                        )
                except Exception as e:
                    logger.warning(f"Failed to send completion email: {e}")

            except Exception as e:
                logger.error(
                    f"Critical error in background document generation: {e}",
                    exc_info=True,
                )
                error_message = str(e)

                # Mark document as failed
                try:
                    await db.execute(
                        update(Document)
                        .where(Document.id == document_id)
                        .values(status="failed")
                    )
                    await db.commit()

                    # Send failure notification email
                    try:
                        from app.models.auth import User
                        from app.services.notification_service import (
                            notification_service,
                        )

                        user_result = await db.execute(
                            select(User).where(User.id == user_id)
                        )
                        user = user_result.scalar_one_or_none()

                        if user and user.email:
                            await (
                                notification_service.send_document_failed_notification(
                                    email=user.email,
                                    document_title=document.title
                                    if document
                                    else "Unknown",
                                    error_message=error_message[:200],  # Limit length
                                )
                            )
                    except Exception as email_error:
                        logger.warning(f"Failed to send failure email: {email_error}")
                except Exception:
                    logger.error(
                        f"Failed to update document {document_id} status to failed"
                    )

    @staticmethod
    @background_task_error_handler("generate_full_document_async")
    async def generate_full_document_async(
        document_id: int,
        user_id: int,
        job_id: int,
        additional_requirements: str | None = None,
    ) -> None:
        """
        Async version of generate_full_document with job progress tracking.

        Updates AIGenerationJob status and progress throughout generation.

        Args:
            document_id: ID of the document to generate
            user_id: ID of the user owning the document
            job_id: ID of the AIGenerationJob for tracking
            additional_requirements: Optional additional requirements
        """
        async with database.AsyncSessionLocal() as db:
            try:
                # Update job to running
                await db.execute(
                    update(AIGenerationJob)
                    .where(AIGenerationJob.id == job_id)
                    .values(status="running", progress=0)
                )
                await db.commit()

                # Notify WebSocket clients
                await manager.send_progress(
                    user_id,
                    {
                        "type": "job_started",
                        "job_id": job_id,
                        "document_id": document_id,
                        "status": "running",
                        "progress": 0,
                    },
                )

                # Call the original generation method
                await BackgroundJobService.generate_full_document(
                    document_id=document_id,
                    user_id=user_id,
                    additional_requirements=additional_requirements,
                )

                # Update job to completed
                await db.execute(
                    update(AIGenerationJob)
                    .where(AIGenerationJob.id == job_id)
                    .values(
                        status="completed", progress=100, completed_at=datetime.utcnow()
                    )
                )
                await db.commit()

                # Notify WebSocket clients
                await manager.send_progress(
                    user_id,
                    {
                        "type": "job_completed",
                        "job_id": job_id,
                        "document_id": document_id,
                        "status": "completed",
                        "progress": 100,
                    },
                )

                logger.info(f"Job {job_id} completed successfully")

            except Exception as e:
                # Update job to failed
                try:
                    await db.execute(
                        update(AIGenerationJob)
                        .where(AIGenerationJob.id == job_id)
                        .values(
                            status="failed",
                            error_message=str(e)[:500],  # Limit error message length
                            success=False,
                            completed_at=datetime.utcnow(),
                        )
                    )
                    await db.commit()

                    # Notify WebSocket clients
                    await manager.send_progress(
                        user_id,
                        {
                            "type": "job_failed",
                            "job_id": job_id,
                            "document_id": document_id,
                            "status": "failed",
                            "error": str(e)[:200],
                        },
                    )
                except Exception:
                    logger.error(f"Failed to update job {job_id} status to failed")
                raise  # Re-raise to maintain error logging

    @staticmethod
    @background_task_error_handler("process_custom_requirement")
    async def process_custom_requirement(
        document_id: int, file_path: str, user_id: int
    ) -> dict[str, Any]:
        """
        Background task to process uploaded custom requirement file

        Extracts text from PDF or DOCX files and stores it for document generation

        Args:
            document_id: ID of the document
            file_path: Path to uploaded file
            user_id: ID of the user

        Returns:
            Dictionary with extracted text and metadata
        """
        async with database.AsyncSessionLocal() as db:
            try:
                logger.info(
                    f"Processing custom requirement for document {document_id}: {file_path}"
                )

                # Verify document ownership
                result = await db.execute(
                    select(Document).where(
                        Document.id == document_id, Document.user_id == user_id
                    )
                )
                document = result.scalar_one_or_none()

                if not document:
                    raise NotFoundError("Document not found")

                # Extract text based on file extension
                extracted_text = ""

                if file_path.endswith(".pdf"):
                    extracted_text = await BackgroundJobService._extract_pdf_text(
                        file_path
                    )
                elif file_path.endswith((".doc", ".docx")):
                    extracted_text = await BackgroundJobService._extract_docx_text(
                        file_path
                    )
                else:
                    raise ValueError(f"Unsupported file format: {file_path}")

                # Store extracted text (can be stored in document metadata or separate table)
                # For now, we'll log it and return it
                logger.info(
                    f"Extracted {len(extracted_text)} characters from {file_path}"
                )

                return {
                    "document_id": document_id,
                    "file_path": file_path,
                    "extracted_text": extracted_text,
                    "text_length": len(extracted_text),
                    "processed_at": datetime.utcnow().isoformat(),
                }

            except Exception as e:
                logger.error(f"Error processing custom requirement: {e}")
                raise

    @staticmethod
    async def _extract_pdf_text(file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            import PyPDF2

            text = ""
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"

            return text.strip()

        except ImportError as e:
            logger.error("PyPDF2 not installed. Install it with: pip install PyPDF2")
            raise ValueError(
                "PDF extraction not available: PyPDF2 not installed"
            ) from e
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            raise ValueError(f"Failed to extract text from PDF: {str(e)}") from e

    @staticmethod
    async def _extract_docx_text(file_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            from docx import Document as DocxDocument

            doc = DocxDocument(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])

            return text.strip()

        except ImportError as e:
            logger.error(
                "python-docx not installed. Install it with: pip install python-docx"
            )
            raise ValueError(
                "DOCX extraction not available: python-docx not installed"
            ) from e
        except Exception as e:
            logger.error(f"Error extracting DOCX text: {e}")
            raise ValueError(f"Failed to extract text from DOCX: {str(e)}") from e
