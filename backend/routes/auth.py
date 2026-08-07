"""Authentication router for Smart Community Platform.

Handles user registration, login, token refresh, email verification, password resets,
profile updates, and soft deletion with strict security enforcement.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models.user import User, UserRole
from backend.schemas.user import (
    UserRegister,
    UserLogin,
    UserResponse,
    UserProfileResponse,
    UserPublicResponse,
    UserUpdate,
    UserChangePassword,
    UserForgotPassword,
    UserResetPassword,
    TokenResponse,
)
from backend.utils.auth import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
    check_account_locked,
    handle_failed_login,
    handle_successful_login,
    generate_verification_token,
    generate_reset_token,
)
from backend.utils.email import (
    send_verification_email,
    send_password_reset_email,
    send_password_changed_email,
)

router = APIRouter(tags=["Authentication"])
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# 1. POST /api/auth/register
# ------------------------------------------------------------------------------
@router.post("/register", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserRegister, db: Session = Depends(get_db)):
    """Register a new user account, enforce password strength, and send verification email."""
    # 1. Check if email already exists
    clean_email = user_in.email.strip().lower()
    existing_user = db.query(User).filter(User.email == clean_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered. Please login or use forgot password.",
        )

    # 2. Validate password strength
    strength_check = validate_password_strength(user_in.password)
    if not strength_check.get("valid"):
        errors = strength_check.get("errors", [])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password too weak: {', '.join(errors)}",
        )

    # 3. Hash password & generate verification token
    hashed_pw = hash_password(user_in.password)
    verif_token = generate_verification_token()
    user_role = user_in.role or UserRole.CITIZEN

    # 4. Instantiate User model
    new_user = User(
        name=user_in.name.strip(),
        email=clean_email,
        password_hash=hashed_pw,
        phone=user_in.phone.strip() if user_in.phone else None,
        role=user_role,
        location_city=user_in.location_city.strip() if user_in.location_city else None,
        is_active=True,
        is_verified=False,
        email_verification_token=verif_token,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        logger.error(f"Error registering user {clean_email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already taken or registration failed.",
        )

    # 5. Send verification email
    email_sent = send_verification_email(
        to_email=new_user.email,
        user_name=new_user.name,
        token=verif_token,
    )

    logger.info(f"New user registered: uuid={new_user.uuid} role={new_user.role}")

    return {
        "message": "Account created successfully. Please check your email to verify your account.",
        "user": UserResponse.model_validate(new_user),
        "email_sent": email_sent,
    }


# ------------------------------------------------------------------------------
# 2. POST /api/auth/login
# ------------------------------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    user_in: Optional[UserLogin] = None,
    db: Session = Depends(get_db),
):
    """Authenticate user credentials and return JWT access and refresh tokens.

    Supports JSON payload or form submission.
    Rate Limiting: Essential to prevent brute-force attacks.
    """
    email: Optional[str] = None
    password: Optional[str] = None
    remember_me: bool = False

    if user_in:
        email = user_in.email
        password = user_in.password
        remember_me = user_in.remember_me
    else:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                body = await request.json()
                email = body.get("email")
                password = body.get("password")
                remember_me = body.get("remember_me", False)
            except Exception:
                pass
        elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            try:
                form = await request.form()
                email = str(form.get("username") or form.get("email") or "")
                password = str(form.get("password") or "")
            except Exception:
                pass

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    clean_email = email.strip().lower()
    user = db.query(User).filter(User.email == clean_email, User.deleted_at == None).first()

    # Generic credentials error to prevent enumeration attacks
    if not user:
        logger.warning(f"Failed login attempt for non-existent user: {clean_email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check account lockout status
    if check_account_locked(user):
        lock_remaining = 30
        if user.locked_until:
            delta = user.locked_until - datetime.utcnow()
            lock_remaining = max(1, int(delta.total_seconds() / 60.0))
        logger.warning(f"Login attempt on locked account: {user.uuid}")
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account temporarily locked due to too many failed attempts. Try again in {lock_remaining} minutes.",
        )

    # Verify password
    if not verify_password(password, user.password_hash):
        handle_failed_login(user, db)
        attempts_left = max(0, 5 - (user.failed_login_attempts or 0))
        logger.warning(f"Failed password check for user: {user.uuid}. Remaining attempts: {attempts_left}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check active status (suspension/ban check)
    if not user.is_active:
        logger.warning(f"Login attempt by suspended user: {user.uuid}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended. Please contact support.",
        )

    # Record login metadata and client IP
    client_ip = request.client.host if request.client else "127.0.0.1"
    handle_successful_login(user, db, ip=client_ip)

    # Issue JWT tokens
    access_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_delta = timedelta(days=30 if remember_me else 7)

    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

    access_token = create_access_token(
        data={"sub": str(user.id), "uuid": str(user.uuid), "role": role_str, "email": user.email},
        expires_delta=access_delta,
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "type": "refresh"},
        expires_delta=refresh_delta,
    )

    logger.info(f"User logged in successfully: {user.uuid} ip={client_ip}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=int(access_delta.total_seconds()),
        user=UserResponse.model_validate(user),
    )


# ------------------------------------------------------------------------------
# 3. POST /api/auth/refresh
# ------------------------------------------------------------------------------
@router.post("/refresh", response_model=Dict[str, Any])
def refresh_access_token(body: Dict[str, str], db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    token_str = body.get("refresh_token")
    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is required.",
        )

    payload = verify_token(token_str)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired. Please login again.",
        )

    user_id_str = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id_str), User.deleted_at == None).first() if user_id_str else None

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive.",
        )

    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    access_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        data={"sub": str(user.id), "uuid": str(user.uuid), "role": role_str, "email": user.email},
        expires_delta=access_delta,
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": int(access_delta.total_seconds()),
    }


# ------------------------------------------------------------------------------
# 4. GET /api/auth/me
# ------------------------------------------------------------------------------
@router.get("/me", response_model=UserProfileResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch complete profile of the authenticated user and update online status."""
    current_user.is_online = True
    current_user.last_seen = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    return current_user


