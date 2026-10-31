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

        # Search for mock sandbox
        res = await client.get("/api/v1/services?query=mock")
        assert res.status_code == 200
        mock_services = res.json()
        assert len(mock_services) >= 1

@pytest.mark.asyncio
async def test_application_portal_url():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create application for mock citizen certificate
        res = await client.post("/api/v1/applications", json={"service_id": "mock-citizen-certificate"})
        assert res.status_code == 201
        data = res.json()
        app_id = data["id"]
        assert data["portal_url"] == "http://localhost:9090"

        # Check portal endpoint
        portal_res = await client.get(f"/api/v1/applications/{app_id}/portal")
        assert portal_res.status_code == 200
        portal_data = portal_res.json()
        assert portal_data["portal_url"] == "http://localhost:9090"
