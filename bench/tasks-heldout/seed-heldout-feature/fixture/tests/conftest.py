import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app([
        {"title": "Dune", "author": "Frank Herbert"},
        {"title": "Piranesi", "author": "Susanna Clarke", "checked_out_by": "ana"},
    ]))
