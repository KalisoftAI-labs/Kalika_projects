import uuid
import logging
from datetime import datetime, timedelta
from urllib.parse import unquote
from lxml import etree

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.models.product import Product
from app.models.cart import CartItem
from app.models.punchout_session import PunchOutSession
from app.services.auth_service import hash_password

logger = logging.getLogger(__name__)
SESSION_TTL_HOURS = 24


async def handle_setup_request(
    db: AsyncSession,
    raw_body: str | None,
    form_body: str | None,
) -> dict:
    cxml_payload = form_body or raw_body
    if not cxml_payload:
        return {"error": "No cXML payload received", "status": 400}

    # Ariba URL-encodes the cXML in the cxml-urlencoded form field.
    # If a proxy/framework left it encoded, decode it before parsing.
    if not cxml_payload.lstrip().startswith("<"):
        decoded = unquote(cxml_payload)
        if decoded != cxml_payload and decoded.lstrip().startswith("<"):
            cxml_payload = decoded

    root = _parse_cxml(cxml_payload)
    if root is None:
        return {"error": "Failed to parse cXML", "status": 400}

    shared_secret = _get_text(root, ".//Credential/SharedSecret")
    if shared_secret:
        if shared_secret != settings.PUNCHOUT_SHARED_SECRET:
            logger.warning(f"Invalid SharedSecret: {shared_secret[:10]}...")
            return {"error": "Authentication failed", "status": 403}

    from_identity = _get_text(root, ".//Header/From/Credential/Identity")
    browser_post_url = _get_text(root, ".//PunchOutSetupRequest/BrowserFormPost/URL")
    buyer_cookie = _get_text(root, ".//PunchOutSetupRequest/BuyerCookie")

    if not all([from_identity, browser_post_url, buyer_cookie]):
        logger.error(f"Missing fields: identity={from_identity}, url={browser_post_url}, cookie={buyer_cookie}")
        return {"error": "Incomplete cXML data", "status": 400}

    user = await _get_or_create_user(db, from_identity)

    session_id = uuid.uuid4().hex
    punch_session = PunchOutSession(
        session_id=session_id,
        user_id=user.id,
        from_identity=from_identity,
        return_url=browser_post_url,
        buyer_cookie=buyer_cookie,
        shared_secret=shared_secret,
        expires_at=datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS),
    )
    db.add(punch_session)
    await db.commit()

    item_out_elements = root.findall(".//ItemOut")
    if item_out_elements:
        logger.info(f"Edit mode: {len(item_out_elements)} ItemOut elements")
        items_added = await _populate_cart_from_item_out(db, session_id, item_out_elements)
        if items_added > 0:
            return {
                "mode": "edit",
                "session_id": session_id,
                "user_id": user.id,
                "items_added": items_added,
                "return_url": browser_post_url,
                "buyer_cookie": buyer_cookie,
            }

    start_page_url = f"https://kalikaindia.com/?punchout_session={session_id}"

    return {
        "mode": "setup",
        "session_id": session_id,
        "start_page_url": start_page_url,
        "user_id": user.id,
        "cxml_response": _generate_setup_response(start_page_url),
    }


async def get_session(db: AsyncSession, session_id: str) -> PunchOutSession | None:
    result = await db.execute(
        select(PunchOutSession).where(
            PunchOutSession.session_id == session_id,
            PunchOutSession.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def _get_or_create_user(db: AsyncSession, buyer_identifier: str) -> User:
    result = await db.execute(
        select(User).where(User.buyer_identifier == buyer_identifier)
    )
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            username=buyer_identifier,
            email=f"{buyer_identifier.replace('@', '_')}@punchout.kalikaindia.com",
            password=hash_password(uuid.uuid4().hex),
            role="PunchOut",
            buyer_identifier=buyer_identifier,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        logger.info(f"Created PunchOut user: {buyer_identifier}")
    return user


async def _populate_cart_from_item_out(
    db: AsyncSession, session_id: str, item_out_elements: list
) -> int:
    added = 0
    await db.execute(
        __import__("sqlalchemy").delete(CartItem).where(CartItem.session_token == session_id)
    )
    for item_out in item_out_elements:
        supplier_part_id = _get_text(item_out, ".//ItemID/SupplierPartID")
        quantity_attr = item_out.get("quantity")
        if not supplier_part_id or not quantity_attr:
            continue
        try:
            result = await db.execute(
                select(Product).where(Product.item_code == supplier_part_id)
            )
            product = result.scalar_one_or_none()
            if product:
                db.add(CartItem(
                    session_token=session_id,
                    product_id=product.item_id,
                    quantity=int(quantity_attr),
                ))
                added += 1
            else:
                logger.warning(f"Product not found by item_code: {supplier_part_id}")
        except Exception as e:
            logger.error(f"Error adding product {supplier_part_id}: {e}")
    await db.commit()
    return added


def _parse_cxml(data: str) -> etree._Element | None:
    try:
        if isinstance(data, str):
            data = data.encode("utf-8")
        return etree.fromstring(data)
    except Exception as e:
        logger.error(f"cXML parse error: {e}")
        return None


def _get_text(element: etree._Element | etree._ElementTree, path: str) -> str | None:
    el = element.find(path)
    return el.text if el is not None else None


def _generate_setup_response(start_page_url: str) -> str:
    now = datetime.utcnow()
    payload_id = f"{int(datetime.utcnow().timestamp())}.{uuid.uuid4()}@kalikaindia.com"

    root = etree.Element("cXML", payloadID=payload_id, timestamp=now.isoformat() + "Z", version="1.2.014")
    resp = etree.SubElement(root, "Response")
    etree.SubElement(resp, "Status", code="200", text="success")
    psr = etree.SubElement(resp, "PunchOutSetupResponse")
    sp = etree.SubElement(psr, "StartPage")
    etree.SubElement(sp, "URL").text = start_page_url

    doctype = '<!DOCTYPE cXML SYSTEM "http://xml.cXML.org/schemas/cXML/1.2.014/cXML.dtd">'
    return etree.tostring(
        root, pretty_print=True, xml_declaration=True, encoding="UTF-8", doctype=doctype
    ).decode("utf-8")
