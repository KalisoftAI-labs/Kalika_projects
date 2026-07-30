import uuid
import logging
from datetime import datetime
from decimal import Decimal
from lxml import etree
import httpx

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.cart import CartItem
from app.models.order import PunchOutOrder, PunchOutOrderItem
from app.services.cart_service import clear_cart
from app.services.s3_service import enrich_product_with_s3_url

logger = logging.getLogger(__name__)


async def checkout(
    db: AsyncSession,
    user_id: int | None = None,
    session_token: str | None = None,
    punchout_return_url: str | None = None,
    buyer_cookie: str | None = None,
) -> dict:
    if not user_id and not session_token:
        return {"success": False, "message": "Cart is empty"}

    if user_id:
        result = await db.execute(
            select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.created_at)
        )
    else:
        result = await db.execute(
            select(CartItem).where(CartItem.session_token == session_token).order_by(CartItem.created_at)
        )
    cart_items = list(result.scalars().all())

    if not cart_items:
        return {"success": False, "message": "Cart is empty"}

    total_cost = sum(ci.quantity * ci.product.price for ci in cart_items)
    cxml_payload = _build_punchout_order_message(cart_items, buyer_cookie or "unknown")

    order = PunchOutOrder(
        user_id=user_id,
        session_token=session_token if not user_id else None,
        total_cost=total_cost,
        cxml_payload=cxml_payload,
        buyer_cookie=buyer_cookie,
        return_url=punchout_return_url,
    )
    db.add(order)
    await db.flush()

    for ci in cart_items:
        item = PunchOutOrderItem(
            order_id=order.id,
            product_title=ci.product.product_title,
            item_code=ci.product.item_code,
            quantity=ci.quantity,
            unit_price=ci.product.price,
            subtotal=ci.quantity * ci.product.price,
            unit_of_measure=ci.product.unit_of_measure or "EA",
            unspsc=ci.product.unspsc,
        )
        db.add(item)

    await db.commit()
    await db.refresh(order)

    if punchout_return_url:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    punchout_return_url,
                    content=cxml_payload,
                    headers={"Content-Type": "text/xml"},
                    timeout=30,
                )
                if resp.status_code != 200:
                    logger.error(f"Ariba returned {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Failed to POST cXML to Ariba: {e}")

    await clear_cart(db, user_id, session_token)

    return {
        "success": True,
        "order": {
            "id": order.id,
            "total_cost": float(total_cost),
            "currency": "INR",
            "status": "completed",
            "buyer_cookie": buyer_cookie,
            "items": [
                {
                    "product_title": ci.product.product_title,
                    "item_code": ci.product.item_code,
                    "quantity": ci.quantity,
                    "unit_price": float(ci.product.price),
                    "subtotal": float(ci.quantity * ci.product.price),
                    "unit_of_measure": ci.product.unit_of_measure or "EA",
                    "unspsc": ci.product.unspsc,
                }
                for ci in cart_items
            ],
            "created_at": order.created_at,
        },
        "cxml_payload": cxml_payload,
        "message": "Order completed successfully",
    }


def _build_punchout_order_message(cart_items: list, buyer_cookie: str) -> str:
    total_cost = sum(ci.quantity * ci.product.price for ci in cart_items)
    now = datetime.utcnow()
    timestamp = now.isoformat() + "Z"
    payload_id = f"{int(now.timestamp())}.{uuid.uuid4()}@kalikaindia.com"

    root = etree.Element("cXML", payloadID=payload_id, timestamp=timestamp, version="1.2.014")

    header = etree.SubElement(root, "Header")
    from_elem = etree.SubElement(header, "From")
    from_cred = etree.SubElement(from_elem, "Credential", domain="NetworkID")
    etree.SubElement(from_cred, "Identity").text = settings.PUNCHOUT_ANID

    to_elem = etree.SubElement(header, "To")
    to_cred = etree.SubElement(to_elem, "Credential", domain="NetworkID")
    etree.SubElement(to_cred, "Identity").text = settings.PUNCHOUT_ANID

    sender_elem = etree.SubElement(header, "Sender")
    sender_cred = etree.SubElement(sender_elem, "Credential", domain="NetworkID")
    etree.SubElement(sender_cred, "Identity").text = settings.PUNCHOUT_SUPPLIER_DUNS or "kalikaindia.com"
    if settings.PUNCHOUT_SHARED_SECRET:
        etree.SubElement(sender_cred, "SharedSecret").text = settings.PUNCHOUT_SHARED_SECRET
    etree.SubElement(sender_elem, "UserAgent").text = "Kalika India PunchOut 1.0"

    message = etree.SubElement(root, "Message")
    poom = etree.SubElement(message, "PunchOutOrderMessage")
    etree.SubElement(poom, "BuyerCookie").text = buyer_cookie

    poom_header = etree.SubElement(poom, "PunchOutOrderMessageHeader", operationAllowed="create")
    total_el = etree.SubElement(poom_header, "Total")
    etree.SubElement(total_el, "Money", currency="INR").text = str(round(float(total_cost), 2))

    for ci in cart_items:
        item_in = etree.SubElement(poom, "ItemIn", quantity=str(ci.quantity))
        item_id_el = etree.SubElement(item_in, "ItemID")
        etree.SubElement(item_id_el, "SupplierPartID").text = ci.product.item_code

        item_detail = etree.SubElement(item_in, "ItemDetail")
        unit_price = etree.SubElement(item_detail, "UnitPrice")
        etree.SubElement(unit_price, "Money", currency="INR").text = str(round(float(ci.product.price), 2))
        etree.SubElement(item_detail, "Description", **{"{http://www.w3.org/XML/1998/namespace}lang": "en"}).text = ci.product.product_title
        etree.SubElement(item_detail, "UnitOfMeasure").text = ci.product.unit_of_measure or "EA"
        if ci.product.unspsc:
            etree.SubElement(item_detail, "Classification", domain="UNSPSC").text = ci.product.unspsc

    doctype = '<!DOCTYPE cXML SYSTEM "http://xml.cXML.org/schemas/cXML/1.2.014/cXML.dtd">'
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8", doctype=doctype).decode("utf-8")
