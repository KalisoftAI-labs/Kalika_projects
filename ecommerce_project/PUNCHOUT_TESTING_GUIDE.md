# PunchOut End-to-End Testing Guide

## Complete Flow Overview
```
SAP Ariba → PunchOut Setup → Browse Products → Add to Cart → Checkout → Return to SAP
```

---

## Step 1: Initial PunchOut Setup (Postman)

### Endpoint
```
POST http://127.0.0.1:8000/punchout/setup/
```

### Headers
```
Content-Type: text/xml
```

### Body (cXML PunchOutSetupRequest)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML version="1.2.014" payloadID="12345678@ariba.com" timestamp="2026-01-23T10:30:00-08:00">
    <Header>
        <From>
            <Credential domain="NetworkID">
                <Identity>AN01234567890</Identity>
            </Credential>
        </From>
        <To>
            <Credential domain="DUNS">
                <Identity>987654321</Identity>
            </Credential>
        </To>
        <Sender>
            <Credential domain="NetworkID">
                <Identity>AN01234567890</Identity>
                <SharedSecret>test_secret_123</SharedSecret>
            </Credential>
            <UserAgent>Ariba Procurement Solution</UserAgent>
        </Sender>
    </Header>
    <Request>
        <PunchOutSetupRequest operation="create">
            <BuyerCookie>1516141750254-123456789</BuyerCookie>
            <Extrinsic name="User">john.doe@company.com</Extrinsic>
            <Extrinsic name="UniqueName">John Doe</Extrinsic>
            <BrowserFormPost>
                <URL>https://your-company.ariba.com/Buyer/Main/ad/supplierReturn/aw</URL>
            </BrowserFormPost>
            <SupplierSetup>
                <URL>http://127.0.0.1:8000/catalog/</URL>
            </SupplierSetup>
        </PunchOutSetupRequest>
    </Request>
</cXML>
```

### Expected Response (PunchOutSetupResponse)
```xml
<?xml version='1.0' encoding='UTF-8'?>
<!DOCTYPE cXML SYSTEM "http://xml.cXML.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML version="1.2.014" payloadID="..." timestamp="...">
    <Response>
        <Status code="200" text="success">PunchOut Setup Success</Status>
        <PunchOutSetupResponse>
            <StartPage>
                <URL>http://127.0.0.1:8000/catalog/</URL>
            </StartPage>
        </PunchOutSetupResponse>
    </Response>
</cXML>
```

### What This Does
- Authenticates the PunchOut session
- Stores session data:
  - `is_punchout = True`
  - `punchout_buyer_cookie = "1516141750254-123456789"`
  - `punchout_return_url = "https://your-company.ariba.com/Buyer/Main/ad/supplierReturn/aw"`
  - `punchout_from_identity = "AN01234567890"`
  - `punchout_user = "john.doe@company.com"`
- Returns StartPage URL to begin shopping

---

## Step 2: Copy Session Cookie from Postman

After successful PunchOut setup in Postman, you need to transfer the session to your browser.

### How to Get Session Cookie from Postman
1. In Postman, after the POST to `/punchout/setup/`, click on **Cookies** (below the Send button)
2. Look for the cookie named `sessionid`
3. Copy the cookie value (long string like `abcd1234efgh5678...`)

### Transfer Session to Browser
#### Option A: Browser Developer Tools (Recommended)
1. Open http://127.0.0.1:8000/ in your browser
2. Press F12 to open Developer Tools
3. Go to **Application** tab (Chrome) or **Storage** tab (Firefox)
4. Under **Cookies** → `http://127.0.0.1:8000`
5. Find or create `sessionid` cookie
6. Replace its value with the one from Postman
7. Set the following:
   - **Domain**: `127.0.0.1`
   - **Path**: `/`
   - **Expires**: Set to future date
8. Refresh the page

#### Option B: Browser Extension
- Use "EditThisCookie" (Chrome) or "Cookie Editor" (Firefox)
- Import/Edit the sessionid cookie value

### Verify Session Transfer
1. Check browser console logs
2. Look at the "Punchout Checkout" button in cart (should be visible if session is active)

---

## Step 3: Browse and Add Products to Cart

### Actions
1. Navigate to: http://127.0.0.1:8000/catalog/
2. Browse products (search, filter by categories)
3. Click "Add to Cart" on products you want
4. Repeat for multiple products

