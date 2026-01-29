# SAP Ariba PunchOut Integration - Flow Analysis

## Executive Summary

✅ **Create Mode**: FULLY COMPATIBLE
❌ **Edit Mode**: FIXED - Now allows user to browse catalog with pre-populated cart

---

## Scenario 1: Create Mode (Empty Cart)

### Flow:
1. **Ariba → Your System**: PunchOutSetupRequest (operation="create")
2. **Your System Processes**:
   - ✅ Extracts: BuyerCookie, BrowserFormPost URL, From Identity
   - ✅ Creates/logs in user based on from_identity
   - ✅ Stores PunchOutSession in database
   - ✅ Generates session_key
3. **Your System → Ariba**: PunchOutSetupResponse
   ```xml
   <StartPage>
     <URL>https://kalikaindia.com/?punchout_session={session_key}</URL>
   </StartPage>
   ```
4. **User browses catalog** in iframe with punchout_session parameter
5. **User adds items** to cart (tracked by session_key)
6. **User clicks "PunchOut Checkout"**
7. **Your System → Ariba**: PunchOutOrderMessage with cart items
8. **Auto-submits** to BrowserFormPost URL

### Code Implementation:
- **File**: `punchout/views.py`
- **Function**: `punchout_setup()` (lines 90-203)
- **Middleware**: `PunchOutSessionMiddleware` ensures session_key consistency
- **Database**: `PunchOutSession` model stores session data
- **Status**: ✅ WORKING

---

## Scenario 2: Edit Mode (Pre-populated Cart)

### Previous Behavior (BROKEN):
- System would immediately return cart to Ariba without letting user browse
- User never saw the catalog

### NEW Fixed Behavior:
1. **Ariba → Your System**: PunchOutSetupRequest (operation="edit") with ItemOut elements
2. **Your System Processes**:
   - ✅ Detects operation="edit"
   - ✅ Extracts all ItemOut elements (SupplierPartID + quantity)
   - ✅ Clears existing cart for session_key
   - ✅ Looks up each product by item_code
   - ✅ Creates CartItem entries with specified quantities
   - ✅ Logs items not found in catalog
3. **Your System → Ariba**: PunchOutSetupResponse
   ```xml
   <StartPage>
     <URL>https://kalikaindia.com/cart/?punchout_session={session_key}</URL>
   </StartPage>
   ```
   **Note**: Redirects to `/cart/` (not home) so user sees pre-populated cart
4. **User sees cart** with pre-populated items
5. **User can**:
   - Add more items from catalog
   - Modify quantities
   - Remove items
6. **User clicks "PunchOut Checkout"** when ready
7. **Your System → Ariba**: PunchOutOrderMessage with final cart state
8. **Auto-submits** to BrowserFormPost URL

### Code Changes Made:
- **File**: `punchout/views.py` (lines 162-207)
- **Key Fix**: Line 206 redirects to cart instead of immediately returning to Ariba
- **Improvements**:
  - Better logging
  - Tracks items not found
  - Uses `update_or_create` instead of `create`
  - Strips whitespace from SupplierPartID
  - Redirects to cart view for user to review

---

## Critical Issues Resolved

### Issue 1: Session Cookie Blocking in iFrame ✅ FIXED
**Problem**: Browsers block 3rd-party cookies in iframes (kalikaindia.com inside service.ariba.com)

**Solution**:
1. **Settings.py**:
   ```python
   CSRF_COOKIE_SAMESITE = 'None'
   SESSION_COOKIE_SAMESITE = 'None'
   CSRF_COOKIE_SECURE = True
   SESSION_COOKIE_SECURE = True
   ```

2. **PunchOutSessionMiddleware**: Forces session_key from `?punchout_session=` parameter

3. **Database Fallback**: Stores PunchOut data in `PunchOutSession` model

### Issue 2: CSRF Token Validation ✅ FIXED
**Problem**: AJAX add-to-cart failing with 403 CSRF error

**Solution**:
1. Added `CSRF_TRUSTED_ORIGINS` for Ariba domains
2. Updated JavaScript to get CSRF token from cookie
3. Added `@ensure_csrf_cookie` decorator to views
4. Preserve punchout_session parameter in AJAX requests

### Issue 3: Edit Mode Flow ✅ FIXED
**Problem**: Edit mode immediately returned cart without letting user browse

**Solution**:
- Changed line 206 from `return _prepare_and_return_cart_to_ariba(request)` 
- To: Redirect to cart view with PunchOutSetupResponse
- User can now modify cart before clicking "PunchOut Checkout"

### Issue 4: SSL Certificate Chain ✅ FIXED
**Problem**: Missing intermediate CA certificate

**Solution**:
- Created fullchain certificate (server + intermediate)
- Updated Nginx to use fullchain
- SSL now validates with `Verify return code: 0`

---

## Database Schema

### PunchOutSession Model
```python
session_key = CharField(max_length=255, unique=True)
return_url = TextField()  # BrowserFormPost URL
buyer_cookie = TextField()  # BuyerCookie from Ariba
from_identity = CharField(max_length=255)  # Buyer's NetworkID
created_at = DateTimeField(auto_now_add=True)
```

**Purpose**: Store PunchOut session data when cookies don't work in iframe

---

## cXML Mapping

