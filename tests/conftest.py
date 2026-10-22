import os

# Must be set BEFORE importing the app
os.environ["API_KEY"] = "test-key"
os.environ["WEBHOOK_SECRET"] = "test-secret"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src import models  # noqa: F401
from src.database import Base, get_db
from src.main import app

test_engine = create_engine("sqlite:///./test.db",
                            connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=test_engine, autoflush=False)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)