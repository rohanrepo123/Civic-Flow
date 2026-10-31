import pytest
from fastapi import HTTPException
from app.main import validate_target

def test_domain_allowlist_accepts_service_domain_and_subdomains():
    validate_target("https://portal.example.gov/path", ["example.gov"])

def test_domain_allowlist_rejects_unapproved_host():
    with pytest.raises(HTTPException) as exc:
        validate_target("https://evil.example.net", ["example.gov"])
    assert exc.value.status_code == 403

@pytest.mark.parametrize("url", ["http://portal.example.gov", "https://localhost", "https://127.0.0.1"])
def test_navigation_blocks_non_https_and_local_targets(url):
    with pytest.raises(HTTPException): validate_target(url, ["example.gov"])
