# punchout/views.py

from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login
from django.conf import settings
from django.utils import timezone
from lxml import etree as ET
import logging

from accounts.models import CustomUser
from cart.models import CartItem
from catalog.models import Product
from .models import PunchOutOrder, PunchOutOrderItem # PunchOutOrderItem ko import karein

logger = logging.getLogger(__name__)

# punchout_setup function (Isme koi badlaav nahi hai)
@csrf_exempt
def punchout_setup(request: HttpRequest) -> HttpResponse:
    """
    Handles the initial PunchOutSetupRequest from the procurement system (e.g., Ariba).
    - Validates the request and shared secret (if provided).
    - Authenticates or creates a user for the PunchOut session.
    - Handles two flows:
        1. Automated Flow: If the cXML contains item details, it adds them to the cart
           and immediately returns the cart to the procurement system.
        2. Manual Flow: If no item details are present, it redirects the user to the
           catalog to start shopping.
    """
    if request.method != 'POST':
        logger.warning("PunchOut setup accessed with a non-POST method.")
        return render(request, 'punchout/punchout_error.html', {'error': 'Invalid request method.'})

    try:
        cxml_payload = request.POST.get('cxml-urlencoded', request.body.decode('utf-8'))
        if not cxml_payload:
            raise ValueError("cXML payload is empty.")
            
        logger.debug(f"Received cXML Payload:\n{cxml_payload}")
        
        parser = ET.XMLParser(resolve_entities=False)
        root = ET.fromstring(cxml_payload.encode('utf-8'), parser)
        
        header = root.find('.//Header')
        from_identity = header.find('.//From/Credential/Identity').text
        sender_identity = header.find('.//Sender/Credential/Identity').text
        shared_secret_element = header.find('.//Sender/Credential/SharedSecret')
        
        if shared_secret_element is not None:
            cxml_secret = shared_secret_element.text
            if not settings.PUNCHOUT_SHARED_SECRET:
                logger.error("cXML contains a SharedSecret, but PUNCHOUT_SHARED_SECRET is not set in Django settings.")
                return render(request, 'punchout/punchout_error.html', {'error': 'Server configuration error: Shared secret not set.'})

            if cxml_secret != settings.PUNCHOUT_SHARED_SECRET:
                logger.error(f"Shared secret mismatch. cXML secret: '{cxml_secret}'")
                return render(request, 'punchout/punchout_error.html', {'error': 'Authentication failed: Shared secret mismatch.'})
            logger.info("Shared secret authenticated successfully.")
        
        else:
            logger.info("No shared secret found in cXML. Proceeding with authentication.")
            
        user, created = CustomUser.objects.get_or_create(
            username=from_identity,
            defaults={
                'email': f'{from_identity}@punchout.user',
                'role': 'PunchOut',
                'buyer_identifier': sender_identity
            }
        )
        if created:
            user.set_unusable_password()
            user.save()
            logger.info(f"Created new PunchOut user: {from_identity}")
        
        login(request, user)
        logger.info(f"User '{from_identity}' logged in for PunchOut session.")

        request.session.flush()
        request.session.create() # Create a new session key after flushing
        request.session['is_punchout'] = True
        
        browser_form_post_url = root.find('.//BrowserFormPost/URL').text
        request.session['punchout_return_url'] = browser_form_post_url
        logger.info(f"PunchOut return URL set to: {browser_form_post_url}")
        
        item_in_elements = root.findall('.//ItemIn')
        
        if item_in_elements:
            logger.info(f"Automated flow detected with {len(item_in_elements)} items.")
            CartItem.objects.filter(session_key=request.session.session_key).delete()
            
            for item in item_in_elements:
                item_id_node = item.find('ItemID/SupplierPartID')
                quantity_node = item.get('quantity')
                
                if item_id_node is not None and quantity_node:
                    item_code = item_id_node.text
                    quantity = int(quantity_node)
                    
                    try:
                        product = Product.objects.get(item_code=item_code)
                        CartItem.objects.create(
                            product=product,
                            quantity=quantity,
                            session_key=request.session.session_key
                        )
                        logger.info(f"Added product {item_code} (Quantity: {quantity}) to cart automatically.")
                    except Product.DoesNotExist:
                        logger.warning(f"Product with item_code '{item_code}' not found in database. Skipping.")
            
            return _prepare_and_return_cart_to_ariba(request)
            
        else:
            logger.info("Manual flow detected. Redirecting to catalog home.")
            return redirect('catalog:home')

    except Exception as e:
        logger.exception("An error occurred during PunchOut setup.")
        return render(request, 'punchout/punchout_error.html', {'error': str(e)})