### PunchOutSetupRequest → Database/Session
| cXML Path | Stored As | Used For |
|-----------|-----------|----------|
| `//From/Credential/Identity` | `from_identity` | User identification, PunchOutOrderMessage Header |
| `//BrowserFormPost/URL` | `return_url` | Where to POST PunchOutOrderMessage |
| `//BuyerCookie` | `buyer_cookie` | Included in PunchOutOrderMessage |
| `//ItemOut/ItemID/SupplierPartID` | Lookup: `Product.item_code` | Pre-populate cart in edit mode |
| `//ItemOut/@quantity` | `CartItem.quantity` | Item quantity in edit mode |

### PunchOutOrderMessage Generation
| Data Source | cXML Element |
|-------------|--------------|
| `from_identity` | `//From/Credential/Identity`, `//To/Credential/Identity` |
| `buyer_cookie` | `//BuyerCookie` |
| `CartItem.product.item_code` | `//ItemIn/ItemID/SupplierPartID` |
| `CartItem.quantity` | `//ItemIn/@quantity` |
| `CartItem.product.price` | `//ItemIn/ItemDetail/UnitPrice/Money` |
| `CartItem.product.product_description` | `//ItemIn/ItemDetail/Description` |
| `CartItem.product.unit_of_measure` | `//ItemIn/ItemDetail/UnitOfMeasure` |
| `CartItem.product.unspsc` | `//ItemIn/ItemDetail/Classification[@domain="UNSPSC"]` |

---

## Security Configuration

### Content Security Policy (CSP)
```python
# Middleware: PunchoutCSPMiddleware
response["Content-Security-Policy"] = (
    "frame-ancestors 'self' "
    "https://*.ariba.com "
    "https://*.sap.com "
    "https://service.ariba.com "
    "https://*.aribanetwork.com"
)
```

### CSRF Trusted Origins
```python
CSRF_TRUSTED_ORIGINS = [
    'https://kalikaindia.com',
    'https://www.kalikaindia.com',
    'https://service.ariba.com',
    'https://*.ariba.com',
    'https://*.sap.com',
    'https://*.aribanetwork.com',
]
```

---

## Testing Checklist

### Create Mode
- [x] Receive PunchOutSetupRequest (operation="create")
- [x] Generate valid PunchOutSetupResponse
- [x] User can browse catalog
- [x] User can add items to cart
- [x] CSRF token works in iframe
- [x] Cart link preserves punchout_session
- [x] Cart shows "PunchOut Checkout" button
- [x] Generate valid PunchOutOrderMessage
- [x] Auto-submit to BrowserFormPost URL

### Edit Mode
- [x] Receive PunchOutSetupRequest (operation="edit") with ItemOut
- [x] Pre-populate cart with ItemOut products
- [x] Log items not found in catalog
- [x] Redirect to cart view (not immediate return)
- [x] User can see pre-populated cart
- [x] User can add more items
- [x] User can modify quantities
- [x] Cart shows "PunchOut Checkout" button
- [x] Generate valid PunchOutOrderMessage with final cart
- [x] Auto-submit to BrowserFormPost URL

---

## Known Limitations

1. **Product Matching**: Edit mode requires exact match of `item_code` to `SupplierPartID`
   - If product not found, it's skipped (logged as warning)
   
2. **Browser Compatibility**: Requires modern browsers that support:
   - SameSite=None cookies
   - Fetch API
   - ES6 JavaScript

3. **HTTPS Required**: Both Ariba and your site must use HTTPS for cookies to work

---

## Logs to Monitor

### Successful Create Mode:
```
punchout.views - INFO - Logged in PunchOut user: AN01000000123
punchout.views - DEBUG - PunchOut session created in DB for session_key: {key}
punchout.views - INFO - Redirecting to catalog for create mode
```

### Successful Edit Mode:
```
punchout.views - INFO - Detected 'edit' mode. Found 3 ItemOut elements
punchout.views - INFO - ✓ Added to cart: COTTON GLOVES x 5
punchout.views - INFO - Edit mode: Pre-populated cart with 3/3 items
punchout.views - INFO - Redirecting to cart view for edit mode
```

### Successful Return:
```
punchout.views - INFO - Retrieved PunchOut session from database
punchout.views - INFO - Generated PunchOutOrderMessage for user AN01000000123
punchout.views - INFO - Successfully logged PunchOutOrder for user: AN01000000123
```

---

## Files Modified

1. **ecommerce/settings.py** - CSRF/Session/CSP settings
2. **ecommerce/middleware/security_middleware.py** - PunchOutSessionMiddleware, CSP middleware
3. **punchout/views.py** - Edit mode flow, session handling
4. **cart/views.py** - Session key handling, punchout detection
5. **cart/templates/cart/view_cart.html** - PunchOut checkout button
6. **catalog/views.py** - Pass punchout_session to templates
7. **catalog/templates/catalog/home.html** - CSRF token from cookie, preserve punchout_session
8. **catalog/templates/catalog/header.html** - Preserve punchout_session in cart link

---

## Support Contact

For PunchOut integration issues, check:
1. Nginx error logs: `sudo journalctl -u nginx -n 100`
2. Uvicorn logs: `sudo journalctl -u uvicorn -n 100`
3. Django logs: Check `LOGGING` configuration in settings.py

**Last Updated**: January 25, 2026
