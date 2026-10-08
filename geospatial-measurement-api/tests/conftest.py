import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client(tmp_path):
    """A TestClient backed by a throw-away SQLite database."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Not used as a context manager on purpose: the app's startup hook
    # (which creates tables in the real database) is skipped.
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def upload(client):
    """Helper: upload bytes under a filename and return the response."""

    def _upload(filename: str, content: bytes):
        return client.post("/api/files/", files={"file": (filename, content)})

    return _upload
