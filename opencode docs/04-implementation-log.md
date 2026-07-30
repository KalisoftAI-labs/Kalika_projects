# Implementation Log — ecommerce-fastapi

> Tracks progress, how to run/test, and what's been built at each stage.

---

## Status Overview

| Step | Description | Status | Date |
|------|------------|--------|------|
| 1 | Project skeleton + health check | **DONE** | 29-Jul |
| 2 | Catalog API (products + categories) | **DONE** | 29-Jul |
| 3 | S3 image service | **DONE** | 29-Jul |
| 4 | Auth + users API | **DONE** | 29-Jul |
| 5 | Cart API | **DONE** | 29-Jul |
| 6 | Homepage rotation + featured + video | **DONE** | 29-Jul |
| 7 | Cart checkout + cXML + order audit | **DONE** | 29-Jul |
| 8 | PunchOut cXML setup + session | **DONE** | 30-Jul |
| 9 | Admin product CRUD + bulk CSV + DataTables + export | **DONE** | 30-Jul |
| 10 | Admin orders + dashboard + users | **DONE** | 30-Jul |
| 10 | Chatbot | ❌ | — |
| 11 | Security middleware (IP block, path block, rate limit) | **DONE** | 30-Jul |
| 12 | Chatbot (Gemini) | ❌ | — |
| 13 | React frontend(s) consuming API | ❌ | — |
| 14 | Security audit + production cutover | ❌ | — |

---

## How to Run

```bash
cd ecommerce-fastapi

# Activate venv
.\venv\Scripts\Activate.ps1

# Start dev server
uvicorn app.main:app --reload --port 8000

# API docs (browser)
http://127.0.0.1:8000/docs

# Health check
curl http://127.0.0.1:8000/api/health
```

---

## How to Test

```bash
cd ecommerce-fastapi

# All tests
.\venv\Scripts\pytest.exe tests/ -v

# Single test file
.\venv\Scripts\pytest.exe tests/test_catalog.py -v
```

---

## Step Log

### Step 1 — Project skeleton + health check (29-Jul)

**Created:**
- `app/main.py`, `config.py`, `database.py` — FastAPI entry, pydantic-settings, SQLAlchemy async engine
- `routers/health.py` — `GET /api/health`
- All `__init__.py` packages
- `tests/conftest.py`, `tests/test_health.py`
- `pyproject.toml`, `requirements.txt`, `.env`
- `scripts/setup_db.py`
- `.gitignore`

**DB:** `ecom_fastapi_dev` (fresh PostgreSQL, separate from old `ecom_prod_catalog`)

**Verify:**
```bash
curl http://127.0.0.1:8000/api/health
# → {"status":"ok","db":"connected"}
```

---

### Step 2 — Catalog API (Products + Categories) (29-Jul)

**Created:**
| File | Purpose |
|------|---------|
| `app/models/product.py` | SQLAlchemy Product model (29 columns, matches old `products` table) |
| `app/schemas/product.py` | Pydantic ProductRead, ProductListResponse, MainCategory/SubCategory |
| `app/services/product_service.py` | list_products, get_product, get_products_by_category, build_category_tree |
| `app/routers/catalog.py` | 5 endpoints: products list, product detail, categories, by category |
| `scripts/import_products.py` | DB seed script — creates table, inserts 10 sample products |
| `tests/test_catalog.py` | 5 tests: list, search, detail, 404, categories |

**Endpoints:**
```
GET /api/catalog/products?page=1&page_size=20&search=&sort_by=item_id&sort_dir=asc
GET /api/catalog/products/{item_id}
GET /api/catalog/categories
GET /api/catalog/categories/{main_category}?sub_category=
```

**Verify:**
```bash
pytest tests/ -v
# → 7 passed (2 health + 5 catalog)

# Product listing:
curl http://localhost:8001/api/catalog/products
# → 10 products with full details

# Categories:
curl http://localhost:8001/api/catalog/categories
# → 5 categories with subcategories and counts
```

**Security:** All queries parameterized via SQLAlchemy. Route input validation via FastAPI Query(). 404 on missing products. No sensitive data in responses.

---

### Step 3 — S3 Image Service (29-Jul)

**Created:**
| File | Purpose |
|------|---------|
| `app/services/s3_service.py` | Presigned URL generation (with TTL cache), S3 image upload, product enrichment |
| `tests/test_s3.py` | 5 tests: fallback, presigned URL, upload, enrichment |

**Integration:**
- `product_service.list_products()` now enriches each product with `s3_image_url`
- `product_service.get_product()` adds `s3_image_url` to single product response
- `product_service.get_products_by_category()` enriches filtered results
- Falls back to `/static/images/noimage.jpg` when no image or S3 unavailable