### Verification
- Check that products appear in cart: http://127.0.0.1:8000/cart/
- Verify quantities and prices are correct
- **Important**: Look for "Punchout Checkout" button (not regular "Proceed to Checkout")

### Expected Cart Page
```html
<!-- If is_punchout session variable is True -->
<button type="submit">Punchout Checkout</button>

<!-- If is_punchout is False -->
<a href="/cart/checkout/">Proceed to Checkout</a>
```

---

## Step 4: Click "Punchout Checkout"

### What Happens
1. Form submits to: `/punchout/return-cart/`
2. Server generates `PunchOutOrderMessage` XML
3. XML includes all cart items with:
   - Product details (title, item code, UNSPSC)
   - Quantities and prices
   - Total cost
   - BuyerCookie (from session)
4. Server renders auto-submit HTML form
5. Form automatically POSTs XML back to SAP Ariba URL

### Expected Auto-Submit Page
You'll briefly see a page that says:
```
Returning order to procurement system...
Please wait while we redirect you back to your procurement system.
```

Then the form automatically submits.

---

## Step 5: Verify PunchOutOrderMessage XML

### Check Server Logs
Look for this log entry:
```
INFO - Generated PunchOutOrderMessage for user john.doe@company.com:
<?xml version='1.0' encoding='UTF-8'?>
<!DOCTYPE cXML SYSTEM "http://xml.cXML.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML version="1.2.014" payloadID="..." timestamp="...">
    <Header>
        <From>
            <Credential domain="DUNS">
                <Identity>987654321</Identity>
            </Credential>
        </From>
        <To>
            <Credential domain="NetworkID">
                <Identity>AN01234567890</Identity>
            </Credential>
        </To>
        <Sender>
            <Credential domain="DUNS">
                <Identity>987654321</Identity>
                <SharedSecret>your_shared_secret</SharedSecret>
            </Credential>
            <UserAgent>Kalika PunchOut</UserAgent>
        </Sender>
    </Header>
    <Message>
        <PunchOutOrderMessage>
            <BuyerCookie>1516141750254-123456789</BuyerCookie>
            <PunchOutOrderMessageHeader operationAllowed="edit">
                <Total>
                    <Money currency="INR">15000.00</Money>
                </Total>
            </PunchOutOrderMessageHeader>
            <ItemIn quantity="2">
                <ItemID>
                    <SupplierPartID>ITEM001</SupplierPartID>
                </ItemID>
                <ItemDetail>
                    <UnitPrice>
                        <Money currency="INR">5000.00</Money>
                    </UnitPrice>
                    <Description>Product Title Here</Description>
                    <UnitOfMeasure>EA</UnitOfMeasure>
                    <Classification domain="UNSPSC">43211500</Classification>
                </ItemDetail>
            </ItemIn>
            <!-- More items... -->
        </PunchOutOrderMessage>
    </Message>
</cXML>
```

### Verify in Database
```sql
SELECT * FROM punchout_punchoutorder ORDER BY created_at DESC LIMIT 5;
SELECT * FROM punchout_punchoutorderitem WHERE order_id = <latest_order_id>;
```

---

## Step 6: Simulate SAP Return (Since You Don't Have Real SAP)

Since you don't have a real SAP Ariba environment, the form will try to POST to a non-existent URL and fail. This is expected.

### To Test Locally Without SAP:

#### Option 1: Inspect the Auto-Submit Form
1. In `return_to_ariba.html` template, temporarily comment out the auto-submit JavaScript:
```html
<!-- Comment this out temporarily -->
<!-- <script>document.forms['cxml-form'].submit();</script> -->
```

2. This will show you the form without auto-submitting
3. You can inspect the hidden field containing the full cXML
4. Copy and verify the XML structure

#### Option 2: Use RequestBin/Webhook.site
1. Go to https://webhook.site/
2. Copy your unique URL (e.g., `https://webhook.site/12abc345`)
3. In the PunchOut setup request (Step 1), replace the BrowserFormPost URL:
```xml
<BrowserFormPost>
    <URL>https://webhook.site/12abc345</URL>
</BrowserFormPost>
```
4. Complete the flow
5. Check webhook.site to see the exact XML that was POSTed

#### Option 3: Local Test Server
Create a simple Flask endpoint to receive the POST:
```python
# test_receiver.py
from flask import Flask, request
app = Flask(__name__)

@app.route('/receive', methods=['POST'])
def receive():
    xml_data = request.data.decode('utf-8')
    print("=" * 80)
    print("Received PunchOutOrderMessage:")
    print(xml_data)
    print("=" * 80)
    return "Order received successfully!", 200

if __name__ == '__main__':
    app.run(port=5000)
```

