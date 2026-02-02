# punchout/views.py

from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login
from django.conf import settings
from django.http import HttpResponseBadRequest, HttpResponseRedirect, HttpResponse
from lxml import etree
import logging
from datetime import datetime
import uuid

from accounts.models import CustomUser
from cart.models import CartItem
from catalog.models import Product
from .models import PunchOutOrder, PunchOutOrderItem, PunchOutSession

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

def _generate_punchout_setup_response(start_page_url):
    """
    Generates a cXML PunchOutSetupResponse with proper DOCTYPE and structure.
    This is sent back to SAP Ariba after receiving PunchOutSetupRequest.
    """
    # SAP Ariba requires timezone offset format: 2011-11-21T12:59:09-07:00 (not 'Z')
    from datetime import timezone, timedelta
    # Use local timezone offset (or UTC with +00:00 instead of Z)
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
    payload_id = f"{int(datetime.utcnow().timestamp())}.{uuid.uuid4()}@kalikaindia.com"
    
    # Create root element with proper attributes
    root = etree.Element(
        "cXML",
        payloadID=payload_id,
        timestamp=timestamp,
        version="1.2.014"
    )
    
    # Add Response element
    response = etree.SubElement(root, "Response")
    status = etree.SubElement(response, "Status", code="200", text="success")
    
    # Add PunchOutSetupResponse
    punchout_setup_response = etree.SubElement(response, "PunchOutSetupResponse")
    start_page = etree.SubElement(punchout_setup_response, "StartPage")
    url_element = etree.SubElement(start_page, "URL")
    url_element.text = start_page_url
    
    # Generate XML with DOCTYPE declaration
    doctype = '<!DOCTYPE cXML SYSTEM "http://xml.cXML.org/schemas/cXML/1.2.014/cXML.dtd">'
    xml_string = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding='UTF-8',
        doctype=doctype
    ).decode('utf-8')
    
    return xml_string

def _generate_cxml_error_response(status_code, status_text):
    """
    Generates a cXML error response for PunchOut failures.
    This ensures ALL responses are cXML-compliant, even errors.
    """
    from datetime import timezone
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
    payload_id = f"{int(datetime.utcnow().timestamp())}.{uuid.uuid4()}@kalikaindia.com"
    
    root = etree.Element(
        "cXML",
        payloadID=payload_id,
        timestamp=timestamp
    )
    
    response = etree.SubElement(root, "Response")
    status = etree.SubElement(response, "Status", code=str(status_code), text=status_text)
    
    doctype = '<!DOCTYPE cXML SYSTEM "http://xml.cXML.org/schemas/cXML/1.2.014/cXML.dtd">'
    xml_string = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding='UTF-8',
        doctype=doctype
    ).decode('utf-8')
    
    return xml_string

