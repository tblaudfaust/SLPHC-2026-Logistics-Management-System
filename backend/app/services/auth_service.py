from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.services import audit_service
from app.services.permission_service import effective_permission_codes


def authenticate(
    db: Session, *, email: str, password: str, ip_address: str | None, user_agent: str | None
) -> User:
    user = db.scalar(select(User).where(User.email == email))

    if user and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        audit_service.record(
            db,
            user_id=user.id,
            action="login_blocked_locked",
            entity_type="user",
            entity_id=str(user.id),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()
        raise HTTPException(
            status.HTTP_423_LOCKED,
            f"Account locked due to repeated failed logins. Try again after {user.locked_until.isoformat()}.",
        )

    if not user or not user.is_active or not verify_password(password, user.hashed_password):
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.LOCKOUT_MINUTES)
            audit_service.record(
                db,
                user_id=user.id,
                action="login_failed",
                entity_type="user",
                entity_id=str(user.id),
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    audit_service.record(
        db, user_id=user.id, action="login", entity_type="user", entity_id=str(user.id),
        ip_address=ip_address, user_agent=user_agent,
    )
    db.commit()
    db.refresh(user)
    return user


def issue_tokens(db: Session, user: User, *, ip_address: str | None, user_agent: str | None) -> tuple[str, str]:
    permission_codes = sorted(effective_permission_codes(user))
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={"roles": [r.name for r in user.roles], "permissions": permission_codes},
    )

    raw_refresh = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=refresh_token_expiry(),
            user_agent=user_agent,
            ip_address=ip_address,
        )
    )
    db.commit()
    return access_token, raw_refresh


def rotate_refresh_token(
    db: Session, raw_refresh_token: str, *, ip_address: str | None, user_agent: str | None
) -> tuple[str, str, User]:
    token_hash = hash_refresh_token(raw_refresh_token)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    if not stored or not stored.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token is invalid or expired.")

    stored.revoked_at = datetime.now(timezone.utc)
    user = stored.user
    access_token, new_raw_refresh = issue_tokens(db, user, ip_address=ip_address, user_agent=user_agent)
    stored.replaced_by_token_hash = hash_refresh_token(new_raw_refresh)
    db.commit()
    return access_token, new_raw_refresh, user


def revoke_refresh_token(db: Session, raw_refresh_token: str) -> None:
    token_hash = hash_refresh_token(raw_refresh_token)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if stored and stored.revoked_at is None:
        stored.revoked_at = datetime.now(timezone.utc)
        db.commit()
