from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import every model module here so Alembic's autogenerate and Base.metadata
# see the full schema. Add new model modules to this list as they are created.
from app.models import location  # noqa: E402,F401
from app.models import warehouse  # noqa: E402,F401
from app.models import rbac  # noqa: E402,F401
from app.models import user  # noqa: E402,F401
from app.models import audit_log  # noqa: E402,F401
from app.models import supplier  # noqa: E402,F401
from app.models import procurement  # noqa: E402,F401
from app.models import asset  # noqa: E402,F401
from app.models import inventory  # noqa: E402,F401
from app.models import notification  # noqa: E402,F401
