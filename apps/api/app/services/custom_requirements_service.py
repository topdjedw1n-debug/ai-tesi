"""
Custom requirements file upload and processing service
Handles PDF, DOCX, and TXT file uploads for additional document requirements
"""
import io
import logging
from pathlib import Path

from docx import Document as DocxDocument
from fastapi import UploadFile
from pypdf import PdfReader

from app.core.exceptions import ValidationError
from app.services.file_validator import FileValidator

logger = logging.getLogger(__name__)

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class CustomRequirementsService:
    """Service for handling custom requirements file uploads"""

    @staticmethod
    async def validate_file(file: UploadFile) -> None:
        """
        Validate uploaded file
        Raises ValidationError if file is invalid
        """
        # Check file size
        if file.size and file.size > MAX_FILE_SIZE:
            raise ValidationError(
                f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / 1024 / 1024} MB"
            )

        # Check content type
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise ValidationError(
                f"Unsupported file type: {file.content_type}. "
                f"Allowed types: {', '.join(ALLOWED_MIME_TYPES.keys())}"
            )

        # Verify extension matches content type
        if file.filename:
            ext = Path(file.filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise ValidationError(
                    f"Unsupported file extension: {ext}. Allowed extensions: {', '.join(ALLOWED_EXTENSIONS)}"
                )
            if ext != ALLOWED_MIME_TYPES[file.content_type]:
                raise ValidationError("File extension does not match content type")

        # Validate file content with magic bytes check
        await FileValidator.validate_file_content(file, file.content_type)

        # Check for ZIP bomb attacks
        await FileValidator.check_zip_bomb(file)

    @staticmethod
    async def extract_text_from_pdf(file: UploadFile) -> str:
        """
        Extract text from PDF file
        Returns extracted text content
        """
        try:
            content = await file.read()
            file.file.seek(0)  # Reset file pointer

            pdf = PdfReader(io.BytesIO(content))
            text_parts = []

            for page in pdf.pages:
                text_parts.append(page.extract_text())

            extracted_text = "\n\n".join(text_parts)
            if not extracted_text or not extracted_text.strip():
                raise ValidationError(
                    "PDF file appears to be empty or contains no extractable text"
                )

            return extracted_text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}", exc_info=True)
            raise ValidationError(f"Failed to extract text from PDF: {str(e)}") from e

    @staticmethod
    async def extract_text_from_docx(file: UploadFile) -> str:
        """
        Extract text from DOCX file
        Returns extracted text content
        """
        try:
            content = await file.read()
            file.file.seek(0)  # Reset file pointer

            doc = DocxDocument(io.BytesIO(content))
            text_parts = []

            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)

            extracted_text = "\n\n".join(text_parts)
            if not extracted_text or not extracted_text.strip():
                raise ValidationError(
                    "DOCX file appears to be empty or contains no extractable text"
                )

            return extracted_text
        except Exception as e:
            logger.error(f"Error extracting text from DOCX: {e}", exc_info=True)
            raise ValidationError(f"Failed to extract text from DOCX: {str(e)}") from e

    @staticmethod
    async def extract_text_from_txt(file: UploadFile) -> str:
        """
        Extract text from TXT file
        Returns extracted text content
        """
        try:
            content = await file.read()
            file.file.seek(0)  # Reset file pointer

            # Try UTF-8 first, fallback to latin-1
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = content.decode("latin-1")

            if not text or not text.strip():
                raise ValidationError("TXT file appears to be empty")

            return text
        except Exception as e:
            logger.error(f"Error extracting text from TXT: {e}", exc_info=True)
            raise ValidationError(f"Failed to extract text from TXT: {str(e)}") from e

    @staticmethod
    async def extract_text(file: UploadFile) -> str:
        """
        Extract text from uploaded file based on its type
        Returns extracted text content
        """
        # Validate first
        await CustomRequirementsService.validate_file(file)

        # Extract based on file type
        content_type = file.content_type
        if content_type == "application/pdf":
            return await CustomRequirementsService.extract_text_from_pdf(file)
        elif (
            content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            return await CustomRequirementsService.extract_text_from_docx(file)
        elif content_type == "text/plain":
            return await CustomRequirementsService.extract_text_from_txt(file)
        else:
            raise ValidationError(f"Unsupported file type: {content_type}")
