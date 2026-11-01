import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_geo_states():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/geo/states")
        assert res.status_code == 200
        states = res.json()
        assert len(states) >= 30
        codes = {s["state_code"] for s in states}
        assert "MH" in codes
        assert "DL" in codes
        assert "BR" in codes
        assert "UP" in codes

@pytest.mark.asyncio
async def test_services_pan_india_search():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Search for Bihar
        res = await client.get("/api/v1/services?state=Bihar")
        assert res.status_code == 200
        bihar_services = res.json()
        assert len(bihar_services) >= 2
        titles = [s["title"] for s in bihar_services]
        assert any("RTPS Bihar" in t for t in titles)

        # Keyword search for driving license
        res = await client.get("/api/v1/services?query=driving")
        assert res.status_code == 200
        dl_services = res.json()
        assert len(dl_services) >= 1

        # Search the official certificate service directory
        res = await client.get("/api/v1/services?query=Aaple%20Sarkar")
        assert res.status_code == 200
        certificate_services = res.json()
        assert len(certificate_services) >= 1

@pytest.mark.asyncio
async def test_existing_certificate_draft_uses_official_maharashtra_portal():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # The legacy service ID remains compatible but no longer points at a local mock.
        res = await client.post("/api/v1/applications", json={"service_id": "mock-citizen-certificate"})
        assert res.status_code == 201
        data = res.json()
        app_id = data["id"]
        expected_portal = "https://aaplesarkar.mahaonline.gov.in/en/CommonForm/CitizenServices_RTS"
        assert data["portal_url"] == expected_portal

        # Check portal endpoint
        portal_res = await client.get(f"/api/v1/applications/{app_id}/portal")
        assert portal_res.status_code == 200
        portal_data = portal_res.json()
        assert portal_data["portal_url"] == expected_portal

@pytest.mark.asyncio
async def test_custom_application_resolves_full_state_name_to_https_portal():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/applications/custom", json={
            "request_text": "Help me apply for an income certificate",
            "jurisdiction": "Maharashtra",
        })
        assert created.status_code == 201
        application_id = created.json()["application_id"]

        detail = await client.get(f"/api/v1/applications/{application_id}")
        assert detail.status_code == 200
        data = detail.json()
        assert data["custom_state"] == "Maharashtra"
        assert data["portal_url"].startswith("https://")
        assert "localhost" not in data["portal_url"]

@pytest.mark.asyncio
async def test_custom_application_does_not_guess_a_portal_for_unknown_jurisdiction():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/applications/custom", json={
            "request_text": "Help me apply for a local service",
            "jurisdiction": "Unlisted Region",
        })
        assert created.status_code == 201
        application_id = created.json()["application_id"]

        detail = await client.get(f"/api/v1/applications/{application_id}")
        assert detail.status_code == 200
        assert detail.json()["portal_url"] is None

@pytest.mark.asyncio
async def test_custom_application_rejects_non_https_portal_urls():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/applications/custom", json={
            "request_text": "Help me apply for a local service",
            "jurisdiction": "Maharashtra",
            "portal_url": "http://localhost:9090",
        })
        assert created.status_code == 422
        assert "HTTPS" in created.json()["detail"]