**Caching:** In-memory dict with TTL (1hr for successful URLs, 5min for defaults). Replace with Redis if throughput grows.

**Verify:**
```bash
# Product detail with S3 URL:
curl http://localhost:8002/api/catalog/products/1
# → s3_image_url: /static/images/noimage.jpg (when no AWS creds)

pytest tests/ -v
# → 11 passed (6 catalog + 5 S3 + 1 health)
```
**Note:** The S3 presigned URLs only work when `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set in `.env`. Without them, all products fall back to the default noimage placeholder.

---

### Step 4 — Auth + Users API (JWT) (29-Jul)

**Created:**
| File | Purpose |
|------|---------|
| `app/models/user.py` | User model (matches old `accounts_customuser` table) |
| `app/schemas/user.py` | UserRegister, UserLogin, UserRead, TokenResponse, TokenRefresh |
| `app/services/auth_service.py` | JWT create/decode, passlib password hash/verify (compat with old Django hashes) |
| `app/dependencies/auth.py` | `get_current_user` (Bearer token), `require_role(role)` |
| `app/routers/auth.py` | 5 endpoints |
| `tests/test_auth.py` | 8 tests |
| `scripts/seed_users.py` | Seeds admin + testuser into new DB |

**Password compat:** Uses `CryptContext` with both `pbkdf2_sha256` (new) and `django_pbkdf2_sha256` (old). Users from old `accounts_customuser` can log in without password reset.

**Endpoints:**
```
POST /api/auth/register    → 201 UserRead
POST /api/auth/login       → 200 {access_token, refresh_token}
POST /api/auth/refresh     → 200 {access_token, refresh_token}
GET  /api/auth/me          → 200 UserRead (requires Bearer token)
```

**Security:** JWT with configurable expiry (default 60min). Refresh tokens valid 30 days. Passwords hashed with pbkdf2-sha256. Bearer auth required for protected endpoints. 401 on invalid/expired tokens. 403 on inactive accounts. `require_role` decorator for admin gating.

**Verify:**
```bash
pytest tests/ -v
# → 19 passed (8 auth + 5 catalog + 5 S3 + 1 health)

# Login as admin:
curl -X POST http://localhost:8003/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
# → {access_token, refresh_token}

# Get current user:
curl http://localhost:8003/api/auth/me \
  -H "Authorization: Bearer <token>"
# → {"id":1,"username":"admin","role":"Admin",...}
```

---

### Step 5 — Cart API (29-Jul)

**Created:**
| File | Purpose |
|------|---------|
| `app/models/cart.py` | CartItem model (user_id or session_token FK) |
| `app/schemas/cart.py` | CartItemAdd, CartItemUpdate, CartItemRead, CartResponse |
| `app/services/cart_service.py` | get, add, update, remove, clear cart |
| `app/routers/cart.py` | 4 endpoints + optional_auth dependency |
| `tests/test_cart.py` | 6 tests |
| `scripts/create_tables.py` | Ensure all tables exist on startup |

**Endpoints:**
```
GET    /api/cart                    → current cart (items, totals)
POST   /api/cart/items             → {product_id, quantity} → add
PUT    /api/cart/items/{id}        → {quantity} → update
DELETE /api/cart/items/{id}        → remove
```

**Auth:** Anonymous via `X-Cart-Token` header (auto-generated UUID). Authenticated via Bearer JWT. Created `optional_current_user` dependency for mixed auth.

**Verify:**
```bash
pytest tests/test_cart.py -v
# → 6 passed (add/get/update/remove/empty/authenticated)
pytest tests/ -v
# → 64 passed
```

---

### Step 11 — Security Middleware (30-Jul)

**Created:**
| File | Purpose |
|------|---------|
| `app/middleware/security.py` | SecurityMiddleware + RateLimitMiddleware (exact port from old `security_middleware.py`) |
| `tests/test_security.py` | 7 tests |

**Two middleware classes:**

**`SecurityMiddleware`** — blocks on every request:
- **12 known malicious IPs** blocked immediately (same list as old site)
- **14 suspicious path patterns** blocked: `.env`, `.git`, `phpinfo.php`, `config.php`, `adminer.php`, `.ini`, `.bak`, `login.asp`, etc.
- **Auto-block:** 3+ suspicious attempts from same IP within 5 min → runtime block
- **Path traversal:** `//` and `..` blocked (at middleware level)
- IP detected via `X-Forwarded-For` header or `REMOTE_ADDR` fallback

