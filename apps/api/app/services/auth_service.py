"""
Authentication service for user management and token handling
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ValidationError
from app.models.auth import MagicLinkToken, User, UserSession
from app.utils.jwt_helpers import extract_user_id_from_payload

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service for authentication and user management"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_magic_link(self, email: str) -> dict[str, Any]:
        """Send magic link for passwordless authentication"""
        try:
            # Validate email format
            if not email or "@" not in email:
                raise ValidationError("Invalid email format")

            # Generate magic link token
            token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(minutes=15)  # 15 minutes expiry

            # Check if user exists, create if not
            result = await self.db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if not user:
                # Create new user
                user = User(email=email, is_verified=False)
                self.db.add(user)
                await self.db.flush()  # Get the user ID

            # Create magic link token
            magic_token = MagicLinkToken(
                token=token, email=email, expires_at=expires_at
            )
            self.db.add(magic_token)

            await self.db.commit()

            # Build magic link URL
            magic_link = f"{settings.FRONTEND_URL}/auth/verify?token={token}"

            # Send email with magic link
            from app.services.notification_service import notification_service

            email_sent = await notification_service.send_magic_link(
                email=email,
                magic_link=magic_link,
                token=token,
            )

            if email_sent:
                logger.info(f"✅ Magic link email sent to {email}")
            else:
                logger.warning(
                    f"⚠️ Magic link email not sent to {email} (SMTP not configured). "
                    f"Link: {magic_link}"
                )

            return {
                "message": "Magic link sent successfully",
                "email": email,
                "expires_in": 900,  # 15 minutes in seconds
                "expires_in_minutes": 15,
                "magic_link": magic_link
                if not email_sent
                else None,  # Only return in dev mode
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error sending magic link: {e}")
            raise AuthenticationError(f"Failed to send magic link: {str(e)}") from e

    async def verify_magic_link(self, token: str) -> dict[str, Any]:
        """Verify magic link token and return access token"""
        try:
            # Find magic link token
            result = await self.db.execute(
                select(MagicLinkToken).where(
                    MagicLinkToken.token == token,
                    ~MagicLinkToken.is_used,
                    ~MagicLinkToken.is_expired,
                    MagicLinkToken.expires_at > datetime.utcnow(),
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
                expires_at=datetime.utcnow()
                + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
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
                    "is_verified": user.is_verified,
                },
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error verifying magic link: {e}")
            raise AuthenticationError(f"Failed to verify magic link: {str(e)}") from e

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh access token using refresh token"""
        try:
            # Find active session
            result = await self.db.execute(
                select(UserSession).where(
                    UserSession.session_token == refresh_token,
                    UserSession.is_active.is_(True),
                    UserSession.expires_at > datetime.utcnow(),
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

            # Update session activity and extend expiration
            session.last_activity = datetime.utcnow()
            session.expires_at = datetime.utcnow() + timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS
            )

            # Generate new access token
            access_token = self._create_access_token(user.id)

            await self.db.commit()

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,  # Return refresh_token so frontend can update localStorage
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "is_verified": user.is_verified,
                },
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error refreshing token: {e}")
            raise AuthenticationError(f"Failed to refresh token: {str(e)}") from e

    async def logout(self, access_token: str) -> dict[str, Any]:
        """Logout user and invalidate session"""
        try:
            # Decode token to get user ID
            payload = jwt.decode(
                access_token, settings.jwt_secret_key, algorithms=[settings.JWT_ALG]
            )
            if payload.get("type") != "access":
                raise AuthenticationError("Invalid token type")

            # Extract and validate user ID (convert from string to int)
            user_id = extract_user_id_from_payload(payload)

            # Deactivate all user sessions - ORM knows user_id is Integer
            await self.db.execute(
                update(UserSession)
                .where(UserSession.user_id == user_id)
                .values(is_active=False)
            )

            await self.db.commit()

            # Return user_id for audit logging
            return user_id

        except JWTError as e:
            raise AuthenticationError("Invalid token") from e
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error during logout: {e}")
            raise AuthenticationError(f"Failed to logout: {str(e)}") from e

    async def get_current_user(self, access_token: str) -> dict[str, Any]:
        """Get current user from access token"""
        try:
            # Decode token
            payload = jwt.decode(
                access_token, settings.jwt_secret_key, algorithms=[settings.JWT_ALG]
            )
            if payload.get("type") != "access":
                raise AuthenticationError("Invalid token type")

            # Extract and validate user ID (convert from string to int)
            user_id = extract_user_id_from_payload(payload)

            # Get user - ORM knows User.id is Integer, so it handles type correctly
            result = await self.db.execute(select(User).where(User.id == user_id))
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
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "is_active": user.is_active,
                "total_cost": user.total_cost,
            }

        except JWTError as e:
            raise AuthenticationError("Invalid token") from e
        except Exception as e:
            logger.error(f"Error getting current user: {e}")
            raise AuthenticationError(
                f"Failed to get user information: {str(e)}"
            ) from e

    def _create_access_token(self, user_id: int) -> str:
        """Create access token with iss, aud, and expiration claims"""
        now = datetime.utcnow()
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "iat": now,
            "type": "access",
            "nbf": now,  # Not before - token valid from now
        }

        # Add iss (issuer) if configured
        if settings.JWT_ISS:
            to_encode["iss"] = settings.JWT_ISS

        # Add aud (audience) if configured
        if settings.JWT_AUD:
            to_encode["aud"] = settings.JWT_AUD

        return jwt.encode(
            to_encode, settings.jwt_secret_key, algorithm=settings.JWT_ALG
        )

    def _create_refresh_token(self, user_id: int) -> str:
        """Create refresh token with iss, aud, and expiration claims"""
        now = datetime.utcnow()
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "iat": now,
            "type": "refresh",
            "nbf": now,  # Not before - token valid from now
        }

        # Add iss (issuer) if configured
        if settings.JWT_ISS:
            to_encode["iss"] = settings.JWT_ISS

        # Add aud (audience) if configured
        if settings.JWT_AUD:
            to_encode["aud"] = settings.JWT_AUD

        return jwt.encode(
            to_encode, settings.jwt_secret_key, algorithm=settings.JWT_ALG
        )

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
