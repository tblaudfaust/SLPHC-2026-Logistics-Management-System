from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import client_ip, client_user_agent, get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.auth import CurrentUser, LoginRequest, TokenResponse
from app.services import auth_service
from app.services.permission_service import effective_permission_codes

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "slphc_refresh_token"


def _set_refresh_cookie(response: Response, raw_refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/api/auth",
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    user = auth_service.authenticate(
        db, email=payload.email, password=payload.password,
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    access_token, raw_refresh = auth_service.issue_tokens(
        db, user, ip_address=client_ip(request), user_agent=client_user_agent(request)
    )
    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(access_token=access_token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_refresh:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token supplied.")

    access_token, new_raw_refresh, _user = auth_service.rotate_refresh_token(
        db, raw_refresh, ip_address=client_ip(request), user_agent=client_user_agent(request)
    )
    _set_refresh_cookie(response, new_raw_refresh)
    return TokenResponse(access_token=access_token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh:
        auth_service.revoke_refresh_token(db, raw_refresh)
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/auth")
    return {"detail": "Logged out."}


@router.get("/me", response_model=CurrentUser)
def me(current_user: User = Depends(get_current_user)):
    permission_codes = sorted(effective_permission_codes(current_user))
    return CurrentUser(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        roles=[r.name for r in current_user.roles],
        permissions=permission_codes,
        region_id=current_user.region_id,
        district_id=current_user.district_id,
    )
