import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def metadata(client):
    response = client.get("/api/metadata")
    assert response.status_code == 200
    payload = response.json()
    if payload["total_records"] == 0:
        pytest.skip("No trajectory records imported. Run: python scripts/import_csv.py")
    return payload


@pytest.fixture(scope="session")
def sample_track_id(client, metadata):
    response = client.get("/api/trajectories", params={"limit": 1})
    assert response.status_code == 200
    payload = response.json()
    if "track_id" in payload:
        return payload["track_id"]
    assert payload["trajectories"]
    return payload["trajectories"][0]["track_id"]
