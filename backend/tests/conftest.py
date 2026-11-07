import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.seed import seed


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEAGUE_DB", str(tmp_path / "test.sqlite3"))
    seed()
    with TestClient(app) as c:
        yield c
