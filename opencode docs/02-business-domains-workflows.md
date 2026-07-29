# Business Domains & Workflow Documentation

## 1. DOMAIN MAP

```
┌─────────────────────────────────────────────────────────┐
│                   KALIKA E-COMMERCE                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  CATALOG     │  │  CART        │  │  AUTH        │   │
│  │  (public)    │  │  (session)   │  │  (Django)    │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                  │           │
│  ┌──────┴─────────────────┴──────────────────┴───────┐   │
│  │              PUNCHOUT (cXML / Ariba)              │   │
│  │  ┌─────────────┐  ┌────────────┐  ┌────────────┐  │   │
│  │  │ Setup       │  │ Shop/Edit  │  │ Return     │  │   │
│  │  │ (Ariba→Us)  │  │ (Our Site) │  │ (Us→Ariba) │  │   │
│  │  └─────────────┘  └────────────┘  └────────────┘  │   │
│  └────────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  ADMIN       │  │  CHATBOT     │  │  INTEGRATIONS│   │
│  │  (FastAPI)   │  │  (Gemini)    │  │  (S3, APIs)  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 2. DOMAIN: PUBLIC CATALOG

### Purpose
Allow buyers (especially Ariba punchout users) to browse products without login.

### Key Files
- `catalog/views.py` (344 lines) — home, product_list, product_detail, products_by_category, products_by_subcategory, all_categories, search_products
- `catalog/models.py` — Product model (maps to `products` table)
- `catalog/context_processors.py` — categories nav + cart count
- `catalog/templatetags/catalog_tags.py` — custom template filter
- `catalog/urls.py` — 7 URL patterns
- Templates: `home.html`, `product_list.html`, `product_detail.html`, `products_by_category.html`, `products_by_subcategory.html`, `all_categories.html`, `search_results.html`

### Data Flow
```
Browser → Nginx → Django
  ├── GET / → home() → Product.objects.filter(main_category__in=DEFINED)
  │     → add_s3_urls_to_products() → cached 5min
  │     → build_category_context() → cached per request
  │     → render home.html
  │
  ├── GET /product/<id>/ → product_detail() → Product.objects.get(item_id=id)
  │     → get_s3_presigned_url() → 1hr cache
  │
  ├── GET /category/<main>/ → products_by_category()
  │     → filter(main_category=main) → S3 URLs → render
  │
  ├── GET /category/<main>/<sub>/ → products_by_subcategory()
  │     → filter(main_category=main, sub_categories=sub) → render
  │
  └── GET /search/?q= → search_products()
        → Q(title__icontains=q) OR Q(category__icontains=q) → limit 12 → render
```

### S3 Image URL Pattern
```
products → add_s3_urls_to_products() → for each product:
  cache_key = f"s3_url_{item_id}_{hash(large_image)}"
  if cached → use cached
  else → boto3 generate_presigned_url('get_object', Bucket, Key, ExpiresIn=3600)
       → cache for 3600s
       → product.s3_image_url = result
```

### Categories Logic
- 18 hardcoded main categories in `DEFINED_MAIN_CATEGORIES`
- Blocklist filters out: "home", "system", "menu1", "shop", ""
- First 10 main categories shown in dropdown
- Subcategories with product count, up to 5 product previews

### API Routes to Create
```
GET /api/catalog/home              → products by category, hero video URL
GET /api/catalog/products          → list with pagination, sort, search
GET /api/catalog/products/{id}     → single product with S3 URL
GET /api/catalog/categories        → nested category tree
GET /api/catalog/categories/{main} → products in main category
GET /api/catalog/categories/{main}/{sub} → products in subcategory
GET /api/catalog/search?q=         → search results
```

---

## 3. DOMAIN: SHOPPING CART

### Purpose
Session-based cart for punchout buyers (no login required for basic cart operations).

### Key Files
- `cart/views.py` (261 lines) — add_to_cart, view_cart, remove_from_cart, update_cart_quantity, checkout, thankyou, proceed_to_thankyou
- `cart/models.py` — CartItem (session_key, product FK, quantity)
- `cart/urls.py` — 7 URL patterns
- Templates: `view_cart.html`, `checkout.html`

### Cart Operations
```
Add:     POST /cart/add/<item_id>/  → get_or_create CartItem(session_key, product)
                                        quantity += 1 (if exists)
                                        AJAX: JsonResponse; else: redirect view_cart

View:    GET /cart/  → CartItem.objects.filter(session_key=session_key)
                        → S3 URLs per product → total = sum(subtotal)
                        → render view_cart.html

Remove:  POST /cart/remove/<item_id>/ → CartItem.objects.get(id=id, session_key=key).delete()

Update:  POST /cart/update_quantity/ (JSON body: {item_id, quantity})
          → CartItem.objects.get(id=id, session_key=key)
          → if qty > 0: update; else: delete
          → return JSON {new_quantity, new_subtotal, new_total}
