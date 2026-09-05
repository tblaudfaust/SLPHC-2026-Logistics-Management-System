import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """Explicit audit call from mutating endpoints/services (brief §15.1).

    Deliberately not an ORM event hook: mutating flows differ enough (who counts
    as the actor, what the 'old' vs 'new' value means for a many-to-many change)
    that an implicit hook would either miss context or need constant overrides.
    Caller is responsible for calling db.flush()/commit() as part of its own
    transaction — this only adds the row to the session.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    return entry