@csrf_exempt
def punchout_setup(request):
    if request.method == 'POST':
        cxml_payload = request.POST.get('cxml-urlencoded', '')
        
        if not cxml_payload:
            # Try reading from request body directly
            cxml_payload = request.body.decode('utf-8')
            logger.info("cxml-urlencoded not found in POST, using request.body")
        
        logger.info(f"--- START INCOMING CXML PAYLOAD ---\n{cxml_payload}\n--- END INCOMING CXML PAYLOAD ---")

        if not cxml_payload:
            logger.error("PunchOut setup failed: No cXML payload received (neither in POST data nor body).")
            error_cxml = _generate_cxml_error_response(400, "No cXML payload received")
            return HttpResponse(error_cxml, content_type='text/xml; charset=utf-8', status=400)

        root = _parse_cxml(cxml_payload)
        if root is None:
            error_cxml = _generate_cxml_error_response(400, "Failed to parse incoming cXML")
            return HttpResponse(error_cxml, content_type='text/xml; charset=utf-8', status=400)

        # --- Credential Verification ---
        # ▼▼▼ [CHANGE 3] REMOVED the 'cxml:' prefixes from all XPath strings below ▼▼▼
        shared_secret = _get_cxml_text(root, ".//Credential/SharedSecret")
        
        if shared_secret:
            if shared_secret != settings.PUNCHOUT_SHARED_SECRET:
                logger.warning("PunchOut setup failed: Invalid SharedSecret provided.")
                error_cxml = _generate_cxml_error_response(401, "Authentication failed. Invalid credentials")
                return HttpResponse(error_cxml, content_type='text/xml; charset=utf-8', status=401)

        # --- Identity and URL Extraction ---
        from_identity = _get_cxml_text(root, ".//Header/From/Credential/Identity")
        to_identity = _get_cxml_text(root, ".//Header/To/Credential/Identity")
        browser_post_url = _get_cxml_text(root, ".//PunchOutSetupRequest/BrowserFormPost/URL")
        buyer_cookie = _get_cxml_text(root, ".//PunchOutSetupRequest/BuyerCookie")

        # Validate To Identity matches our NetworkID
        if to_identity and to_identity != settings.PUNCHOUT_ANID:
            logger.warning(f"PunchOut setup: To Identity mismatch. Expected {settings.PUNCHOUT_ANID}, got {to_identity}")
            # Note: Not failing here as some buyers might not send To/Identity
        
        if not all([from_identity, browser_post_url, buyer_cookie]):
            logger.error(f"PunchOut setup failed: Missing required cXML fields. Found Identity: {from_identity}, URL: {browser_post_url}, BuyerCookie: {buyer_cookie}")
            error_cxml = _generate_cxml_error_response(400, "Incomplete cXML data. Missing required fields")
            return HttpResponse(error_cxml, content_type='text/xml; charset=utf-8', status=400)

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
            error_cxml = _generate_cxml_error_response(500, "Internal error during user management")
            return HttpResponse(error_cxml, content_type='text/xml; charset=utf-8', status=500)

        # --- Store PunchOut session data ---
        # Store in both session (if it works) and database (fallback for iframe issues)
        request.session['is_punchout'] = True
        request.session['punchout_return_url'] = browser_post_url
        request.session['punchout_buyer_cookie'] = buyer_cookie
        request.session['punchout_from_identity'] = from_identity
        
        # Ensure session is created before using session_key
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key
        
        # Store in database for iframe compatibility
        PunchOutSession.objects.update_or_create(
            session_key=session_key,
            defaults={
                'return_url': browser_post_url,
                'buyer_cookie': buyer_cookie,
                'from_identity': from_identity,
            }
        )
        logger.debug(f"PunchOut session created in DB for session_key: {session_key}, return_url: {browser_post_url}")
        
        # --- Handle Edit/Inspect Mode - Pre-populate Cart ---
        operation = root.find(".//PunchOutSetupRequest").get("operation", "create")
        item_out_elements = root.findall(".//ItemOut")
        
        if operation in ("edit", "inspect") and item_out_elements:
            logger.info(f"Detected '{operation}' mode. Found {len(item_out_elements)} ItemOut elements. Pre-populating cart...")
            
            logger.info(f"Using session_key: {session_key}")
            
            # Clear existing cart items for this session
            CartItem.objects.filter(session_key=session_key).delete()
            
            items_added = 0
            items_not_found = []
            
            for item_out in item_out_elements:
                item_id_node = item_out.find(".//ItemID/SupplierPartID")
                quantity_attr = item_out.get("quantity")
                
                if item_id_node is not None and quantity_attr is not None:
                    supplier_part_id = item_id_node.text.strip()
                    quantity = int(quantity_attr)
                    logger.info(f"Processing ItemOut: {supplier_part_id} x {quantity}")
                    
                    try:
                        product = Product.objects.get(item_code=supplier_part_id)
                        cart_item, created = CartItem.objects.update_or_create(
                            session_key=session_key,
                            product=product,
                            defaults={'quantity': quantity}
                        )
                        items_added += 1
                        logger.info(f"✓ Added to cart: {product.product_title} x {quantity}")
                    except Product.DoesNotExist:
                        items_not_found.append(supplier_part_id)
                        logger.warning(f"✗ Product with SupplierPartID '{supplier_part_id}' not found in database.")
                    except Exception as e:
                        logger.error(f"✗ Error adding product {supplier_part_id} to cart: {e}")
            
            logger.info(f"{operation.capitalize()} mode: Pre-populated cart with {items_added}/{len(item_out_elements)} items.")
            if items_not_found:
                logger.warning(f"Items not found in catalog: {', '.join(items_not_found)}")
            
            # IMPORTANT: In edit mode, redirect user to catalog so they can modify cart
            # Do NOT return to Ariba immediately - user needs to browse and click "PunchOut Checkout"
            session_id = request.session.session_key
            start_page_url = f"https://kalikaindia.com/cart/?punchout_session={session_id}"
            response_cxml = _generate_punchout_setup_response(start_page_url)
            logger.info(f"Redirecting to cart view for {operation} mode")
            return HttpResponse(response_cxml, content_type='application/xml')

        # --- Generate and return PunchOutSetupResponse for Create mode ---
        session_id = request.session.session_key
        start_page_url = f"https://kalikaindia.com/?punchout_session={session_id}"
        
        setup_response_xml = _generate_punchout_setup_response(start_page_url)
        logger.info(f"Sending PunchOutSetupResponse:\n{setup_response_xml}")
        
        return HttpResponse(setup_response_xml, content_type='text/xml; charset=utf-8')

    # Non-POST requests (e.g., browser GET) should still return cXML error
    # This makes the endpoint SAP Ariba compliant even for invalid requests
    error_cxml = _generate_cxml_error_response(405, "Can not parse request cXML!")
    logger.warning(f"PunchOut setup received non-POST request from {request.META.get('REMOTE_ADDR')}")
    return HttpResponse(error_cxml, content_type='text/xml; charset=utf-8', status=405)


