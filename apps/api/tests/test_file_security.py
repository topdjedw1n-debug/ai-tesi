"""
File security tests - magic bytes and ZIP bomb validation
"""
import io

import pytest
from fastapi import UploadFile

from app.core.exceptions import ValidationError
from app.services.file_validator import FileValidator


def create_upload_file(content: bytes, filename: str, content_type: str) -> UploadFile:
    """Helper to create UploadFile for testing"""
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers={"content-type": content_type},
    )


@pytest.mark.asyncio
async def test_valid_pdf():
    """Test that valid PDF is accepted"""
    # Simple PDF content (PDF header + minimal structure)
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 0\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF"

    file = create_upload_file(pdf_content, "test.pdf", "application/pdf")

    # Should not raise
    await FileValidator.validate_file_content(file, "application/pdf")


@pytest.mark.asyncio
async def test_fake_pdf_extension():
    """Test that file with .pdf extension but invalid content is rejected"""
    # Text file renamed to .pdf
    fake_pdf_content = b"This is not a PDF file, just plain text"

    file = create_upload_file(fake_pdf_content, "fake.pdf", "application/pdf")

    with pytest.raises(
        ValidationError, match="File content does not match expected type"
    ):
        await FileValidator.validate_file_content(file, "application/pdf")


@pytest.mark.asyncio
async def test_executable_upload_mz():
    """Test that Windows EXE is rejected (MZ signature)"""
    # PE executable header
    exe_content = b"MZ\x90\x00" + b"\x00" * 100

    file = create_upload_file(exe_content, "malware.exe", "application/octet-stream")

    with pytest.raises(ValidationError, match="contains forbidden signature"):
        await FileValidator.validate_file_content(file, "application/pdf")


@pytest.mark.asyncio
async def test_executable_upload_elf():
    """Test that Linux ELF is rejected"""
    # ELF executable header
    elf_content = b"\x7fELF\x01\x01\x01" + b"\x00" * 100

    file = create_upload_file(elf_content, "malware.elf", "application/octet-stream")

    with pytest.raises(ValidationError, match="contains forbidden signature"):
        await FileValidator.validate_file_content(file, "application/pdf")


@pytest.mark.asyncio
async def test_script_upload_shell():
    """Test that shell script is rejected"""
    # Shell script
    script_content = b"#!/bin/bash\necho 'malicious script'"

    file = create_upload_file(script_content, "malware.sh", "text/x-shellscript")

    with pytest.raises(ValidationError, match="contains forbidden signature"):
        await FileValidator.validate_file_content(file, "application/pdf")


@pytest.mark.asyncio
async def test_php_upload():
    """Test that PHP file is rejected"""
    # PHP script
    php_content = b"<?php\necho 'malicious code';"

    file = create_upload_file(php_content, "malware.php", "application/x-php")

    with pytest.raises(ValidationError, match="contains forbidden signature"):
        await FileValidator.validate_file_content(file, "application/pdf")


@pytest.mark.asyncio
async def test_valid_text_file():
    """Test that valid text file is accepted"""
    # Plain text
    text_content = b"This is a valid text file"

    file = create_upload_file(text_content, "test.txt", "text/plain")

    # Should not raise
    await FileValidator.validate_file_content(file, "text/plain")


@pytest.mark.asyncio
async def test_empty_file():
    """Test that empty file is rejected"""
    file = create_upload_file(b"", "empty.txt", "text/plain")

    with pytest.raises(ValidationError, match="appears to be empty"):
        await FileValidator.validate_file_content(file, "text/plain")
