"""
End-to-end PunchOut flow test against a REAL running API + mock Ariba.

Run:
  Terminal 1:  uvicorn app.main:app --port 8000
  Terminal 2:  python -m scripts.mock_ariba        (port 9001)
  Terminal 3:  python -m scripts.e2e_punchout

Simulates the complete SAP Ariba PunchOut session:
  1. Ariba sends PunchOutSetupRequest â†’ we return SetupResponse + StartPage URL
  2. Buyer opens StartPage, shops, adds to cart
  3. Buyer checks out â†’ cXML PunchOutOrderMessage POSTed to Ariba (mock)
  4. Mock Ariba validates the cXML (DTD + business rules) â†’ PASS/FAIL report
"""

import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API = "http://127.0.0.1:8000"
ARIRA_MOCK = "http://127.0.0.1:9001"

SETUP_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cXML.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML payloadID="e2e-test-123@ariba.com" timestamp="2026-07-31T10:00:00-05:00" version="1.2.014">
  <Header>
    <From><Credential domain="NetworkID"><Identity>AN01284122159-T</Identity></Credential></From>
    <To><Credential domain="NetworkID"><Identity>kalika-buyer-org</Identity></Credential></To>
    <Sender><Credential domain="NetworkID"><Identity>kalika-buyer-org</Identity><SharedSecret>test-secret</SharedSecret></Credential><UserAgent>Ariba</UserAgent></Sender>
  </Header>
  <Request>
    <PunchOutSetupRequest operation="create">
      <BuyerCookie>E2E-COOKIE-001</BuyerCookie>
      <Extrinsic name="UserEmail">buyer@kalika-buyer.com</Extrinsic>
      <BrowserFormPost><URL>{ariba_punchback}</URL></BrowserFormPost>
    </PunchOutSetupRequest>
  </Request>
</cXML>"""

PASS = 0
FAIL = 0


def report(name, ok, detail=""):
    global PASS, FAIL
    mark = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{mark}] {name}" + (f" â€” {detail}" if detail else ""))


def post(url, data, headers=None):
    req = urllib.request.Request(url, data=data.encode("utf-8"), headers=headers or {})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8"), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), dict(e.headers)


def get(url):
    with urllib.request.urlopen(url) as resp:
        return resp.status, resp.read().decode("utf-8")


def main():
    print("=" * 60)
    print("PUNCHOUT END-TO-END FLOW (local, realistic cXML)")
    print("=" * 60)

    # --- Step 1: Ariba sends PunchOutSetupRequest ---
    print("\n[1] Ariba â†’ Kalika: PunchOutSetupRequest")
    setup_xml = SETUP_REQUEST.format(ariba_punchback=f"{ARIRA_MOCK}/punchback")
    status, body, headers = post(f"{API}/api/punchout/setup", setup_xml, {"Content-Type": "text/xml"})
    report("Setup endpoint responds 200", status == 200, f"status={status}")
    report("Response is XML", "text/xml" in headers.get("content-type", ""), headers.get("content-type", ""))
    report("Response has DOCTYPE", "<!DOCTYPE cXML" in body)
    report("Response has PunchOutSetupResponse", "PunchOutSetupResponse" in body)
    report("Response has StartPage URL", "StartPage" in body and "<URL>" in body)

    # --- Extract session from StartPage ---
    import re
    m = re.search(r"punchout_session=([a-f0-9]+)", body)
    if not m:
        report("StartPage URL contains session id", False)
        print("\nRESULT: FAILED (no session) â€” aborting")
        return
    session_id = m.group(1)
    report("StartPage URL contains session id", True, f"session={session_id[:12]}...")

    # --- Step 2: Buyer shops (cart via session token) ---
    print("\n[2] Buyer shops: adds items to cart")
    for pid, qty in [(1, 2), (6, 1)]:
        payload = json.dumps({"product_id": pid, "quantity": qty})
        status, body, _ = post(f"{API}/api/cart/items", payload, {
            "Content-Type": "application/json",
            "X-Cart-Token": session_id,
        })
        ok = status == 201 and json.loads(body)["item_count"] > 0
        report(f"Add product {pid} x{qty}", ok, f"status={status}")

    req = urllib.request.Request(f"{API}/api/cart", headers={"X-Cart-Token": session_id})
    with urllib.request.urlopen(req) as resp:
        cart = json.loads(resp.read().decode("utf-8"))
    report("Cart has expected items", len(cart["items"]) == 2, f"{len(cart['items'])} items")

    # --- Step 3: Checkout with return URL to mock Ariba ---
    print("\n[3] Buyer checks out â†’ cXML POSTed to Ariba (mock)")
    checkout = json.dumps({
        "punchout_return_url": f"{ARIRA_MOCK}/punchback",
        "buyer_cookie": "E2E-COOKIE-001",
    })
    status, body, _ = post(f"{API}/api/cart/checkout", checkout, {
        "Content-Type": "application/json",
        "X-Cart-Token": session_id,
    })
    result = json.loads(body)
    report("Checkout succeeds", status == 200 and result.get("success"), f"status={status}")
    report("Order persisted with items", len(result.get("order", {}).get("items", [])) == 2)
    cxml = result.get("cxml_payload", "")
    report("cXML payload returned", bool(cxml))
    report("cXML has BuyerCookie round-trip", "E2E-COOKIE-001" in cxml)
    report("cXML has UNSPSC classification", "Classification" in cxml)

    # --- Step 4: Mock Ariba received + validated ---
    print("\n[4] Mock Ariba validates received PunchOutOrderMessage")
    status, body = get(f"{ARIRA_MOCK}/received")
    received_list = json.loads(body)
    report("Ariba received the return POST", len(received_list) == 1, f"{len(received_list)} received")
    if received_list:
        checks = received_list[0]["checks"]
        report("DTD valid (official cXML 1.2.014)", checks.get("dtd_valid"))
        report("Version 1.2.014", checks.get("version") == "1.2.014")
        report("BuyerCookie matches setup", checks.get("buyer_cookie") == "E2E-COOKIE-001", str(checks.get("buyer_cookie")))
        report("Sender identity present", bool(checks.get("sender_identity")), str(checks.get("sender_identity")))
        report("SharedSecret present", checks.get("shared_secret_present"))
        report("operationAllowed=create", checks.get("operation") == "create")
        report("Total money present", checks.get("total") is not None, str(checks.get("total")))
        report("2 items in message", checks.get("item_count") == 2, f"{checks.get('item_count')}")
        report("All required fields complete", checks.get("all_required_present"))

    print("\n" + "=" * 60)
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 60)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
