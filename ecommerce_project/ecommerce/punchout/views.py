# punchout/views.py

from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login
from django.conf import settings
from django.http import HttpResponseBadRequest
from lxml import etree
import logging
from datetime import datetime
import uuid

from accounts.models import CustomUser
from cart.models import CartItem
from catalog.models import Product
from .models import PunchOutOrder, PunchOutOrderItem

logger = logging.getLogger(__name__)

# This dictionary maps XML namespaces to prefixes for easier parsing with lxml
NSMAP = {'cxml': 'cXML'}

def _parse_cxml(cxml_data):
    """Parses cXML data, handling potential encoding issues."""
    try:
        if isinstance(cxml_data, str):
            cxml_data = cxml_data.encode('utf-8')
        return etree.fromstring(cxml_data)
    except etree.XMLSyntaxError as e:
        logger.error(f"cXML Syntax Error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing cXML: {e}")
        return None

def _get_cxml_text(root, path):
    """Safely gets text content from an element found by an XPath expression."""
    # ▼▼▼ [CHANGE 2] REMOVED the 'namespaces' argument from the find() method ▼▼▼
    element = root.find(path)
    return element.text if element is not None else None

@csrf_exempt
def punchout_setup(request):
    if request.method == 'POST':
        cxml_payload = request.POST.get('cxml-urlencoded', '')
        logger.info(f"--- START INCOMING CXML PAYLOAD ---\n{cxml_payload}\n--- END INCOMING CXML PAYLOAD ---")

        if not cxml_payload:
            logger.error("PunchOut setup failed: cxml-urlencoded is missing from POST data.")
            return render(request, 'punchout/punchout_error.html', {'error': 'cXML payload was not received.'})

        root = _parse_cxml(cxml_payload)
        if root is None:
            return render(request, 'punchout/punchout_error.html', {'error': 'Failed to parse incoming cXML.'})

        # --- Credential Verification ---
        # ▼▼▼ [CHANGE 3] REMOVED the 'cxml:' prefixes from all XPath strings below ▼▼▼
        shared_secret = _get_cxml_text(root, ".//Credential/SharedSecret")
        
        if shared_secret:
            if shared_secret != settings.PUNCHOUT_SHARED_SECRET:
                logger.warning("PunchOut setup failed: Invalid SharedSecret provided.")
                return render(request, 'punchout/punchout_error.html', {'error': 'Authentication failed. Invalid credentials.'})

        # --- Identity and URL Extraction ---
        from_identity = _get_cxml_text(root, ".//Header/From/Credential/Identity")
        browser_post_url = _get_cxml_text(root, ".//PunchOutSetupRequest/BrowserFormPost/URL")
        buyer_cookie = _get_cxml_text(root, ".//PunchOutSetupRequest/BuyerCookie")

        if not all([from_identity, browser_post_url, buyer_cookie]):
            logger.error(f"PunchOut setup failed: Missing required cXML fields. Found Identity: {from_identity}, URL: {browser_post_url}, BuyerCookie: {buyer_cookie}")
            return render(request, 'punchout/punchout_error.html', {'error': 'Incomplete cXML data.'})

        # --- User Management ---
        try:
            user, created = CustomUser.objects.get_or_create(
                buyer_identifier=from_identity,
                defaults={'username': from_identity} # <-- 'role' removed
            )
            if created:
                user.set_unusable_password()
                user.save()
                logger.info(f"Created new PunchOut user: {from_identity}")
            
            login(request, user)
            logger.info(f"Logged in PunchOut user: {user.username}")

        except Exception as e:
            logger.error(f"Error during PunchOut user creation/login: {e}")
            return render(request, 'punchout/punchout_error.html', {'error': 'User management failed.'})

        # --- Store PunchOut session data ---
        request.session['is_punchout'] = True
        request.session['punchout_return_url'] = browser_post_url
        request.session['punchout_buyer_cookie'] = buyer_cookie
        logger.debug(f"PunchOut session created for user: {user.username}, return_url: {browser_post_url}")
        
        # --- Handle Automated/Edit Cart Flow ---
        item_out_elements = root.findall(".//ItemOut")
        if item_out_elements:
            logger.info("Detected 'edit' or 'inspect' mode. Populating cart from ItemOut tags.")
            
            CartItem.objects.filter(session_key=request.session.session_key).delete()
            
            for item_out in item_out_elements:
                item_id_node = item_out.find(".//ItemID/SupplierPartID")
                quantity_node = item_out.get("quantity")
                
                if item_id_node is not None and quantity_node is not None:
                    supplier_part_id = item_id_node.text
                    quantity = int(quantity_node)
                    try:
                        product = Product.objects.get(item_code=supplier_part_id)
                        CartItem.objects.create(
                            session_key=request.session.session_key,
                            product=product,
                            quantity=quantity
                        )
                    except Product.DoesNotExist:
                        logger.warning(f"Product with SupplierPartID '{supplier_part_id}' not found.")
            
            return _prepare_and_return_cart_to_ariba(request)

        return redirect('catalog:home')

    return HttpResponseBadRequest("This endpoint only supports POST requests.")


