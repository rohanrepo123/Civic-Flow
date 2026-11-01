from fastapi.testclient import TestClient
import time

from backend.app.main import create_app


def _register(client: TestClient, email: str) -> str:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "very-long-demo-password"})
    assert response.status_code == 201
    return response.json()["access_token"]


def test_authentication_profile_and_cross_account_isolation(monkeypatch):
    from backend.app.agent.nodes.intent import RuleBasedIntentExtractor
    from backend.app.agent.services.curated_knowledge import CuratedKnowledge

    class TestEmbeddings:
        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(
        "backend.app.main.build_intent_extractor",
        lambda: RuleBasedIntentExtractor(),
    )
    knowledge = CuratedKnowledge.default(embeddings=TestEmbeddings())
    monkeypatch.setattr("backend.app.main.CuratedKnowledge.default", lambda: knowledge)
    app = create_app(database_url="sqlite://")
    with TestClient(app) as client:
        first_token = _register(client, "citizen-one@example.com")
        second_token = _register(client, "citizen-two@example.com")
        first = {"Authorization": f"Bearer {first_token}"}
        second = {"Authorization": f"Bearer {second_token}"}

        assert client.get("/api/v1/profile").status_code == 401
        assert client.put("/api/v1/profile", headers=first, json={"age": 27, "city": "Pune"}).status_code == 200
        assert client.get("/api/v1/profile", headers=second).json()["data"] == {}
        assert client.put("/api/v1/profile", headers=first, json={"account": {"otp": "123456"}}).status_code == 422

        document = client.post(
            "/api/v1/documents",
            headers=first,
            files={"file": ("proof.pdf", b"%PDF-1.7\nmock document", "application/pdf")},
        )
        assert document.status_code == 201
        document_id = document.json()["document_id"]
        assert client.get(f"/api/v1/documents/{document_id}/content", headers=second).status_code == 404
        assert client.get(f"/api/v1/documents/{document_id}/content", headers=first).content.startswith(b"%PDF-")

        task_response = client.post("/api/v1/tasks", headers=first, json={"user_request": "Apply for a Maharashtra domicile certificate"})
        assert task_response.status_code == 202
        task_id = task_response.json()["task_id"]
        for _ in range(40):
            latest = client.get(f"/api/v1/tasks/{task_id}", headers=first).json()
            if latest["status"] != "running":
                break
            time.sleep(0.025)
        assert latest["status"] == "failed"
        assert any("Browser Agent is not connected" in error for error in latest["state"]["errors"])
        assert latest["state"]["requirements"]["sources"]
        task_event_rows = client.get(f"/api/v1/tasks/{task_id}/events", headers=first).json()
        assert task_event_rows
        assert len({row["sequence"] for row in task_event_rows}) == len(task_event_rows)
        assert client.get(f"/api/v1/tasks/{task_id}", headers=second).status_code == 404
        assert client.get(f"/api/v1/tasks/{task_id}/events", headers=second).status_code == 404


def test_login_rejects_invalid_credentials_and_token_tampering():
    app = create_app(database_url="sqlite://")
    with TestClient(app) as client:
        token = _register(client, "login@example.com")
        bad_login = client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "wrong-password-long"})
        assert bad_login.status_code == 401
        assert client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {token}tampered"}).status_code == 401
