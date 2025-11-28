#!/usr/bin/env python3
"""
Script to set a hashed password for admin user.
This replaces the temporary ADMIN_TEMP_PASSWORD with a proper bcrypt hash.

Usage:
    python scripts/set-admin-password.py <email> <password>
    
Example:
    python scripts/set-admin-password.py admin@tesigo.com "NewSecurePassword123!"
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent / "apps" / "api"
sys.path.insert(0, str(project_root))

from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.auth import User
from app.services.auth_service import AuthService


async def set_admin_password(email: str, password: str):
    """Set hashed password for admin user"""
    
    if len(password) < 8:
        print("❌ Password must be at least 8 characters long")
        return False
    
    async with AsyncSessionLocal() as db:
        # Find admin user
        result = await db.execute(
            select(User).where(
                User.email == email,
                User.is_admin == True,  # noqa: E712
            )
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"❌ Admin user not found: {email}")
            print("   Make sure the user exists and is_admin=True")
            return False
        
        # Hash password
        password_hash = AuthService.hash_password(password)
        
        # Update user
        await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(password_hash=password_hash)
        )
        await db.commit()
        
        print(f"✅ Password updated for {email}")
        print(f"   User ID: {user.id}")
        print(f"   Password hash: {password_hash[:20]}...")
        print("\n🔐 You can now login with this password!")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        
        return True


async def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/set-admin-password.py <email> <password>")
        print("\nExample:")
        print('  python scripts/set-admin-password.py admin@tesigo.com "MySecurePassword123!"')
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    print(f"🔧 Setting password for admin: {email}")
    print("=" * 60)
    
    success = await set_admin_password(email, password)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
