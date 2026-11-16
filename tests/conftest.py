import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.main import create_app


@pytest.fixture
def engine():
    database = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(database, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(database)
    yield database
    database.dispose()


@pytest.fixture
def client(engine):
    settings = Settings(_env_file=None, app_env="test", demo_mode=True)
    with TestClient(create_app(settings, engine)) as test_client:
        yield test_client
