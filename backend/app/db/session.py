from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
# autoflush=True (the default — kept explicit since it matters here): several
# services read a relationship on an object added-but-not-yet-flushed in the
# same request (e.g. notification_service rendering a template right after
# inventory_service creates a ledger row). With autoflush off, that lazy
# load silently returns None instead of flushing first and querying —
# confirmed as a real bug via app/api/v1/inventory.py's goods-receipt path.
SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