# ------------------------------------------------------------------------------
# 5. POST /api/auth/logout
# ------------------------------------------------------------------------------
@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Terminate current user session by clearing online status."""
    current_user.is_online = False
    current_user.last_seen = datetime.utcnow()
    db.commit()
    logger.info(f"User logged out: {current_user.uuid}")
    return {"message": "Logged out successfully."}


# ------------------------------------------------------------------------------
# 6. GET /api/auth/verify-email/{token}
# ------------------------------------------------------------------------------
@router.get("/verify-email/{token}", response_model=Dict[str, Any])
def verify_email(token: str, db: Session = Depends(get_db)):
    """Confirm user email address via token link."""
    user = db.query(User).filter(User.email_verification_token == token, User.deleted_at == None).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link.",
        )

    user.is_verified = True
    user.email_verification_token = None
    user.updated_at = datetime.utcnow()
    db.commit()

    logger.info(f"User email verified: {user.uuid}")
    return {
        "message": "Email verified successfully! You can now login.",
        "user": UserResponse.model_validate(user),
    }


# ------------------------------------------------------------------------------
# 7. POST /api/auth/resend-verification
# ------------------------------------------------------------------------------
@router.post("/resend-verification", status_code=status.HTTP_200_OK)
def resend_verification(body: Dict[str, str], db: Session = Depends(get_db)):
    """Resend email verification token to user. Always returns generic success."""
    email_val = body.get("email", "").strip().lower()
    generic_msg = {"message": "If that email is registered, a verification link was sent."}

    if not email_val:
        return generic_msg

    user = db.query(User).filter(User.email == email_val, User.deleted_at == None).first()
    if not user:
        return generic_msg

    if user.is_verified:
        return {"message": "Email is already verified. Please login."}

    new_token = generate_verification_token()
    user.email_verification_token = new_token
    db.commit()

    send_verification_email(to_email=user.email, user_name=user.name, token=new_token)
    logger.info(f"Resent verification email to: {user.uuid}")

    return generic_msg


# ------------------------------------------------------------------------------
# 8. POST /api/auth/forgot-password
# ------------------------------------------------------------------------------
@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(data: UserForgotPassword, db: Session = Depends(get_db)):
    """Initiate password recovery flow. Always returns generic message to prevent email enumeration."""
    clean_email = data.email.strip().lower()
    generic_response = {
        "message": "If that email is registered, you will receive a password reset link shortly."
    }

    user = db.query(User).filter(User.email == clean_email, User.deleted_at == None).first()
    if user and user.is_active:
        reset_tok = generate_reset_token()
        user.password_reset_token = reset_tok
        user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        db.commit()

        send_password_reset_email(to_email=user.email, user_name=user.name, token=reset_tok)
        logger.info(f"Password reset link requested for user: {user.uuid}")

    return generic_response


# ------------------------------------------------------------------------------
# 9. POST /api/auth/reset-password
# ------------------------------------------------------------------------------
@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(data: UserResetPassword, db: Session = Depends(get_db)):
    """Reset user password using token from reset email."""
    user = db.query(User).filter(User.password_reset_token == data.token, User.deleted_at == None).first()
    if not user or not user.password_reset_expires or user.password_reset_expires < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link.",
        )

    # Validate new password strength
    strength_check = validate_password_strength(data.new_password)
    if not strength_check.get("valid"):
        errors = strength_check.get("errors", [])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password too weak: {', '.join(errors)}",
        )

    # Prevent re-using existing password
    if verify_password(data.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password.",
        )

    user.password_hash = hash_password(data.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    user.failed_login_attempts = 0
    user.locked_until = None
    user.updated_at = datetime.utcnow()
    db.commit()

    send_password_changed_email(to_email=user.email, user_name=user.name)
    logger.info(f"Password reset successful for user: {user.uuid}")

    return {"message": "Password reset successfully. You can now login."}


# ------------------------------------------------------------------------------
# 10. PUT /api/auth/change-password
# ------------------------------------------------------------------------------
@router.put("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    data: UserChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change password for logged-in user."""
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    strength_check = validate_password_strength(data.new_password)
    if not strength_check.get("valid"):
        errors = strength_check.get("errors", [])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password too weak: {', '.join(errors)}",
        )

    if verify_password(data.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password.",
        )

    current_user.password_hash = hash_password(data.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()

    send_password_changed_email(to_email=current_user.email, user_name=current_user.name)
    logger.info(f"Password changed by user: {current_user.uuid}")

    return {"message": "Password changed successfully."}


# ------------------------------------------------------------------------------
# 11. PUT /api/auth/update-profile
# ------------------------------------------------------------------------------
@router.put("/update-profile", response_model=UserProfileResponse)
def update_profile(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Partial update of current user profile information."""
    update_data = user_in.model_dump(exclude_unset=True)

    for field, val in update_data.items():
        if hasattr(current_user, field):
            setattr(current_user, field, val)

    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)

    logger.info(f"Profile updated for user: {current_user.uuid}")
    return current_user


# ------------------------------------------------------------------------------
# 12. DELETE /api/auth/delete-account
# ------------------------------------------------------------------------------
@router.delete("/delete-account", status_code=status.HTTP_200_OK)
def delete_account(
    body: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft delete user account and anonymize PII data."""
    password_val = body.get("password")
    if not password_val or not verify_password(password_val, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password.",
        )

    current_user.deleted_at = datetime.utcnow()
    current_user.is_active = False
    current_user.is_online = False

    # Anonymize Personal Identifiable Information (PII)
    current_user.email = f"deleted_{current_user.uuid}@deleted.com"
    current_user.name = "Deleted User"
    current_user.phone = None
    current_user.avatar_url = None
    current_user.bio = None

    db.commit()

    logger.warning(f"Account deleted and anonymized: {current_user.uuid}")
    return {"message": "Account deleted successfully."}

