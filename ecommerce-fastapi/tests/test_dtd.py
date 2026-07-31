"""Validate generated cXML against the official cXML 1.2.014 DTD from xml.cXML.org."""

from pathlib import Path

import pytest
from lxml import etree

from app.services.checkout_service import _build_punchout_order_message
from app.services.punchout_service import _generate_setup_response

DTD_PATH = Path(__file__).resolve().parent / "fixtures" / "cXML.dtd"


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


def _validate(xml_str: str) -> list:
    dtd = etree.DTD(DTD_PATH)
    root = etree.fromstring(xml_str.encode("utf-8"))
    if dtd.validate(root):
        return []
    return list(dtd.error_log)


def test_order_message_validates_against_official_dtd():
    items = [
        _FakeCartItem(_FakeProduct("SAF-GLOVE-001", "Nitrile Safety Gloves", 249.99, "BX", "46182000"), 2),
        _FakeCartItem(_FakeProduct("TLS-DRL-001", "Cordless Drill 18V", 4999.99, "EA", "27112700"), 1),
    ]
    poom = _build_punchout_order_message(items, "dtd-test-cookie")
    errors = _validate(poom)
    assert errors == [], f"DTD errors: {[f'line {e.line}: {e.message}' for e in errors[:5]]}"


def test_setup_response_validates_against_official_dtd():
    setup = _generate_setup_response("https://kalikaindia.com/?punchout_session=abc123")
    errors = _validate(setup)
    assert errors == [], f"DTD errors: {[f'line {e.line}: {e.message}' for e in errors[:5]]}"