def return_cart_to_ariba(request):
    """
    Initiates the process of returning the cart to the procurement system.
    This view is typically linked from a 'Checkout' button for PunchOut users.
    """
    # Check for punchout_session parameter (used in iframe contexts where cookies don't work)
    # Check both POST and GET as the form sends via POST
    punchout_session_key = request.POST.get('punchout_session') or request.GET.get('punchout_session')
    
    # If no parameter, try to get from session
    if not punchout_session_key:
        if request.session.get('is_punchout'):
            punchout_session_key = request.session.session_key
        else:
            logger.warning("return_cart_to_ariba accessed without a valid PunchOut session.")
            return render(request, 'punchout/punchout_error.html', {'error': 'Not a valid PunchOut session.'})
    
    logger.info(f"return_cart_to_ariba - Using session_key: {punchout_session_key}")
        
    return _prepare_and_return_cart_to_ariba(request, session_key=punchout_session_key)


def _prepare_and_return_cart_to_ariba(request, session_key=None):
    """
    Prepares the cXML PunchOutOrderMessage and renders the auto-submitting form.
    This is a helper function, not a direct view.
    
    Args:
        request: The HTTP request object
        session_key: Optional session key to use instead of request.session.session_key
                     (needed for iframe contexts where session cookies don't work)
    """
    # Use provided session_key or fall back to request session
    if not session_key:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
    
    logger.info(f"_prepare_and_return_cart_to_ariba - Using session_key: {session_key}")

    cart_items = CartItem.objects.filter(session_key=session_key)
    
    if not cart_items:
        logger.warning("Attempted to return an empty cart to Ariba.")
        return render(request, 'punchout/punchout_error.html', {'error': 'Your shopping cart is empty.'})
    
    # Try to get PunchOut session data from database first (for iframe compatibility)
    try:
        punchout_session = PunchOutSession.objects.get(session_key=session_key)
        return_url = punchout_session.return_url
        buyer_cookie = punchout_session.buyer_cookie
        from_identity = punchout_session.from_identity
        logger.info(f"Retrieved PunchOut session from database for session_key: {session_key}")
    except PunchOutSession.DoesNotExist:
        # Fallback to session (if cookies work)
        return_url = request.session.get('punchout_return_url')
        buyer_cookie = request.session.get('punchout_buyer_cookie')
        from_identity = request.session.get('punchout_from_identity', 'UNKNOWN')
        logger.info(f"Retrieved PunchOut session from cookies for session_key: {session_key}")
    
    if not return_url or not buyer_cookie:
        logger.error(f"Missing PunchOut return URL or buyer cookie for session: {session_key}")
        return render(request, 'punchout/punchout_error.html', {
            'error': 'PunchOut session data not found. Please restart the PunchOut process.'
        })

    total_cost = sum(item.subtotal for item in cart_items)

    # SAP Ariba requires timezone offset format: 2011-11-21T12:59:09-07:00 (not 'Z')
    from datetime import timezone
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
    payload_id = f"{int(datetime.utcnow().timestamp())}.{uuid.uuid4()}@kalikaindia.com"
    CXML_CURRENCY = "INR"
    
    # Create cXML root with proper attributes
    root = etree.Element(
        "cXML",
        payloadID=payload_id,
        timestamp=timestamp,
        version="1.2.014"
    )
    
    # Build Header with From, To, and Sender
    header = etree.SubElement(root, "Header")
    
    # From - The buyer (SAP Ariba)
    from_elem = etree.SubElement(header, "From")
    from_cred = etree.SubElement(from_elem, "Credential", domain="NetworkID")
    etree.SubElement(from_cred, "Identity").text = from_identity
    
    # To - The supplier (Kalika India) per SAP Ariba documentation
    to_elem = etree.SubElement(header, "To")
    to_cred = etree.SubElement(to_elem, "Credential", domain="NetworkID")
    etree.SubElement(to_cred, "Identity").text = settings.PUNCHOUT_ANID
    
    # Sender - The supplier (your system)
    sender_elem = etree.SubElement(header, "Sender")
    sender_cred = etree.SubElement(sender_elem, "Credential", domain="NetworkID")
    etree.SubElement(sender_cred, "Identity").text = settings.PUNCHOUT_ANID
    if settings.PUNCHOUT_SHARED_SECRET:
        etree.SubElement(sender_cred, "SharedSecret").text = settings.PUNCHOUT_SHARED_SECRET
    etree.SubElement(sender_elem, "UserAgent").text = "Kalika India PunchOut 1.0"
    
    # Message container
    message = etree.SubElement(root, "Message")
    poom = etree.SubElement(message, "PunchOutOrderMessage")
    etree.SubElement(poom, "BuyerCookie").text = buyer_cookie
    
    poom_header = etree.SubElement(poom, "PunchOutOrderMessageHeader", operationAllowed="edit")
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
    
    # Generate XML with DOCTYPE
    doctype = '<!DOCTYPE cXML SYSTEM "http://xml.cXML.org/schemas/cXML/1.2.014/cXML.dtd">'
    final_cxml_payload = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding='UTF-8',
        doctype=doctype
    ).decode('utf-8')
    
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
                unit_of_measure=item.product.unit_of_measure or 'EA',
                unspsc=item.product.unspsc or ''
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