```

### Checkout Flow (critical dual-path)
```
POST /cart/checkout/:
  if is_punchout in session:
    → _prepare_and_return_cart_to_ariba()
    → build PunchOutOrderMessage cXML
    → POST to Ariba return URL
  else:
    → save PunchOutOrder locally
    → render thankyou
```

### API Routes to Create
```
GET  /api/cart              → current cart with items, totals, S3 URLs
POST /api/cart/items        → {product_id, quantity} → add to cart
PUT  /api/cart/items/{id}   → {quantity} → update quantity
DELETE /api/cart/items/{id} → remove from cart
POST /api/cart/checkout     → process checkout (punchout or standard)
```

---

## 4. DOMAIN: PUNCHOUT / cXML (SAP ARIBA)

### Purpose
SAP Ariba PunchOut integration via cXML 1.2.014 protocol.

### Key Files
- `punchout/views.py` (330 lines) — punchout_setup, return_cart_to_ariba, _prepare_and_return_cart_to_ariba
- `punchout/models.py` — PunchOutOrder, PunchOutOrderItem
- `punchout/urls.py` — 2 URL patterns
- `punchout/admin.py` — Django admin registration
- Templates: `return_to_ariba.html`, `punchout_error.html`

### Workflow 1: PunchOut Setup (Ariba → Kalika)
```
1. Ariba POSTs /punchout/setup/ with cxml-urlencoded form field
2. URL-decode cXML payload
3. Parse with lxml.etree
4. Verify <SharedSecret> matches settings.PUNCHOUT_SHARED_SECRET
5. Extract: from_identity, browser_post_url, buyer_cookie
6. GetOrCreate CustomUser(buyer_identifier=from_identity)
7. Store in session: is_punchout, punchout_return_url, punchout_buyer_cookie, punchout_from_identity
8. If <ItemOut> elements exist (edit mode):
   → Lookup products by item_code
   → Create CartItem entries
   → Immediately call return_cart_to_ariba
9. If setup mode:
   → Generate StartPage URL: https://kalikaindia.com/?punchout_session=<session_key>
   → Return cXML PunchOutSetupResponse
```

### Workflow 2: Return Cart (Kalika → Ariba)
```
1. Buyer clicks "Checkout" in catalog
2. If is_punchout in session:
3. Fetch CartItems for session
4. Build cXML PunchOutOrderMessage:
   <cXML>
     <Header> <From> <To> <Sender>
     <Message>
       <PunchOutOrderMessage>
         <BuyerCookie>
         <PunchOutOrderMessageHeader>
           <Total><Money>
         <ItemIn quantity=N> per cart item:
           <ItemID><SupplierPartID>
           <ItemDetail><UnitPrice><Money>
                     <Description>
                     <UnitOfMeasure>
                     <Classification domain="UNSPSC">
