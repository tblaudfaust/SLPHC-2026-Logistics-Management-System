from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogRead
from app.schemas.common import Page, PaginationParams
from app.services.pagination import paginate

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=Page[AuditLogRead])
def list_audit_logs(
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    _=Depends(require_permission("audit.view")),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if params.search:
        stmt = stmt.where(AuditLog.entity_type.ilike(f"%{params.search}%"))
    return paginate(db, stmt, AuditLog, params, AuditLogRead)