Run: `python test_receiver.py`

Use `http://127.0.0.1:5000/receive` as BrowserFormPost URL.

---

## Troubleshooting

### Issue: "Punchout Checkout" Button Not Visible
**Cause**: Session variable `is_punchout` not set to `True`

**Fix**:
- Redo PunchOut setup request in Postman
- Verify response is successful
- Copy session cookie correctly to browser
- Check: `request.session.get('is_punchout')` should return `True`

### Issue: "You must be logged in to checkout"
**Cause**: User not authenticated in Django

**Fix**:
```python
# Create a test user if needed
python manage.py createsuperuser
# Or use existing user credentials
```
Login at: http://127.0.0.1:8000/accounts/login/

### Issue: "Your cart is empty"
**Cause**: Cart items not persisted or wrong session

**Fix**:
- Use same browser session that has the PunchOut cookie
- Don't clear browser data between steps
- Verify cart items in database:
```sql
SELECT * FROM cart_cartitem WHERE session_key = '<your_session_key>';
```

### Issue: XML Generation Errors
**Cause**: Missing product data (price, item_code, etc.)

**Fix**:
- Verify products have required fields populated
- Check logs for specific errors
- Ensure products have valid `price`, `item_code`, and `product_title`

---

## Complete Testing Checklist

- [ ] 1. Send PunchOut setup request in Postman
- [ ] 2. Verify PunchOutSetupResponse received
- [ ] 3. Copy sessionid cookie from Postman
- [ ] 4. Open browser to http://127.0.0.1:8000/
- [ ] 5. Paste sessionid cookie in browser dev tools
- [ ] 6. Login to Django (if required)
- [ ] 7. Browse catalog at /catalog/
- [ ] 8. Add multiple products to cart
- [ ] 9. Go to cart at /cart/
- [ ] 10. Verify "Punchout Checkout" button is visible
- [ ] 11. Click "Punchout Checkout"
- [ ] 12. Verify auto-submit page appears
- [ ] 13. Check server logs for PunchOutOrderMessage XML
- [ ] 14. Verify database PunchOutOrder records created
- [ ] 15. (Optional) Use webhook.site to capture the POST

---

## Key URLs

| Purpose | URL |
|---------|-----|
| PunchOut Setup (Postman) | `POST http://127.0.0.1:8000/punchout/setup/` |
| Home/Catalog | `http://127.0.0.1:8000/catalog/` |
| View Cart | `http://127.0.0.1:8000/cart/` |
| Django Admin | `http://127.0.0.1:8000/django-admin/` |
| FastAPI Admin | `http://127.0.0.1:8000/admin/` |
| Login | `http://127.0.0.1:8000/accounts/login/` |

---

## Session Variables Reference

After PunchOut setup, these should be in session:
```python
request.session['is_punchout'] = True
request.session['punchout_buyer_cookie'] = "1516141750254-123456789"
request.session['punchout_return_url'] = "https://your-company.ariba.com/..."
request.session['punchout_from_identity'] = "AN01234567890"
request.session['punchout_user'] = "john.doe@company.com"
```

To check in Django shell:
```python
python manage.py shell
from django.contrib.sessions.models import Session
from django.utils import timezone
active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
for s in active_sessions:
    print(s.get_decoded())
```

---

## Expected Database Records

### After Checkout
```sql
-- PunchOut Orders
SELECT 
    id,
    user_id,
    total_cost,
    created_at,
    LENGTH(cxml_payload) as xml_size
FROM punchout_punchoutorder 
ORDER BY created_at DESC 
LIMIT 5;

-- Order Items
SELECT 
    id,
    order_id,
    product_title,
    item_code,
    quantity,
    unit_price,
    subtotal
FROM punchout_punchoutorderitem 
ORDER BY id DESC 
LIMIT 10;
```

---

## Success Criteria

✅ PunchOut setup returns valid XML response
✅ Session variables are set correctly
✅ "Punchout Checkout" button appears in cart
✅ Auto-submit form page renders
✅ PunchOutOrderMessage XML is well-formed
✅ XML includes all cart items with correct data
✅ Database records created for order tracking
✅ Cart is cleared after checkout
✅ Session is flushed after return
