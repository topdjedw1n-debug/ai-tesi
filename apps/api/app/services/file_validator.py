"""
File validator for magic bytes and security checks
"""
import io
import logging
import zipfile

from fastapi import UploadFile

from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Magic bytes for valid file types
PDF_MAGIC = b"%PDF"
DOCX_MAGIC = b"PK\x03\x04"  # ZIP signature used by DOCX
TXT_MAGIC = [b"\xef\xbb\xbf", b""]  # UTF-8 BOM or empty

# File type to magic bytes mapping
FILE_MAGIC_BYTES = {
    "application/pdf": PDF_MAGIC,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DOCX_MAGIC,
    "text/plain": TXT_MAGIC,
}

# Forbidden signatures (potential security risks)
FORBIDDEN_SIGNATURES = [
    b"MZ",  # Windows EXE
    b"\x7fELF",  # Linux executable
    b"#!/",  # Shell script
    b"<?php",  # PHP
    b"PK\x03\x04",  # ZIP files (unless expected as DOCX)
]


class FileValidator:
    """Validator for file content security"""

    @staticmethod
    async def validate_file_content(file: UploadFile, expected_type: str) -> None:
        """
        Validate file content by checking magic bytes and forbidden signatures.
        
        Args:
            file: Uploaded file to validate
            expected_type: Expected MIME type of the file
        
        Raises:
            ValidationError: If file content is invalid or potentially dangerous
        """
        # Read first 1024 bytes to check magic bytes
        content = await file.read(1024)
        await file.seek(0)  # Reset file pointer
        
        if not content:
            raise ValidationError("File appears to be empty")
        
        # Check for forbidden signatures first (security check)
        for forbidden in FORBIDDEN_SIGNATURES:
            if content.startswith(forbidden):
                # Exception: DOCX files use PK\x03\x04 (ZIP signature)
                if expected_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    if content.startswith(DOCX_MAGIC):
                        continue  # This is expected for DOCX
                
                # Otherwise, this is a dangerous file
                raise ValidationError(
                    f"File contains forbidden signature: {forbidden.hex()}. "
                    "Executable files and scripts are not allowed."
                )
        
        # Check magic bytes match expected type
        expected_magic = FILE_MAGIC_BYTES.get(expected_type)
        if not expected_magic:
            # Unknown file type
            return
        
        # Handle list of possible magic bytes (e.g., TXT with or without BOM)
        if isinstance(expected_magic, list):
            magic_match = any(content.startswith(magic) for magic in expected_magic)
        else:
            magic_match = content.startswith(expected_magic)
        
        if not magic_match:
            raise ValidationError(
                f"File content does not match expected type {expected_type}. "
                "File may have been renamed or corrupted."
            )
        
        # Additional validation for DOCX (ZIP structure)
        if expected_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            await FileValidator._validate_docx_structure(file)
    
    @staticmethod
    async def _validate_docx_structure(file: UploadFile) -> None:
        """
        Validate DOCX file has proper ZIP structure.
        
        Args:
            file: Uploaded file to validate
        
        Raises:
            ValidationError: If DOCX structure is invalid
        """
        try:
            content = await file.read()
            await file.seek(0)  # Reset file pointer
            
            # Try to open as ZIP file
            with zipfile.ZipFile(io.BytesIO(content), "r") as zip_file:
                # Check for required DOCX files
                required_files = [
                    "[Content_Types].xml",
                    "_rels/.rels",
                    "word/document.xml",
                ]
                
                file_names = zip_file.namelist()
                for required in required_files:
                    if not any(name.endswith(required) for name in file_names):
                        raise ValidationError(
                            f"Invalid DOCX structure: missing required file '{required}'"
                        )
        except zipfile.BadZipFile as e:
            raise ValidationError("Invalid DOCX file: corrupted ZIP structure") from e
        except Exception as e:
            raise ValidationError(f"Failed to validate DOCX structure: {str(e)}") from e
    
    @staticmethod
    async def check_zip_bomb(file: UploadFile) -> None:
        """
        Check for potential ZIP bomb (high compression ratio attack).
        
        Args:
            file: Uploaded file to check
        
        Raises:
            ValidationError: If file has suspicious compression ratio
        """
        try:
            content = await file.read()
            await file.seek(0)  # Reset file pointer
            
            # Only check ZIP-based formats (DOCX uses ZIP internally)
            if not content.startswith(DOCX_MAGIC):
                return  # Not a ZIP-based file
            
            # Open as ZIP to check compression ratio
            with zipfile.ZipFile(io.BytesIO(content), "r") as zip_file:
                total_size = len(content)
                extracted_size = sum(info.file_size for info in zip_file.infolist())
                
                # Calculate compression ratio
                if total_size > 0:
                    compression_ratio = extracted_size / total_size
                    
                    # Alert if ratio exceeds 100 (sign of potential zip bomb)
                    if compression_ratio > 100:
                        logger.warning(
                            f"Potential ZIP bomb detected: compression ratio {compression_ratio:.1f}"
                        )
                        raise ValidationError(
                            f"File has suspicious compression ratio ({compression_ratio:.1f}x). "
                            "This could be a ZIP bomb attack."
                        )
        except zipfile.BadZipFile:
            # Not a ZIP file, skip check
            return
        except ValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.warning(f"Error checking ZIP bomb: {e}")
            # Don't fail on errors, just log them