**`RateLimitMiddleware`** — limits on sensitive paths:
- **20 requests/minute** on `/api/auth/`, `/api/admin/`, `/api/punchout/`
- Returns 429 when exceeded
- Per-IP per-path tracking with 60s sliding window

**Verify:**
```bash
pytest tests/test_security.py -v
# → 7 passed
pytest tests/ -v
# → 64 passed
```

**Known gaps vs old site (see 05-migration-gap-analysis.md):**
- ❌ Checkout dual-path (punchout vs standard)
- ❌ AJAX quantity update format (old uses JSON POST, we use PUT)
- ❌ cXML generation in checkout
- ❌ PunchOutOrder + PunchOutOrderItem audit creation
- ❌ requests.post to Ariba return URL

---

### Step 6 — Homepage Rotation + Featured + Hero Video (29-Jul)

**Changes:**
| File | What |
|------|------|
| `app/services/product_service.py` | Added `get_homepage_data()` with 9-min rotation, `_get_hero_video_url()`, `_products_to_list()`, updated `build_category_tree()` with 5 product previews per subcategory |
| `app/schemas/product.py` | Added `HomepageProduct`, `HomepageResponse` schemas, added `products` field to `SubCategory` |
| `app/routers/catalog.py` | Added `GET /api/catalog/home` endpoint |
| `app/services/s3_service.py` | Graceful `None` return when no AWS credentials configured |

**Endpoint:**
```
GET /api/catalog/home → {products_by_category, featured_products, hero_video_url, categories}
```

**Homepage logic:**
- Products grouped by 25 `DEFINED_MAIN_CATEGORIES`
- Fuzzy match: `main_category ILIKE first_word%`
- **9-minute rotation:** products shift by 9 every 9 minutes, showing max 10 per category with wrap-around
- Excludes products with `noimage.jpg` in large_image (but includes NULL images)
- **Featured:** first 10 from "Hand & Power Tools"
- **Hero video:** S3 presigned URL for `kalika-images/kalika-ad1.mp4`, cached 3000s
- All S3 URLs batch-processed in a single pass
- Homepage data cached in-memory for 300s

**Category tree update:**
- Each subcategory now includes up to 5 product previews (`item_id`, `product_title`)
- Limited to first 10 main categories
- Both counts and previews returned

**Verify:**
```bash
pytest tests/ -v
# → 26 passed
curl http://localhost:8004/api/catalog/home
# → {products_by_category: {...}, featured_products: [...], categories: {...}}
```

---

### Step 8 — PunchOut cXML Setup + Session (30-Jul)

**Created:**
| File | Purpose |
|------|---------|
| `app/models/punchout_session.py` | PunchOutSession model (replaces Django session storage with own table) |
| `app/services/punchout_service.py` | cXML parsing, SharedSecret verification, user get-or-create, edit mode cart population, setup response generation |
| `app/routers/punchout.py` | 2 endpoints (setup POST + session GET) |
| `tests/test_punchout.py` | 8 tests (parse, validate, setup response, edit mode) |

**Endpoints:**
```
POST /api/punchout/setup       → receives cXML → returns PunchOutSetupResponse XML or edit mode JSON
GET  /api/punchout/session/{id} → punchout session details
```

**Two modes:**
- **Setup mode:** Parses cXML, verifies SharedSecret, creates/get user by buyer_identifier, stores session in `punchout_sessions` table (24hr TTL), returns `PunchOutSetupResponse` cXML with StartPage URL
- **Edit mode:** If `<ItemOut>` elements exist, populates cart with matched products, returns JSON with session_id + return_url + buyer_cookie

**Session storage replaces Django sessions** — punchout metadata (return_url, buyer_cookie, from_identity) stored in `punchout_sessions` table keyed by UUID session_id.

**Verify:**
```bash
pytest tests/test_punchout.py -v
# → 8 passed (parse, generate, setup success, edit mode, invalid cXML, wrong secret)
pytest tests/ -v
# → 38 passed
```

---

### Step 9 — Admin Product CRUD + Bulk CSV + DataTables + Export (30-Jul)

**Created:**
| File | Purpose |
|------|---------|
| `app/services/admin_product_service.py` | CRUD, DataTables query, bulk CSV import (4 modes), datatables |
| `app/services/export_service.py` | CSV export with column selection |
| `app/routers/admin_products.py` | 9 endpoints (all admin-protected via `require_role("Admin")`) |
| `tests/test_admin_products.py` | 11 tests |