5. Save PunchOutOrder + PunchOutOrderItem records (audit trail)
6. Delete CartItems
7. Render auto-submit form that POSTs cXML to Ariba's return URL
```

### cXML Credentials (from .env)
```
PUNCHOUT_ANID = AN01284122159-T        (supplier's Ariba Network ID)
PUNCHOUT_SUPPLIER_DUNS = 651009354     (DUNS number)
PUNCHOUT_SHARED_SECRET = <secret>      (authenticates sender)
ARIBA_NETWORK_ID = <buyer-org-id>
ARIBA_ENDPOINT = https://test.ariba.com/punchout/cxml/setup
```

### API Routes to Create
```
POST /api/punchout/setup         → receive cxml-urlencoded → parse → respond
POST /api/punchout/return-cart   → build cXML PunchOutOrderMessage → return XML
GET  /api/punchout/orders        → list punchout orders
GET  /api/punchout/orders/{id}   → single punchout order detail
```

### Risk: CRITICAL
- Must preserve EXACT cXML format — SAP Ariba rejects deviations
- DOCTYPE declaration required: `<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">`
- `<BuyerCookie>` must round-trip correctly
- SharedSecret verification must be exact match
- Session continuity between setup → shopping → return must not break

---

## 5. DOMAIN: USER AUTH

### Current State: Dual System

| Aspect | Django Public | FastAPI Admin |
|--------|---------------|---------------|
| Auth method | `django.contrib.auth` | raw passlib + session |
| Password hash | Django's PBKDF2 | passlib pbkdf2_sha256 |
| Session | Django DB sessions | Starlette SessionMiddleware |
| User model | CustomUser (accounts_customuser table) | Same table, raw queries |

### CustomUser Model
```
CustomUser(AbstractUser):
  role = CharField(choices: Admin/User/PunchOut)
  buyer_identifier = CharField(unique, indexed, nullable)
  first_name = None (removed)
  last_name = None (removed)
```

### API Routes to Create
```
POST /api/auth/register    → create user
POST /api/auth/login       → return JWT tokens
POST /api/auth/refresh     → refresh access token
POST /api/auth/logout      → invalidate refresh token
GET  /api/auth/me          → current user profile
```

---

## 6. DOMAIN: ADMIN PANEL

### Current Implementation
- **Framework:** FastAPI (single `app.py` — 2,402 lines)
- **Templates:** 24 Jinja2 HTML files
- **CSS:** `styles.css` (~600 lines)
- **Auth:** Custom session-based (passlib verify against `accounts_customuser`)

### Admin Capabilities

| Feature | Route | Description |
|---------|-------|-------------|
| Dashboard | `/dashboard` | Sales, products, users, orders stats; Chart.js charts |
| Items list | `/items` | DataTable with server-side processing, search, sort |
| Add product | `/products/add` | Form with S3 image upload (file + URL) |
| Edit product | `/edit-product?item_id=X` | Load by ID, update all fields |
| Advance edit | `/advance-edit?item_id=X` | Additional fields editing |
| Bulk modify | `/bulk-modify` | CSV upload: add/update_price/update_description/delete |
| Bulk properties | `/bulk-modify-properties` | CSV: update item properties by item_code |
| Bulk column | `/bulk-modify-properties-column` | CSV with Action column (add/edit/delete) |
| Export | `/export-file` | Background CSV export with threading |
| Categories | `/categories` | Category management UI |
| Item options | `/item-options` | Additional item configuration |
| Inventory | `/inventory` | Inventory management |
| Orders | `/pending-orders`, `/orders` | Order listing and management |
| Users | `/users`, `/users/add`, `/users/edit/{id}` | User CRUD |
| PunchOut | `/punchout` | PunchOut response history |
| Analytics | `/analytics` | Product category analytics |
| Settings | `/settings` | App settings page |

### Product DB Operations (all in app.py)
- `get_product_by_identifier(item_id, item_code, product_title)` — fetch single
- `add_product_to_db(product_data)` — insert with RETURNING item_id
- `update_product_in_db(item_id, product_data)` — dynamic SET clause
- `update_product_price_in_db(item_id, price)` — targeted price update
- `update_product_description_in_db(item_id, desc)` — targeted description update
- `delete_product_by_identifier(item_id, item_code)` — delete by either
- `api_products_list(draw, start, length, search, order)` — DataTables JSON
- `simulate_export(job_id, options)` — background CSV export (threading)

### API Routes to Create
```
GET  /api/admin/dashboard        → stats
GET  /api/admin/products         → paginated list (DataTables compat)
POST /api/admin/products         → create product
PUT  /api/admin/products/{id}    → update product
DELETE /api/admin/products/{id}  → delete product
POST /api/admin/products/bulk    → CSV bulk import
POST /api/admin/products/export  → initiate export
GET  /api/admin/products/export/{job_id} → export status
GET  /api/admin/categories       → category tree
GET  /api/admin/orders           → order list (pending/completed)
GET  /api/admin/users            → user list
POST /api/admin/users            → create user
PUT  /api/admin/users/{id}       → update user
```

---

## 7. DOMAIN: CHATBOT

### Implementation
```
chatbot/views.py (71 lines):
- POST /chatbot/chat/       → receive {message} → Gemini API → return {response}
- GET  /chatbot/chat/clear/ → clear session chat history
- Chat history stored in Django session
- Gemini model: gemini-2.0-flash
- CSRF exempt (simple CSRF)
```

### API Route to Create
```
POST /api/chatbot/message   → {message} → Gemini → {response}
POST /api/chatbot/clear     → clear history
```

---

## 8. DOMAIN: INTEGRATIONS

| Integration | Type | Purpose | Key Code |
|-------------|------|---------|----------|
| SAP Ariba | cXML POST | PunchOut setup + cart return | `punchout/views.py` |
| AWS S3 | SDK (boto3) | Product image storage + presigned URLs | `catalog/views.py:80-96`, `fastapi_app/app.py:52-99` |
| Google Gemini | REST API | AI chatbot | `chatbot/views.py` |

---

## 9. SECURITY DOMAIN

### Current Middleware Stack
1. `django.middleware.security.SecurityMiddleware` — Django built-in
2. `ecommerce.middleware.security_middleware.SecurityMiddleware` — custom IP block + path block
3. `ecommerce.middleware.security_middleware.RateLimitMiddleware` — 20 req/min on sensitive paths
4. Django: SessionMiddleware, CommonMiddleware, CsrfViewMiddleware, AuthMiddleware, MessageMiddleware, XFrameOptionsMiddleware

### Custom Security Middleware
```
BLOCKED_IPS = {22 known malicious IPs}
SUSPICIOUS_PATHS = ['.env', '.git', 'phpinfo.php', 'info.php', ...]
Rate limit: 20 requests/minute on /admin/, /accounts/login/, /punchout/
Path traversal: '//' and '..' blocked
IP auto-block after 3 suspicious attempts (5min cache)
```

### Must Port to FastAPI
- Same BLOCKED_IPS set
- Same SUSPICIOUS_PATHS logic
- Rate limiting via FastAPI middleware or dependency
- CORS middleware (already exists in Starlette)
