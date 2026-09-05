import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.permission_service import effective_permission_codes

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_error = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise credentials_error

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise credentials_error

    user = db.scalar(select(User).where(User.id == user_id))
    if not user or not user.is_active:
        raise credentials_error
    return user


def require_permission(permission_code: str):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_permissions = effective_permission_codes(current_user)
        if permission_code not in user_permissions:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Missing required permission: {permission_code}",
            )
        return current_user

    return dependency


def require_role(*role_names: str):
    allowed = set(role_names)

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_role_names = {r.name for r in current_user.roles}
        if not user_role_names & allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role.")
        return current_user

    return dependency


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def client_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")
