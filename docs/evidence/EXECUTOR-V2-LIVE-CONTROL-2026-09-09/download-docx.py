import asyncio,hashlib,sys
from app.core import database
from app.models.document import Document
from app.services.storage_service import StorageService
async def main():
 async with database.AsyncSessionLocal() as db:
  d=await db.get(Document,12)
  assert d.docx_path and d.docx_sha256,'No recorded DOCX'
  content=await StorageService().download_file(d.docx_path)
  assert hashlib.sha256(content).hexdigest()==d.docx_sha256,'Stored DOCX hash differs'
  sys.stdout.buffer.write(content)
asyncio.run(main())
