import asyncio
from app.core.database import AsyncSessionLocal
from app.models.auth import User
from app.services.auth_service import AuthService
async def main():
 async with AsyncSessionLocal() as db:
  db.add_all([User(id=1,email="qa-manager",full_name="QA operator",is_active=True,is_verified=True,password_hash=AuthService.hash_password("Local-QA-20260907!")), User(id=2,email="qa-other",full_name="QA other operator",is_active=True,is_verified=True,password_hash=AuthService.hash_password("Local-QA-20260907!"))])
  await db.commit()
 print("Isolated users created; no production account used")
asyncio.run(main())
