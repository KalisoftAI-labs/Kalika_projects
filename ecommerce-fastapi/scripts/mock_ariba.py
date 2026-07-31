"""
Mock Ariba receiver — simulates SAP Ariba's PunchOut side for local testing.

Run: python -m scripts.mock_ariba  (port 9001)

Endpoints:
  POST /punchback          receives PunchOutOrderMessage from our checkout
  GET  /received           list of received cXML payloads
  GET  /health
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lxml import etree
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from scripts.dtd_validate import validate_against_dtd

app = FastAPI(title="Mock Ariba")
received: list[dict] = []


def _check_punchout_order_message(xml_str: str) -> dict:
    """Validate like Ariba would: DTD + business checks."""
    checks = {}

    dtd_errors = validate_against_dtd(xml_str)
    checks["dtd_valid"] = len(dtd_errors) == 0
    checks["dtd_errors"] = [f"line {e.line}: {e.message}" for e in dtd_errors[:5]]

    try:
        root = etree.fromstring(xml_str.encode("utf-8"))
        checks["well_formed"] = True
    except Exception as e:
        return {**checks, "well_formed": False, "error": str(e)}

    checks["version"] = root.get("version")
    checks["payloadID"] = bool(root.get("payloadID"))
    checks["timestamp"] = bool(root.get("timestamp"))

    def txt(path):
        el = root.find(path)
        return el.text if el is not None else None

    checks["buyer_cookie"] = txt(".//PunchOutOrderMessage/BuyerCookie")
    checks["sender_identity"] = txt(".//Header/Sender/Credential/Identity")
    checks["shared_secret_present"] = txt(".//Header/Sender/Credential/SharedSecret") is not None
    checks["currency"] = txt(".//PunchOutOrderMessageHeader/Total/Money").strip() if txt(".//PunchOutOrderMessageHeader/Total/Money") else None
    checks["total"] = txt(".//PunchOutOrderMessageHeader/Total/Money")
    checks["operation"] = root.find(".//PunchOutOrderMessageHeader").get("operationAllowed") if root.find(".//PunchOutOrderMessageHeader") is not None else None

    item_ins = root.findall(".//PunchOutOrderMessage/ItemIn")
    checks["item_count"] = len(item_ins)
    items = []
    for it in item_ins:
        items.append({
            "supplier_part_id": txt_from(it, ".//ItemID/SupplierPartID"),
            "quantity": it.get("quantity"),
            "unit_price": txt_from(it, ".//ItemDetail/UnitPrice/Money"),
            "description": txt_from(it, ".//ItemDetail/Description"),
            "uom": txt_from(it, ".//ItemDetail/UnitOfMeasure"),
            "unspsc": txt_from(it, ".//ItemDetail/Classification"),
        })
    checks["items"] = items

    checks["all_required_present"] = all([
        checks["version"] == "1.2.014",
        checks["payloadID"], checks["timestamp"],
        checks["buyer_cookie"], checks["sender_identity"],
        checks["total"] is not None, checks["operation"] == "create",
        checks["item_count"] > 0,
        all(i["supplier_part_id"] and i["quantity"] and i["unit_price"] for i in items),
    ])
    return checks


def txt_from(el, path):
    child = el.find(path)
    return child.text if child is not None else None


@app.post("/punchback")
async def punchback(request: Request):
    raw = (await request.body()).decode("utf-8")
    checks = _check_punchout_order_message(raw)
    received.append({"payload": raw, "checks": checks})
    if checks.get("all_required_present"):
        return PlainTextResponse("OK", status_code=200)
    return JSONResponse({"status": "validation_failed", "checks": checks}, status_code=400)


@app.get("/received")
async def list_received():
    return [{"index": i, "checks": r["checks"]} for i, r in enumerate(received)]


@app.get("/health")
async def health():
    return {"status": "ok", "received_count": len(received)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=9001)
