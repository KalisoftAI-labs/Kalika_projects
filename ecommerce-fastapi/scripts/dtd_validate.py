"""Verify our generated cXML validates against the official cXML 1.2.014 DTD."""

from pathlib import Path
from lxml import etree
from app.services.checkout_service import _build_punchout_order_message
from app.services.punchout_service import _generate_setup_response

DTD_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "cXML.dtd"


class _FakeProduct:
    def __init__(self, code, title, price, uom, unspsc):
        self.item_code = code
        self.product_title = title
        self.price = price
        self.unit_of_measure = uom
        self.unspsc = unspsc


class _FakeCartItem:
    def __init__(self, product, qty):
        self.product = product
        self.quantity = qty


def validate_against_dtd(xml_str: str) -> list[str]:
    dtd = etree.DTD(DTD_PATH)
    root = etree.fromstring(xml_str.encode("utf-8"))
    if dtd.validate(root):
        return []
    return list(dtd.error_log)


if __name__ == "__main__":
    items = [
        _FakeCartItem(_FakeProduct("SAF-GLOVE-001", "Nitrile Safety Gloves", 249.99, "BX", "46182000"), 2),
        _FakeCartItem(_FakeProduct("TLS-DRL-001", "Cordless Drill 18V", 4999.99, "EA", "27112700"), 1),
    ]
    poom = _build_punchout_order_message(items, "test-buyer-cookie")

    errors = validate_against_dtd(poom)
    print(f"PunchOutOrderMessage DTD validation: {'PASS' if not errors else 'FAIL'}")
    for e in errors[:10]:
        print(f"  line {e.line}: {e.message}")

    setup = _generate_setup_response("https://kalikaindia.com/?punchout_session=abc123")
    errors2 = validate_against_dtd(setup)
    print(f"PunchOutSetupResponse DTD validation: {'PASS' if not errors2 else 'FAIL'}")
    for e in errors2[:10]:
        print(f"  line {e.line}: {e.message}")
