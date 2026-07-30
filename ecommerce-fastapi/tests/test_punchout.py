"""Snapshot tests: compare generated cXML against known-good old Django output."""

SAMPLE_SETUP_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML payloadID="1680000000-12345678@ariba.com" timestamp="2026-01-01T12:00:00-05:00" version="1.2.014">
  <Header>
    <From>
      <Credential domain="NetworkID">
        <Identity>AN01284122159-T</Identity>
      </Credential>
    </From>
    <To>
      <Credential domain="NetworkID">
        <Identity>buyer-org-network-id</Identity>
      </Credential>
    </To>
    <Sender>
      <Credential domain="NetworkID">
        <Identity>buyer-org-network-id</Identity>
        <SharedSecret>test-secret</SharedSecret>
      </Credential>
      <UserAgent>Ariba</UserAgent>
    </Sender>
  </Header>
  <Request>
    <PunchOutSetupRequest operation="create">
      <BuyerCookie>abc123</BuyerCookie>
      <Extrinsic name="UserEmail">buyer@company.com</Extrinsic>
      <BrowserFormPost>
        <URL>https://buyer.ariba.com/punchback</URL>
      </BrowserFormPost>
    </PunchOutSetupRequest>
  </Request>
</cXML>"""

SAMPLE_EDIT_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML payloadID="1680000000-87654321@ariba.com" timestamp="2026-01-01T12:00:00-05:00" version="1.2.014">
  <Header>
    <From><Credential domain="NetworkID"><Identity>AN01284122159-T</Identity></Credential></From>
    <To><Credential domain="NetworkID"><Identity>buyer-org</Identity></Credential></To>
    <Sender><Credential domain="NetworkID"><Identity>buyer-org</Identity><SharedSecret>test-secret</SharedSecret></Credential><UserAgent>Ariba</UserAgent></Sender>
  </Header>
  <Request>
    <PunchOutSetupRequest operation="edit">
      <BuyerCookie>edit-cookie-456</BuyerCookie>
      <BrowserFormPost><URL>https://buyer.ariba.com/punchback</URL></BrowserFormPost>
      <ItemOut quantity="5">
        <ItemID><SupplierPartID>SAF-GLOVE-001</SupplierPartID></ItemID>
      </ItemOut>
      <ItemOut quantity="2">
        <ItemID><SupplierPartID>SAF-EYE-001</SupplierPartID></ItemID>
      </ItemOut>
    </PunchOutSetupRequest>
  </Request>
</cXML>"""


def test_parse_cxml():
    from app.services.punchout_service import _parse_cxml, _get_text
    root = _parse_cxml(SAMPLE_SETUP_REQUEST)
    assert root is not None
    assert _get_text(root, ".//Credential/SharedSecret") == "test-secret"
    assert _get_text(root, ".//Header/From/Credential/Identity") == "AN01284122159-T"
    assert _get_text(root, ".//PunchOutSetupRequest/BuyerCookie") == "abc123"
    assert _get_text(root, ".//PunchOutSetupRequest/BrowserFormPost/URL") == "https://buyer.ariba.com/punchback"


def test_parse_cxml_empty():
    from app.services.punchout_service import _parse_cxml
    assert _parse_cxml("") is None
    assert _parse_cxml("not xml") is None


def test_generate_setup_response_has_doctype():
    from app.services.punchout_service import _generate_setup_response
    xml = _generate_setup_response("https://kalikaindia.com/?punchout_session=test123")
    assert "<!DOCTYPE cXML SYSTEM" in xml
    assert "PunchOutSetupResponse" in xml
    assert "StartPage" in xml
    assert "https://kalikaindia.com/?punchout_session=test123" in xml


def test_generate_setup_response_has_status_200():
    from app.services.punchout_service import _generate_setup_response
    xml = _generate_setup_response("https://kalikaindia.com/?ps=test")
    assert 'code="200"' in xml or "code='200'" in xml
    assert "text=\"success\"" in xml or "text='success'" in xml


async def test_setup_endpoint_invalid_cxml(client):
    resp = await client.post("/api/punchout/setup", content="not valid cxml")
    assert resp.status_code == 400


async def test_setup_endpoint_missing_secret(client):
    from app.config import settings
    old_secret = settings.PUNCHOUT_SHARED_SECRET
    settings.PUNCHOUT_SHARED_SECRET = "different-secret"
    try:
        resp = await client.post(
            "/api/punchout/setup",
            content=SAMPLE_SETUP_REQUEST,
            headers={"Content-Type": "text/xml"},
        )
        assert resp.status_code == 403
    finally:
        settings.PUNCHOUT_SHARED_SECRET = old_secret


async def test_setup_endpoint_success(client):
    resp = await client.post(
        "/api/punchout/setup",
        content=SAMPLE_SETUP_REQUEST,
        headers={"Content-Type": "text/xml"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    assert resp.headers["content-type"] == "text/xml; charset=utf-8"
    body = resp.text
    assert "<!DOCTYPE cXML SYSTEM" in body
    assert "PunchOutSetupResponse" in body
    assert "StartPage" in body


async def test_setup_endpoint_edit_mode(client):
    resp = await client.post(
        "/api/punchout/setup",
        content=SAMPLE_EDIT_REQUEST,
        headers={"Content-Type": "text/xml"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    assert data["mode"] == "edit"
    assert data["items_added"] > 0
    assert data["return_url"] == "https://buyer.ariba.com/punchback"
    assert data["buyer_cookie"] == "edit-cookie-456"
