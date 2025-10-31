"""
from typing import Optional
AI service for generating content using various providers
"""

import logging
import time
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AIProviderError, NotFoundError
from app.models.document import Document, DocumentOutline, DocumentSection

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI content generation"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_outline(
        self,
        document_id: int,
        user_id: int,
        additional_requirements: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate document outline using AI"""
        try:
            # Get document
            result = await self.db.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.user_id == user_id
                )
            )
            document = result.scalar_one_or_none()

            if not document:
                raise NotFoundError("Document not found")

            # Generate outline using AI
            start_time = time.time()
            outline_data = await self._call_ai_provider(
                provider=document.ai_provider,
                model=document.ai_model,
                prompt=self._build_outline_prompt(document, additional_requirements)
            )

            generation_time = int(time.time() - start_time)

            # Save outline
            outline = DocumentOutline(
                document_id=document_id,
                outline_data=outline_data,
                total_sections=len(outline_data.get('sections', [])),
                ai_provider=document.ai_provider,
                ai_model=document.ai_model,
                tokens_used=outline_data.get('tokens_used', 0),
                generation_time_seconds=generation_time
            )

            self.db.add(outline)

            # Update document status
            await self.db.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(
                    outline=outline_data,
                    status='outline_generated',
                    tokens_used=Document.tokens_used + outline_data.get('tokens_used', 0),
                    generation_time_seconds=Document.generation_time_seconds + generation_time
                )
            )

            await self.db.commit()

            return {
                "document_id": document_id,
                "outline": outline_data,
                "status": "completed",
                "tokens_used": outline_data.get('tokens_used', 0),
                "generation_time_seconds": generation_time
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error generating outline: {e}")
            raise AIProviderError(f"Failed to generate outline: {str(e)}") from e

    async def generate_section(
        self,
        document_id: int,
        section_title: str,
        section_index: int,
        user_id: int,
        additional_requirements: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a specific section using AI"""
        try:
            # Get document
            result = await self.db.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.user_id == user_id
                )
            )
            document = result.scalar_one_or_none()

            if not document:
                raise NotFoundError("Document not found")

            # Generate section content using AI
            start_time = time.time()
            section_content = await self._call_ai_provider(
                provider=document.ai_provider,
                model=document.ai_model,
                prompt=self._build_section_prompt(
                    document, section_title, section_index, additional_requirements
                )
            )

            generation_time = int(time.time() - start_time)

            # Save or update section
            result = await self.db.execute(
                select(DocumentSection).where(
                    DocumentSection.document_id == document_id,
                    DocumentSection.section_index == section_index
                )
            )
            section = result.scalar_one_or_none()

            if section:
                section.content = section_content.get('content', '')
                section.status = 'completed'
                section.tokens_used = section_content.get('tokens_used', 0)
                section.generation_time_seconds = generation_time
                section.completed_at = time.time()
            else:
                section = DocumentSection(
                    document_id=document_id,
                    title=section_title,
                    section_index=section_index,
                    content=section_content.get('content', ''),
                    status='completed',
                    tokens_used=section_content.get('tokens_used', 0),
                    generation_time_seconds=generation_time,
                    completed_at=time.time()
                )
                self.db.add(section)

            # Update document tokens and time
            await self.db.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(
                    tokens_used=Document.tokens_used + section_content.get('tokens_used', 0),
                    generation_time_seconds=Document.generation_time_seconds + generation_time
                )
            )

            await self.db.commit()

            return {
                "document_id": document_id,
                "section_title": section_title,
                "section_index": section_index,
                "content": section_content.get('content', ''),
                "status": "completed",
                "tokens_used": section_content.get('tokens_used', 0),
                "generation_time_seconds": generation_time
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error generating section: {e}")
            raise AIProviderError(f"Failed to generate section: {str(e)}") from e

    async def get_user_usage(self, user_id: int) -> Dict[str, Any]:
        """Get AI usage statistics for a user"""
        try:
            # Get total documents and tokens used
            result = await self.db.execute(
                select(
                    Document.total_documents_created,
                    Document.total_tokens_used
                ).where(Document.user_id == user_id)
            )
            stats = result.first()

            return {
                "user_id": user_id,
                "total_documents": stats.total_documents_created if stats else 0,
                "total_tokens_used": stats.total_tokens_used if stats else 0,
                "last_updated": time.time()
            }

        except Exception as e:
            logger.error(f"Error getting user usage: {e}")
            raise AIProviderError(f"Failed to get usage statistics: {str(e)}") from e

    async def _call_ai_provider(
        self,
        provider: str,
        model: str,
        prompt: str
    ) -> Dict[str, Any]:
        """Call the appropriate AI provider"""
        if provider == "openai":
            return await self._call_openai(model, prompt)
        elif provider == "anthropic":
            return await self._call_anthropic(model, prompt)
        else:
            raise AIProviderError(f"Unsupported AI provider: {provider}")

    async def _call_openai(self, model: str, prompt: str) -> Dict[str, Any]:
        """Call OpenAI API"""
        try:
            import openai

            if not settings.OPENAI_API_KEY:
                raise AIProviderError("OpenAI API key not configured")

            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert academic writer specializing in thesis and research paper generation."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000,
                temperature=0.7
            )

            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0

            return {
                "content": content,
                "tokens_used": tokens_used
            }

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise AIProviderError(f"OpenAI API error: {str(e)}") from e

    async def _call_anthropic(self, model: str, prompt: str) -> Dict[str, Any]:
        """Call Anthropic API"""
        try:
            import anthropic

            if not settings.ANTHROPIC_API_KEY:
                raise AIProviderError("Anthropic API key not configured")

            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

            response = await client.messages.create(
                model=model,
                max_tokens=4000,
                temperature=0.7,
                system="You are an expert academic writer specializing in thesis and research paper generation.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            return {
                "content": content,
                "tokens_used": tokens_used
            }

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise AIProviderError(f"Anthropic API error: {str(e)}") from e

    def _build_outline_prompt(
        self,
        document: Document,
        additional_requirements: Optional[str] = None
    ) -> str:
        """Build prompt for outline generation"""
        prompt = f"""
Generate a detailed academic thesis outline for the following topic:

Topic: {document.topic}
Language: {document.language}
Target Pages: {document.target_pages}

Please provide a structured outline with:
1. Introduction
2. Literature Review
3. Methodology
4. Results/Analysis
5. Discussion
6. Conclusion
7. References

For each section, include:
- Main points to cover
- Sub-sections
- Estimated word count
- Key concepts to address

Additional Requirements: {additional_requirements or 'None specified'}

Please respond with a JSON structure containing the outline data.
"""
        return prompt.strip()

    def _build_section_prompt(
        self,
        document: Document,
        section_title: str,
        section_index: int,
        additional_requirements: Optional[str] = None
    ) -> str:
        """Build prompt for section generation"""
        prompt = f"""
Write a comprehensive academic section for a thesis with the following details:

Document Topic: {document.topic}
Section Title: {section_title}
Section Index: {section_index}
Language: {document.language}
Target Pages: {document.target_pages}

Please write this section with:
- Academic tone and style
- Proper structure and flow
- Evidence-based arguments
- Appropriate citations (use [Author, Year] format)
- Clear transitions between paragraphs
- Professional language suitable for academic publication

Additional Requirements: {additional_requirements or 'None specified'}

Please provide only the section content without any meta-commentary.
"""
        return prompt.strip()