**Endpoints:**
```
GET    /api/admin/products                    → paginated list
GET    /api/admin/products/{id}               → single product
POST   /api/admin/products                    → create product
PUT    /api/admin/products/{id}               → update product
DELETE /api/admin/products/{id}               → delete product
POST   /api/admin/products/bulk               → CSV bulk import (add/update_price/update_description/delete)
GET    /api/admin/products/datatables          → DataTables server-side (draw, start, length, search, order)
GET    /api/admin/products/export/csv          → CSV export with column options
```

**Bulk CSV modes:** `add` (required: main_category, item_code, product_title, price), `update_price` (item_id + price), `update_description` (item_id + description), `delete` (item_id). Encoding: utf-8-sig first, latin-1 fallback.

**DataTables:** Returns `{draw, recordsTotal, recordsFiltered, data}` with search across title/code/status/category, sortable by id/title/code/status/last_modified.

**Export:** Column sets for "Export Item Information", "Export Item Price", "Export Item Properties" matching old `simulate_export()`.

**Security:** All endpoints protected by `require_role("Admin")` — returns 401 if not authenticated, 403 if not admin.

**Verify:**
```bash
pytest tests/test_admin_products.py -v
# → 11 passed
pytest tests/ -v
# → 49 passed
```

---

### Step 10 — Admin Dashboard + Orders + Users (30-Jul)

**Created:**
| File | Purpose |
|------|---------|
| `app/routers/admin_dashboard.py` | Dashboard stats endpoint (sales, products, users, orders, categories) |
| `app/routers/admin_orders.py` | Order listing (all/pending/completed from punchout_orders) |
| `app/routers/admin_users.py` | User management (list/create/update) |
| `tests/test_admin_rest.py` | 8 tests |

**Endpoints:**
```
GET  /api/admin/dashboard          → {total_sales, total_products, total_users, total_orders, recent_orders, category_data}
GET  /api/admin/orders             → all punchout orders with items
GET  /api/admin/orders/pending     → pending orders
GET  /api/admin/orders/completed   → completed + shipped orders
GET  /api/admin/users              → list all users
POST /api/admin/users              → create user (username, email, password, role)
PUT  /api/admin/users/{id}         → update user (username, email, role, is_active, password)
```

**Security:** All endpoints protected by `require_role("Admin")`.

**Verify:**
```bash
pytest tests/ -v
# → 64 passed
```

**Created:**
| File | Purpose |
|------|---------|
| `app/models/order.py` | PunchOutOrder, PunchOutOrderItem (matches old `punchout_punchoutorder` + `punchout_punchoutorderitem`) |
| `app/schemas/order.py` | CheckoutRequest, CheckoutResponse, OrderRead, OrderItemRead |
| `app/services/checkout_service.py` | checkout logic, cXML generation via lxml, httpx POST to Ariba |
| `tests/test_checkout.py` | 4 tests: empty cart, standard, punchout, cXML structure |

**Endpoint:**
```
POST /api/cart/checkout
Body: {punchout_return_url?, buyer_cookie?}
→ {success, order: {id, items: [...], total_cost}, cxml_payload?, message}
```

**Checkout flow:**
1. Fetches cart for user/session (returns 400 if empty or not found)
2. Builds cXML `PunchOutOrderMessage` with lxml (proper DOCTYPE, Header, BuyerCookie, ItemIn per item)
3. Creates `PunchOutOrder` + `PunchOutOrderItem` DB records
4. If `punchout_return_url` provided: POSTs cXML to Ariba via httpx (non-blocking)
5. Clears cart items
6. Returns order confirmation with cXML payload

**cXML format:**
```xml
<?xml version='1.0' encoding='UTF-8'?>
<!DOCTYPE cXML SYSTEM "http://xml.cXML.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML payloadID="..." timestamp="..." version="1.2.014">
  <Header><From><To><Sender>
  <Message><PunchOutOrderMessage>
    <BuyerCookie>
    <PunchOutOrderMessageHeader operationAllowed="create"><Total><Money>
    <ItemIn quantity="N"><ItemID><SupplierPartID><ItemDetail><UnitPrice><Money><Description><UnitOfMeasure><Classification>
```

**Verify:**
```bash
pytest tests/ -v
# → 30 passed (4 checkout + 8 auth + 6 cart + 6 catalog + 5 S3 + 1 health)
```

**Known gaps vs old site (see 05-migration-gap-analysis.md):**
- ❌ PunchOut session metadata (is_punchout, return_url) not yet persisted across flows (Step 8)
- ❌ Old cart creates PunchOutOrder records differently (one per cart item) — ours creates one order with items
- ✅ cXML format matches old `punchout/views.py` (lxml, DOCTYPE, same element structure)
