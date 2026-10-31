from fastapi.testclient import TestClient

from browser_worker.app.config import BrowserWorkerSettings
from browser_worker.app.main import create_app


class FakeManager:
    async def start(self) -> None: pass
    async def stop(self) -> None: pass


app = create_app(settings=BrowserWorkerSettings("test-token", frozenset()), manager=FakeManager())


def test_browser_worker_health() -> None:
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "browser-worker"}
