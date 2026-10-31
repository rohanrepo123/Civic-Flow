from fastapi.testclient import TestClient

from backend.app.main import app


def test_backend_health() -> None:
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "backend"}
