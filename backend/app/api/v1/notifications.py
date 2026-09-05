import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.notification import Notification
from app.schemas.common import Page, PaginationParams
from app.schemas.notification import NotificationRead
from app.services.pagination import paginate

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationRead])
def list_notifications(
    params: PaginationParams = Depends(),
    event_type: str | None = None,
    status_filter: str | None = None,
    recipient_user_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("notifications.view")),
):
    stmt = select(Notification)
    if event_type:
        stmt = stmt.where(Notification.event_type == event_type)
    if status_filter:
        stmt = stmt.where(Notification.status == status_filter)
    if recipient_user_id:
        stmt = stmt.where(Notification.recipient_user_id == recipient_user_id)
    if params.search:
        like = f"%{params.search}%"
        stmt = stmt.where((Notification.recipient_email.ilike(like)) | (Notification.recipient_phone.ilike(like)))
    stmt = stmt.order_by(Notification.created_at.desc())
    return paginate(db, stmt, Notification, params, NotificationRead)
