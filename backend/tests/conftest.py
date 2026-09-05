"""Runs against a real Postgres database (set TEST_DATABASE_URL, defaults to
the docker-compose 'postgres' service with a '_test' suffix database) — the
schema uses Postgres-specific types (UUID, JSONB) so SQLite is not a substitute.
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://slphc:change-me@localhost:5432/slphc_logistics_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

from app.api.deps import get_db  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.models.rbac import Permission, Role  # noqa: E402

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture()
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection)
    session = TestingSessionLocal()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def seed_permission(db_session):
    def _seed(code: str, module: str = "test") -> Permission:
        perm = Permission(code=code, module=module)
        db_session.add(perm)
        db_session.flush()
        return perm

    return _seed


@pytest.fixture()
def seed_role(db_session):
    def _seed(name: str, permission_codes: list[str] | None = None) -> Role:
        role = Role(name=name)
        if permission_codes:
            perms = db_session.query(Permission).filter(Permission.code.in_(permission_codes)).all()
            role.permissions = perms
        db_session.add(role)
        db_session.flush()
        return role

    return _seed