def return_cart_to_ariba(request):
    """
    Initiates the process of returning the cart to the procurement system.
    This view is typically linked from a 'Checkout' button for PunchOut users.
    """
    if not request.session.get('is_punchout'):
        logger.warning("return_cart_to_ariba accessed without a valid PunchOut session.")
        return render(request, 'punchout/punchout_error.html', {'error': 'Not a valid PunchOut session.'})

    return _prepare_and_return_cart_to_ariba(request)


def _prepare_and_return_cart_to_ariba(request):
    """
    Prepares the cXML PunchOutOrderMessage and renders the auto-submitting form.
    This is a helper function, not a direct view.
    """
    if not request.session.session_key:
        request.session.create()

    session_key = request.session.session_key
    cart_items = CartItem.objects.filter(session_key=session_key)
    
    if not cart_items:
        logger.warning("Attempted to return an empty cart to Ariba.")
        return render(request, 'punchout/punchout_error.html', {'error': 'Your shopping cart is empty.'})
        
    return_url = request.session.get('punchout_return_url')
    buyer_cookie = request.session.get('punchout_buyer_cookie')

    total_cost = sum(item.subtotal for item in cart_items)

    timestamp = datetime.utcnow().isoformat() + 'Z'
    payload_id = f"{int(datetime.utcnow().timestamp())}.{uuid.uuid4()}@yourdomain.com"
    CXML_CURRENCY = "INR"

    root = etree.Element("cXML", payloadID=payload_id, timestamp=timestamp)
    header = etree.SubElement(root, "Header")
    
    message = etree.SubElement(root, "Message")
    poom = etree.SubElement(message, "PunchOutOrderMessage")
    etree.SubElement(poom, "BuyerCookie").text = buyer_cookie
    
    poom_header = etree.SubElement(poom, "PunchOutOrderMessageHeader", operationAllowed="create")
    total_element = etree.SubElement(poom_header, "Total")
    etree.SubElement(total_element, "Money", currency=CXML_CURRENCY).text = str(round(total_cost, 2))

    for item in cart_items:
        item_in = etree.SubElement(poom, "ItemIn", quantity=str(item.quantity))
        item_id = etree.SubElement(item_in, "ItemID")
        etree.SubElement(item_id, "SupplierPartID").text = item.product.item_code
        
        item_detail = etree.SubElement(item_in, "ItemDetail")
        unit_price = etree.SubElement(item_detail, "UnitPrice")
        etree.SubElement(unit_price, "Money", currency=CXML_CURRENCY).text = str(round(item.product.price, 2))
        etree.SubElement(item_detail, "Description", **{'{http://www.w3.org/XML/1998/namespace}lang': 'en'}).text = item.product.product_title
        etree.SubElement(item_detail, "UnitOfMeasure").text = item.product.unit_of_measure or 'EA'
        if item.product.unspsc:
            etree.SubElement(item_detail, "Classification", domain="UNSPSC").text = item.product.unspsc
            
    final_cxml_payload = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode('utf-8')
    logger.info(f"Generated PunchOutOrderMessage for user {request.user}:\n{final_cxml_payload}")

    try:
        logged_in_user = request.user if request.user.is_authenticated else None

        order_log = PunchOutOrder.objects.create(
            user=logged_in_user,
            total_cost=total_cost,
            cxml_payload=final_cxml_payload
        )

        for item in cart_items:
            PunchOutOrderItem.objects.create(
                order=order_log,
                product_title=item.product.product_title,
                item_code=item.product.item_code,
                quantity=item.quantity,
                unit_price=item.product.price,
                subtotal=item.subtotal,
                unit_of_measure=item.product.unit_of_measure,
                unspsc=item.product.unspsc
            )
        logger.info(f"Successfully logged PunchOutOrder {order_log.id} for user: {logged_in_user}")
    except Exception as e:
        logger.error(f"Failed to log PunchOutOrder to database: {e}")
        return render(request, 'punchout/punchout_error.html', {'error': 'Failed to log the transaction before returning.'})

    cart_items.delete()
    request.session.flush()

    context = {
        'return_url': return_url,
        'cxml_payload': final_cxml_payload
    }
    return render(request, 'punchout/return_to_ariba.html', context)