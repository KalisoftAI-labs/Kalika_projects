# cart/views.py
from django.shortcuts import render, redirect, get_object_or_404
from .models import CartItem
from catalog.models import Product
from punchout.models import PunchOutOrder
from django.http import JsonResponse, HttpResponse
import json
import logging
from catalog.views import get_s3_presigned_url
from django.conf import settings
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
import uuid

logger = logging.getLogger(__name__)

def add_to_cart(request, item_id):
    """Adds a product to the cart. Supports AJAX and redirects."""
    product = get_object_or_404(Product, item_id=item_id)
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key

    cart_item, created = CartItem.objects.get_or_create(
        session_key=session_key,
        product=product,
        defaults={'quantity': 1}
    )

    if not created:
        cart_item.quantity += 1
        cart_item.save()

    logger.info(f"Item {item_id} added to cart for session_key: {session_key}")

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Product added to cart successfully.'})

    return redirect('cart:view_cart')

# cart/views.py (Corrected)

def view_cart(request):
    """Display the cart with S3 image URLs."""
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key
    cart_items = CartItem.objects.filter(session_key=session_key)
    total = sum(item.subtotal for item in cart_items) # You can even use the property here to make it cleaner

    for item in cart_items:
        # The problematic line has been removed.
        # The template can now access item.subtotal directly from the model property.
        item.product.s3_image_url = get_s3_presigned_url(settings.AWS_S3_BUCKET_NAME, item.product.large_image) if item.product.large_image else None
        logger.debug(f"Cart item {item.id}: s3_image_url = {item.product.s3_image_url}")
    
    return render(request, 'cart/view_cart.html', {
        'cart_items': cart_items,
        'total': total
    })

def remove_from_cart(request, item_id):
    """Remove an item from the cart."""
    if request.method == 'POST':
        try:
            cart_item = CartItem.objects.get(id=item_id, session_key=request.session.session_key)
            cart_item.delete()
            messages.success(request, 'Item removed from cart.')
        except CartItem.DoesNotExist:
            logger.warning(f"CartItem id {item_id} not found for session {request.session.session_key}")
            messages.error(request, 'Item not found in your cart.')
        return redirect('cart:view_cart')
    return redirect('cart:view_cart')

