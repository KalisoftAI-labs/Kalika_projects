"""Tests for the EXACT wire format real SAP Ariba uses.

Real Ariba does NOT post raw XML — it sends:
  Content-Type: application/x-www-form-urlencoded
  body: cxml-urlencoded=<url-encoded cXML>

This is the critical path for production integration.
"""

from urllib.parse import quote
import pytest

from tests.test_punchout import SAMPLE_SETUP_REQUEST, SAMPLE_EDIT_REQUEST

pytestmark = pytest.mark.asyncio


async def test_real_ariba_wire_format_setup(client):
    """Ariba form-encodes the cXML in a cxml-urlencoded field."""
    resp = await client.post(
        "/api/punchout/setup",
        data={"cxml-urlencoded": SAMPLE_SETUP_REQUEST},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
    assert "text/xml" in resp.headers.get("content-type", "")
    assert "PunchOutSetupResponse" in resp.text
    assert "StartPage" in resp.text


async def test_real_ariba_wire_format_urlencoded_value(client):
    """Ariba URL-encodes the cXML value inside the form field."""
    encoded = quote(SAMPLE_SETUP_REQUEST)
    resp = await client.post(
        "/api/punchout/setup",
        data={"cxml-urlencoded": encoded},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
    assert "PunchOutSetupResponse" in resp.text


async def test_real_ariba_wire_format_edit(client):
    """Edit mode over the real Ariba form-encoded format."""
    resp = await client.post(
        "/api/punchout/setup",
        data={"cxml-urlencoded": SAMPLE_EDIT_REQUEST},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
    data = resp.json()
    assert data["mode"] == "edit"
    assert data["items_added"] > 0


async def test_real_ariba_wire_format_bad_secret(client):
    """Wrong SharedSecret over form-encoded path → 403."""
    from app.config import settings
    old = settings.PUNCHOUT_SHARED_SECRET
    settings.PUNCHOUT_SHARED_SECRET = "real-ariba-secret-xyz"
    try:
        resp = await client.post(
            "/api/punchout/setup",
            data={"cxml-urlencoded": SAMPLE_SETUP_REQUEST},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 403
    finally:
        settings.PUNCHOUT_SHARED_SECRET = old


async def test_real_ariba_wire_format_missing_field(client):
    """Form POST without cxml-urlencoded field → 400."""
    resp = await client.post(
        "/api/punchout/setup",
        data={"something_else": "x"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 400
