"""Authentication, JWT token lifecycle, password hashing, and role authorization dependencies."""

from datetime import datetime, timedelta
import logging
import re
import secrets
from typing import Dict, Any, List, Optional, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import uuid as uuid_pkg

from backend.config import settings
from backend.database import get_db
from backend.models.user import User, UserRole

logger = logging.getLogger(__name__)

# Passlib CryptContext for password hashing with bcrypt (rounds=12)
pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12, deprecated="auto")

# OAuth2 scheme instances
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=True)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ------------------------------------------------------------------------------
# 1. Password Hashing & Verification Functions
# ------------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash plain text password using passlib bcrypt with rounds=12."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password.

    Returns False on any error or invalid hash without raising exceptions.
    """
    try:
        if not plain_password or not hashed_password:
            return False
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.warning(f"Password verification encountered exception: {e}")
        return False


def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength against complexity guidelines.

    Returns:
        dict: {"valid": bool, "errors": list[str]}
    """
    errors: List[str] = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password):
        errors.append("Password must contain at least one special character")

    return {"valid": len(errors) == 0, "errors": errors}


# ------------------------------------------------------------------------------
# 2. JWT Token Lifecycle Functions
# ------------------------------------------------------------------------------
from datetime import datetime, timedelta, timezone

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create signed JWT access token.

    Payload includes sub, role, uuid, iat, exp, and type='access'.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Ensure role is serialized as string if passed as Enum
    role_val = to_encode.get("role")
    if isinstance(role_val, UserRole):
        to_encode["role"] = role_val.value

    # Ensure uuid is serialized as string if passed as UUID
    uuid_val = to_encode.get("uuid")
    if isinstance(uuid_val, uuid_pkg.UUID):
        to_encode["uuid"] = str(uuid_val)

    to_encode.update({
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    })
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create signed JWT refresh token valid for 7 days.

    Payload includes sub, uuid, iat, exp, and type='refresh'.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    uuid_val = to_encode.get("uuid")
    if isinstance(uuid_val, uuid_pkg.UUID):
        to_encode["uuid"] = str(uuid_val)

    to_encode.update({
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "refresh",
    })

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify JWT token payload.

    Returns payload dict if valid, or None if expired or invalid. Never raises exceptions.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
    except Exception as e:
        logger.warning(f"Unexpected token verification failure: {e}")
        return None


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate access token, raising HTTP 401 error if invalid or expired."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = verify_token(token)
    if not payload:
        raise credentials_exception

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type for access authentication",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if not sub:
        raise credentials_exception

    return payload


# ------------------------------------------------------------------------------
# 3. FastAPI Authorization Dependencies
# ------------------------------------------------------------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """FastAPI dependency: Extract and validate user from Bearer JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or user not found",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    user_uuid = payload.get("uuid")
    email = payload.get("email")
    sub = payload.get("sub")

    user = None
    if user_uuid:
        try:
            parsed_uuid = uuid_pkg.UUID(str(user_uuid))
            user = db.query(User).filter(User.uuid == parsed_uuid, User.deleted_at == None).first()
        except (ValueError, TypeError):
            pass

    if not user and email:
        user = db.query(User).filter(User.email == email, User.deleted_at == None).first()

    if not user and sub:
        try:
            if isinstance(sub, int) or (isinstance(sub, str) and sub.isdigit()):
                user = db.query(User).filter(User.id == int(sub), User.deleted_at == None).first()
            else:
                user = db.query(User).filter(User.email == str(sub), User.deleted_at == None).first()
        except Exception:
            pass

    if not user:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated or banned",
        )

    return user


def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency: Ensure user account is active."""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated or soft banned",
        )
    return user


def require_role(*allowed_roles: Any) -> Callable[..., User]:
    """Dependency factory returning a dependency function that enforces specific roles."""
    normalized_roles = [
        r.value if isinstance(r, UserRole) else str(r).lower()
        for r in allowed_roles
    ]

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_str = current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role).lower()
        if user_role_str not in normalized_roles:
            logger.warning(
                f"Role authorization failed for user {current_user.email}. "
                f"Role '{user_role_str}' not in required list {normalized_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of the following roles: {', '.join(normalized_roles)}",
            )
        return current_user

    return role_checker


def require_admin(current_user: User = Depends(require_role(UserRole.ADMIN))) -> User:
    """FastAPI dependency shortcut: Enforce Admin role access."""
    return current_user


def require_authority(current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.AUTHORITY))) -> User:
    """FastAPI dependency shortcut: Enforce Authority or Admin role access."""
    return current_user


def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """FastAPI dependency: Extract user if valid token present, otherwise return None without raising."""
    if not token:
        return None

    payload = verify_token(token)
    if not payload or payload.get("type") != "access":
        return None

    user_uuid = payload.get("uuid")
    email = payload.get("sub")

    try:
        query = db.query(User)
        if user_uuid:
            try:
                parsed_uuid = uuid_pkg.UUID(str(user_uuid))
                user = query.filter(User.uuid == parsed_uuid).first()
            except ValueError:
                user = query.filter(User.email == email).first()
        else:
            user = query.filter(User.email == email).first()

        if user and user.is_active:
            return user
    except Exception as e:
        logger.warning(f"Optional user retrieval failed gracefully: {e}")

    return None


# ------------------------------------------------------------------------------
# 4. Account Security & Lockout Handlers
# ------------------------------------------------------------------------------
def check_account_locked(user: User) -> bool:
    """Check whether account is currently locked, unlocking automatically if lockout period expired."""
    if user.locked_until is None:
        return False

    now = datetime.utcnow()
    if now > user.locked_until:
        # Lockout period has elapsed; reset lock state
        user.locked_until = None
        user.failed_login_attempts = 0
        return False

    return True


def handle_failed_login(user: User, db: Session) -> None:
    """Increment failed login attempts and lock account for 30 minutes after 5 consecutive failures."""
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= 5:
        user.locked_until = datetime.utcnow() + timedelta(minutes=30)
        logger.warning(f"Account for {user.email} locked until {user.locked_until} due to 5 failed login attempts.")
    
    db.commit()
    db.refresh(user)


def handle_successful_login(user: User, db: Session, ip: str) -> None:
    """Reset failed attempts count, update last login metadata, and set online status."""
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    user.last_login_ip = ip
    user.is_online = True

    db.commit()
    db.refresh(user)


# ------------------------------------------------------------------------------
# 5. Secure Token Generation for Email Operations
# ------------------------------------------------------------------------------
def generate_verification_token() -> str:
    """Generate secure 32-character hexadecimal token for email verification."""
    return secrets.token_hex(16)


def generate_reset_token() -> str:
    """Generate secure 32-character hexadecimal token for password reset."""
    return secrets.token_hex(16)
