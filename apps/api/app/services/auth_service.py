"""
Authentication service for user management and token handling
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.models.auth import User, UserSession, MagicLinkToken
from app.core.exceptions import AuthenticationError, ValidationError
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service for authentication and user management"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def send_magic_link(self, email: str) -> Dict[str, Any]:
        """Send magic link for passwordless authentication"""
        try:
            # Validate email format
            if not email or "@" not in email:
                raise ValidationError("Invalid email format")
            
            # Generate magic link token
            token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(minutes=15)  # 15 minutes expiry
            
            # Check if user exists, create if not
            result = await self.db.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                # Create new user
                user = User(
                    email=email,
                    is_verified=False
                )
                self.db.add(user)
                await self.db.flush()  # Get the user ID
            
            # Create magic link token
            magic_token = MagicLinkToken(
                token=token,
                email=email,
                expires_at=expires_at
            )
            self.db.add(magic_token)
            
            await self.db.commit()
            
            # TODO: Send email with magic link
            # For now, we'll just return the token for development
            magic_link = f"http://localhost:3000/auth/verify?token={token}"
            
            logger.info(f"Magic link generated for {email}: {magic_link}")
            
            return {
                "message": "Magic link sent successfully",
                "email": email,
                "expires_in": 900,  # 15 minutes in seconds
                "magic_link": magic_link  # Only for development
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error sending magic link: {e}")
            raise AuthenticationError(f"Failed to send magic link: {str(e)}")
    
    async def verify_magic_link(self, token: str) -> Dict[str, Any]:
        """Verify magic link token and return access token"""
        try:
            # Find magic link token
            result = await self.db.execute(
                select(MagicLinkToken).where(
                    MagicLinkToken.token == token,
                    MagicLinkToken.is_used == False,
                    MagicLinkToken.is_expired == False,
                    MagicLinkToken.expires_at > datetime.utcnow()
                )
            )
            magic_token = result.scalar_one_or_none()
            
            if not magic_token:
                raise AuthenticationError("Invalid or expired magic link")
            
            # Mark token as used
            magic_token.is_used = True
            magic_token.used_at = datetime.utcnow()
            
            # Get or create user
            result = await self.db.execute(
                select(User).where(User.email == magic_token.email)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                raise AuthenticationError("User not found")
            
            # Update user login time
            user.last_login = datetime.utcnow()
            user.is_verified = True
            
            # Generate access and refresh tokens
            access_token = self._create_access_token(user.id)
            refresh_token = self._create_refresh_token(user.id)
            
            # Create user session
            session = UserSession(
                user_id=user.id,
                session_token=refresh_token,
                expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
            )
            self.db.add(session)
            
            await self.db.commit()
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "is_verified": user.is_verified
                }
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error verifying magic link: {e}")
            raise AuthenticationError(f"Failed to verify magic link: {str(e)}")
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        try:
            # Find active session
            result = await self.db.execute(
                select(UserSession).where(
                    UserSession.session_token == refresh_token,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.utcnow()
                )
            )
            session = result.scalar_one_or_none()
            
            if not session:
                raise AuthenticationError("Invalid or expired refresh token")
            
            # Get user
            result = await self.db.execute(
                select(User).where(User.id == session.user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")
            
            # Update session activity
            session.last_activity = datetime.utcnow()
            
            # Generate new access token
            access_token = self._create_access_token(user.id)
            
            await self.db.commit()
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "is_verified": user.is_verified
                }
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error refreshing token: {e}")
            raise AuthenticationError(f"Failed to refresh token: {str(e)}")
    
    async def logout(self, access_token: str) -> Dict[str, Any]:
        """Logout user and invalidate session"""
        try:
            # Decode token to get user ID
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=["HS256"]
            )
            user_id = payload.get("sub")
            if payload.get("type") != "access":
                raise AuthenticationError("Invalid token type")

            if not user_id:
                raise AuthenticationError("Invalid token")

            # Convert user_id to integer (JWT returns string)
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                raise AuthenticationError("Invalid token: invalid user ID")

            # Deactivate all user sessions
            await self.db.execute(
                update(UserSession)
                .where(UserSession.user_id == user_id)
                .values(is_active=False)
            )
            
            await self.db.commit()
            
            return {"message": "Successfully logged out"}
            
        except JWTError:
            raise AuthenticationError("Invalid token")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error during logout: {e}")
            raise AuthenticationError(f"Failed to logout: {str(e)}")
    
    async def get_current_user(self, access_token: str) -> Dict[str, Any]:
        """Get current user from access token"""
        try:
            # Decode token
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=["HS256"]
            )
            user_id = payload.get("sub")
            if payload.get("type") != "access":
                raise AuthenticationError("Invalid token type")

            if not user_id:
                raise AuthenticationError("Invalid token")

            # Convert user_id to integer (JWT returns string)
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                raise AuthenticationError("Invalid token: invalid user ID")

            # Get user
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")
            
            return {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_verified": user.is_verified,
                "is_admin": user.is_admin,
                "preferred_language": user.preferred_language,
                "timezone": user.timezone,
                "total_tokens_used": user.total_tokens_used,
                "total_documents_created": user.total_documents_created,
                "created_at": user.created_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None
            }
            
        except JWTError:
            raise AuthenticationError("Invalid token")
        except Exception as e:
            logger.error(f"Error getting current user: {e}")
            raise AuthenticationError(f"Failed to get user information: {str(e)}")
    
    def _create_access_token(self, user_id: int) -> str:
        """Create access token"""
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "type": "access"
        }
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    
    def _create_refresh_token(self, user_id: int) -> str:
        """Create refresh token"""
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "type": "refresh"
        }
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")