def update_cart_quantity(request):
    """Update cart item quantity via AJAX."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            quantity = data.get('quantity')

            cart_item = CartItem.objects.get(id=item_id, session_key=request.session.session_key)

            if quantity > 0:
                cart_item.quantity = quantity
                cart_item.save()
                logger.info(f"Updated quantity for CartItem {item_id} to {quantity}.")
                updated_cart_items = CartItem.objects.filter(session_key=request.session.session_key)
                new_total = sum(item.quantity * item.product.price for item in updated_cart_items)
                return JsonResponse({
                    'success': True,
                    'new_quantity': quantity,
                    'new_subtotal': cart_item.quantity * cart_item.product.price,
                    'new_total': new_total
                })
            else:
                cart_item.delete()
                logger.info(f"Removed CartItem {item_id} as quantity was 0 or less.")
                updated_cart_items = CartItem.objects.filter(session_key=request.session.session_key)
                new_total = sum(item.quantity * item.product.price for item in updated_cart_items)
                return JsonResponse({
                    'success': True,
                    'removed': True,
                    'item_id': item_id,
                    'new_total': new_total
                })
        except CartItem.DoesNotExist:
            logger.error(f"CartItem id {item_id} not found for session {request.session.session_key}.")
            return JsonResponse({'success': False, 'error': 'Item not found'}, status=404)
        except json.JSONDecodeError:
            logger.error("JSON decode error in update_cart_quantity.")
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

@csrf_exempt
def checkout(request):
    """Handle checkout, processing both PunchOut and non-PunchOut orders."""
    if not request.session.session_key:
        logger.info("No session key, creating a new one.")
        request.session.create()

    session_key = request.session.session_key
    is_punchout = request.session.get('is_punchout', False)
    punchout_return_url = request.session.get('punchout_return_url', settings.PUNCHOUT_RETURN_URL)
    punchout_user = request.session.get('punchout_user', request.user.email if request.user.is_authenticated else 'test@localhost')
    punchout_buyer_cookie = request.session.get('punchout_buyer_cookie', '123456')
    logger.info(f"Checkout accessed with method: {request.method}, session_key: {session_key}, is_punchout: {is_punchout}")

    if not request.user.is_authenticated:
        logger.info(f"User not authenticated for session_key {session_key}, redirecting to login.")
        messages.warning(request, "Please log in to proceed with checkout.")
        return redirect('accounts:login')

    cart_items = CartItem.objects.filter(session_key=session_key)
    if not cart_items.exists():
        logger.warning("Empty cart for checkout")
        messages.warning(request, "Your cart is empty.")
        return redirect('cart:view_cart')

    total = 0
    for item in cart_items:
        item.subtotal = item.product.price * item.quantity
        total += item.subtotal
        item.product.s3_image_url = get_s3_presigned_url(settings.AWS_S3_BUCKET_NAME, item.product.large_image) if item.product.large_image else None

    if request.method == 'POST':
        # Generate unique order_id for this checkout
        order_id = uuid.uuid4()

        # Generate PunchOutOrderMessage
        cxml = ET.Element('cXML', version="1.2.020", payloadID=f"poom_{session_key}_{int(datetime.utcnow().timestamp())}",
                          timestamp=datetime.utcnow().isoformat() + 'Z')
        message = ET.SubElement(cxml, 'PunchOutOrderMessage')
        ET.SubElement(message, 'BuyerCookie').text = punchout_buyer_cookie
        header = ET.SubElement(message, 'PunchOutOrderMessageHeader')
        total_elem = ET.SubElement(header, 'Total')
        ET.SubElement(total_elem, 'Money', currency="INR").text = str(total)

        for item in cart_items:
            item_in = ET.SubElement(message, 'ItemIn', quantity=str(item.quantity))
            item_id = ET.SubElement(item_in, 'ItemID')
            ET.SubElement(item_id, 'SupplierPartID').text = item.product.item_code
            item_detail = ET.SubElement(item_in, 'ItemDetail')
            unit_price = ET.SubElement(item_detail, 'UnitPrice')
            ET.SubElement(unit_price, 'Money', currency="INR").text = str(item.product.price)
            ET.SubElement(item_detail, 'Description').text = item.product.product_title
            ET.SubElement(item_detail, 'UnitOfMeasure').text = "EA"
            if item.product.unspsc:
                # Agar hai, to Classification tag add karein
                ET.SubElement(item_detail, 'Classification', domain="UNSPSC").text = item.product.unspsc

        poom_xml = ET.tostring(cxml, encoding='utf-8', method='xml').decode('utf-8')

        # Save cart items to PunchOutOrder with cXML
        for item in cart_items:
            PunchOutOrder.objects.create(
                order_id=order_id,
                session_key=session_key,
                buyer_cookie=punchout_buyer_cookie,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price,
                return_url=punchout_return_url,
                buyer_identity=punchout_user,
                cxml_content=poom_xml
            )
        logger.info(f"Saved {cart_items.count()} items to PunchOutOrder with order_id: {order_id}, session_key: {session_key}")

        # Send to Ariba's return URL
        try:
            response = requests.post(punchout_return_url, data=poom_xml, headers={'Content-Type': 'text/xml'})
            if response.status_code == 200:
                logger.info(f"PunchOutOrderMessage sent successfully to {punchout_return_url}")
                # Clear cart and session
                cart_items.delete()
                if is_punchout:
                    request.session['is_punchout'] = False
                    request.session['punchout_buyer_cookie'] = None
                    request.session['punchout_return_url'] = None
                    request.session['punchout_user'] = None
                    request.session.save()
                return redirect(punchout_return_url)
            else:
                logger.error(f"Failed to send PunchOutOrderMessage: {response.status_code}")
                messages.error(request, "Failed to process order with Ariba.")
                return redirect('cart:view_cart')
        except requests.RequestException as e:
            logger.error(f"Error sending PunchOutOrderMessage: {e}")
            messages.error(request, "Error connecting to Ariba.")
            return redirect('cart:view_cart')

    # Render checkout page for GET requests
    return render(request, 'cart/checkout.html', {'cart_items': cart_items, 'total': total})

def thankyou(request):
    """Render thank you page for non-PunchOut checkouts."""
    logger.info(f"Thank You page accessed for session_key: {request.session.session_key}")
    return render(request, 'cart/thankyou.html')

def proceed_to_thankyou(request):
    """Handle non-PunchOut checkout completion."""
    if not request.session.session_key:
        logger.info("No session key, creating a new one.")
        request.session.create()

    session_key = request.session.session_key
    if request.session.get('is_punchout', False):
        logger.info(f"PunchOut session detected, redirecting to PunchOut return flow.")
        return redirect('punchout:return_cart_to_ariba')

    logger.info(f"Proceed to Thank You accessed with method: {request.method}, session_key: {session_key}")

    if request.method == 'POST':
        cart_items = CartItem.objects.filter(session_key=session_key)
        logger.info(f"Clearing cart for session_key: {session_key}, items: {cart_items.count()}")
        cart_items.delete()
        logger.info(f"Cart cleared, redirecting to thank you page for session_key: {session_key}")
        return redirect('cart:thankyou')

    return redirect('cart:view_cart')