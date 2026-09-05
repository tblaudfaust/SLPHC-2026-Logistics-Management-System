import math

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.schemas.common import Page, PaginationParams


def paginate(db: Session, stmt: Select, model, params: PaginationParams, schema) -> Page:
    """Applies sort/offset/limit to an ORM `select(model)...` statement and wraps
    the result in a Page envelope. `model` supplies sortable columns via getattr."""
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    if params.sort_by and hasattr(model, params.sort_by):
        column = getattr(model, params.sort_by)
        stmt = stmt.order_by(column.desc() if params.sort_dir == "desc" else column.asc())

    offset = (params.page - 1) * params.page_size
    rows = db.execute(stmt.offset(offset).limit(params.page_size)).scalars().all()

    return Page(
        items=[schema.model_validate(row) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
        pages=max(1, math.ceil(total / params.page_size)),
    )