# return_cart_to_ariba function (Isme koi badlaav nahi hai)
def return_cart_to_ariba(request: HttpRequest) -> HttpResponse:
    """
    View function called when the user clicks 'Punchout Checkout' in the cart.
    This is the trigger for the manual shopping flow.
    """
    if not request.session.get('is_punchout'):
        return render(request, 'punchout/punchout_error.html', {'error': 'Not a valid PunchOut session.'})
    
    return _prepare_and_return_cart_to_ariba(request)


def _prepare_and_return_cart_to_ariba(request: HttpRequest) -> HttpResponse:
    """
    Helper function to gather cart items, generate the PunchOutOrderMessage cXML,
    log the transaction in structured tables, and render the form that posts back
    to the procurement system.
    """
    session_key = request.session.session_key
    cart_items = CartItem.objects.filter(session_key=session_key).select_related('product')
    
    if not cart_items:
        return render(request, 'punchout/punchout_error.html', {'error': 'Your cart is empty.'})

    total_cost = sum(item.subtotal for item in cart_items)
    
    # --- cXML Generation (No changes here) ---
    cxml = ET.Element('cXML', {
        'payloadID': f"{timezone.now().timestamp()}.{request.user.username}",
        'timestamp': timezone.now().isoformat()
    })
    header = ET.SubElement(cxml, 'Header')
    ET.SubElement(header, 'From').text = 'Your Company Name'
    ET.SubElement(header, 'To').text = request.user.buyer_identifier if hasattr(request.user, 'buyer_identifier') else 'UnknownBuyer'
    sender = ET.SubElement(header, 'Sender')
    sender_credential = ET.SubElement(sender, 'Credential', {'domain': 'NetworkID'})
    ET.SubElement(sender_credential, 'Identity').text = 'Your Network ID'
    message = ET.SubElement(cxml, 'Message')
    punchout_order_message = ET.SubElement(message, 'PunchOutOrderMessage')
    ET.SubElement(punchout_order_message, 'BuyerCookie').text = "UserSessionCookie123"
    pom_header = ET.SubElement(punchout_order_message, 'PunchOutOrderMessageHeader', {'operationAllowed': 'edit'})
    ET.SubElement(pom_header, 'Total', {'currency': 'INR'}).text = str(total_cost)

    for item in cart_items:
        item_in = ET.SubElement(punchout_order_message, 'ItemIn', {'quantity': str(item.quantity)})
        item_id = ET.SubElement(item_in, 'ItemID')
        ET.SubElement(item_id, 'SupplierPartID').text = item.product.item_code
        item_detail = ET.SubElement(item_in, 'ItemDetail')
        ET.SubElement(item_detail, 'UnitPrice', {'currency': 'INR'}).text = str(item.product.price)
        ET.SubElement(item_detail, 'Description', {'xml:lang': 'en'}).text = item.product.product_title
        ET.SubElement(item_detail, 'UnitOfMeasure').text = item.product.unit_of_measure or 'EA'
        classification = ET.SubElement(item_detail, 'Classification', {'domain': 'UNSPSC'})
        classification.text = item.product.unspsc or '00000000'
    
    final_cxml_payload = ET.tostring(cxml, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode('utf-8')
    logger.debug(f"Returning cXML to Ariba:\n{final_cxml_payload}")

    # --- Structured Data Logging (Naya Logic Yahan Hai) ---
    # 1. Pehle PunchOutOrder record banayein
    order_log = PunchOutOrder.objects.create(
        user=request.user,
        total_cost=total_cost,
        cxml_payload=final_cxml_payload # Raw cXML abhi bhi save ho raha hai
    )
    logger.info(f"Created PunchOutOrder log with ID: {order_log.id}")

    # 2. Phir har cart item ke liye PunchOutOrderItem record banayein
    for item in cart_items:
        PunchOutOrderItem.objects.create(
            order=order_log,
            product_title=item.product.product_title,
            item_code=item.product.item_code,
            quantity=item.quantity,
            unit_price=item.product.price,
            subtotal=item.subtotal,
            unit_of_measure=item.product.unit_of_measure or 'EA',
            unspsc=item.product.unspsc or '00000000'
        )
    logger.info(f"Logged {len(cart_items)} items for PunchOutOrder ID: {order_log.id}")
    
    # --- Session Cleanup and Return to Ariba ---
    return_url = request.session.get('punchout_return_url', '#')
    request.session.flush()
    
    context = {
        'return_url': return_url,
        'cxml_payload': final_cxml_payload
    }
    return render(request, 'punchout/return_to_ariba.html', context)