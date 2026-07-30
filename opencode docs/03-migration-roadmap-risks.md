# Migration Roadmap — Developer-First Phased Plan

> **Approach:** Build the new FastAPI backend step by step, starting with the simplest independent piece. Keep the old Django site running in parallel. Deploy to Cloud Run only after all backend features are built and tested.

---

## 1. TARGET PROJECT STRUCTURE

```
ecommerce-fastapi/                    # NEW project — sibling to old ecommerce/
├── app/
│   ├── __init__.py
│   ├── main.py                       # FastAPI app entry, lifespan
│   ├── config.py                     # Settings (pydantic-settings, reads .env)
│   ├── database.py                   # SQLAlchemy engine + session
│   │
│   ├── models/                       # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── product.py                # products table
│   │   ├── user.py                   # accounts_customuser + users
│   │   ├── cart.py                   # cart items (session-keyed)
│   │   ├── order.py                  # orders tables
│   │   └── punchout.py              # punchout audit tables
│   │
│   ├── schemas/                      # Pydantic request/response
│   │   ├── __init__.py
│   │   ├── product.py
│   │   ├── user.py
│   │   ├── cart.py
│   │   └── order.py
│   │
│   ├── routers/                      # API route modules
│   │   ├── __init__.py
│   │   ├── health.py                 # /api/health (always first)
│   │   ├── catalog.py                # Public product browsing
│   │   ├── auth.py                   # Register / Login / JWT
│   │   ├── cart.py                   # Cart CRUD
│   │   ├── admin_products.py         # Admin product management
│   │   ├── admin_orders.py           # Order views
│   │   ├── admin_users.py            # User management
│   │   ├── admin_dashboard.py        # Dashboard stats
│   │   ├── punchout.py               # cXML PunchOut
│   │   └── chatbot.py               # Gemini chat
│   │
│   ├── services/                     # Business logic
│   │   ├── __init__.py
│   │   ├── product_service.py        # Product CRUD, S3 URLs, search
│   │   ├── cart_service.py           # Cart operations
│   │   ├── auth_service.py           # Auth + JWT
│   │   ├── punchout_service.py       # cXML parse + generate
│   │   ├── export_service.py         # Background CSV export
│   │   ├── s3_service.py             # S3 upload + presigned URLs
│   │   └── chatbot_service.py        # Gemini API
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── security.py               # IP block, path block, rate limit
│   │
│   └── dependencies/
│       ├── __init__.py
│       ├── auth.py                   # get_current_user, require_role
│       └── db.py                     # get_db session
│
├── tests/                            # All tests
│   ├── conftest.py
│   ├── test_catalog.py
│   ├── test_auth.py
│   ├── test_cart.py
│   ├── test_punchout.py
│   ├── test_admin.py
│   └── test_middleware.py
│
├── scripts/                          # Utility scripts
│   ├── import_products.py            # CSV import
│   └── seed_data.py                  # Dev sample data
│
├── templates/                        # Jinja2 admin (from old fastapi_app/)
├── static/                           # Admin CSS
├── .env                              # DB creds, secrets
├── requirements.txt
├── Dockerfile                        # (for later Cloud Run)
└── README.md
```

---

## 2. DEVELOPMENT ORDER (Easiest First)

```
STEP 1   Project skeleton + health check          [1 day]
STEP 2   Catalog API (products + categories)      [3 days]
STEP 3   S3 image service                         [1 day]
STEP 4   Auth + users API                         [3 days]
STEP 5   Cart API                                 [3 days]
STEP 6   Admin product CRUD                       [3 days]
STEP 7   Admin orders + dashboard                 [2 days]
STEP 8   Admin users + middleware                 [2 days]
STEP 9   PunchOut cXML (HIGHEST RISK)             [5 days]
STEP 10  Chatbot                                  [1 day]
────────────────────────────────────────────────────────
        TOTAL BACKEND                            ~24 days
STEP 11  Frontend template integration            [5 days]
STEP 12  Security audit + hardening               [3 days]
STEP 13  Old DB data migration                    [2 days]
────────────────────────────────────────────────────────
        TOTAL FULL                               ~34 days
────────────────────────────────────────────────────────
FUTURE   Cloud Run deployment                     [when ready]
```

---

## 3. DETAILED STEP-BY-STEP

### STEP 1: Project Skeleton + Health Check

**Goal:** Have a running FastAPI server you can curl.

**Create:**
- `ecommerce-fastapi/app/main.py` — FastAPI app with one `/api/health` route
- `ecommerce-fastapi/app/config.py` — pydantic-settings reading `.env`
- `ecommerce-fastapi/app/database.py` — SQLAlchemy + asyncpg connection to **new** PostgreSQL database (e.g. `ecom_fastapi_dev`)
- `ecommerce-fastapi/requirements.txt`

**New DB (separate from old Django DB):**
```sql
CREATE DATABASE ecom_fastapi_dev;
CREATE USER fastapi_user WITH PASSWORD '...';
GRANT ALL PRIVILEGES ON DATABASE ecom_fastapi_dev TO fastapi_user;
```

**Test:**
```bash
curl http://127.0.0.1:8000/api/health
# → {"status": "ok", "db": "connected"}
```

**Files created:**
```
ecommerce-fastapi/app/main.py        ~20 lines
ecommerce-fastapi/app/config.py      ~40 lines
ecommerce-fastapi/app/database.py    ~30 lines
ecommerce-fastapi/app/__init__.py
ecommerce-fastapi/requirements.txt
ecommerce-fastapi/.env
```

---

### STEP 2: Catalog API (Products + Categories)

**Goal:** Public product browsing endpoints working against the new DB.

**Create:**
- `app/models/product.py` — SQLAlchemy Product model (mirror `products` table)
- `app/schemas/product.py` — Pydantic ProductRead, ProductList
- `app/services/product_service.py` — query functions
- `app/routers/catalog.py` — public endpoints
- `scripts/import_products.py` — copy subset of products from old DB to new DB

**Endpoints:**
```
GET  /api/catalog/products          → paginated list, search, sort
GET  /api/catalog/products/{id}     → single product detail
GET  /api/catalog/categories        → nested category tree
GET  /api/catalog/categories/{main} → products by main category
```

**Data Strategy:**
- Import ~50-100 sample products from old DB via a one-time script
- Use a fresh `products` table in the new DB (don't touch old DB yet)
- Schema identical to old `products` table (28 columns)

**Files created:**
```
app/models/__init__.py
app/models/product.py                     ~60 lines
app/schemas/__init__.py
app/schemas/product.py                    ~40 lines
app/services/__init__.py
app/services/product_service.py           ~150 lines
app/routers/__init__.py
app/routers/catalog.py                    ~100 lines
scripts/import_products.py                ~80 lines
```

**Test:**
```bash
# Start server
uvicorn app.main:app --reload

# Browse products
curl http://127.0.0.1:8000/api/catalog/products?limit=10

# Get single product
curl http://127.0.0.1:8000/api/catalog/products/1

# Categories
curl http://127.0.0.1:8000/api/catalog/categories

# Search
curl "http://127.0.0.1:8000/api/catalog/products?q=safety"

# pytest
pytest tests/test_catalog.py -v
```

---

### STEP 3: S3 Image Service

**Goal:** Product images served via S3 presigned URLs (same as old system).

**Create:**
- `app/services/s3_service.py` — `get_s3_presigned_url()`, `upload_to_s3()`
- Cache with in-memory dict (or aiocache) — 1hr TTL

**Reuse from old code:**
- `fastapi_app/app.py:52-99` (upload_image_to_s3)
- `catalog/views.py:80-96` (get_s3_presigned_url)

**Files created:**
```
app/services/s3_service.py           ~80 lines
```

**Test:**
```bash
curl http://127.0.0.1:8000/api/catalog/products/1
# → large_image should be a full presigned S3 URL
```

---

### STEP 4: Auth + Users API

**Goal:** Register, login (JWT), protected routes.

**Create:**
- `app/models/user.py` — User model (mirror `accounts_customuser`)
- `app/schemas/user.py` — UserCreate, UserRead, TokenResponse
- `app/services/auth_service.py` — JWT create/verify, password hashing (passlib, pbkdf2_sha256 — same as old)
- `app/dependencies/auth.py` — `get_current_user`, `require_role(role)`
- `app/routers/auth.py` — /api/auth/* endpoints

**Endpoints:**
```
POST /api/auth/register   → create user
POST /api/auth/login      → email+password → access_token + refresh_token
POST /api/auth/refresh    → refresh_token → new access_token
GET  /api/auth/me         → current user profile (requires auth)
```

**Password Compatibility:**
- Use same `passlib.context.CryptContext(schemes=["pbkdf2_sha256"])` as old `fastapi_app/app.py`
- This ensures users created by the old Django admin can still log in via new API

**Files created:**
```
app/models/user.py                    ~40 lines
app/schemas/user.py                   ~30 lines
app/services/auth_service.py          ~100 lines
app/dependencies/__init__.py
app/dependencies/auth.py              ~30 lines
app/dependencies/db.py                ~10 lines
app/routers/auth.py                   ~80 lines
```

**Test:**
```bash
# Register
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@test.com","password":"test123"}'

# Login
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'
# → {"access_token": "...", "token_type": "bearer"}

# Protected route
curl http://127.0.0.1:8000/api/auth/me \
  -H "Authorization: Bearer <token>"

# pytest
pytest tests/test_auth.py -v
```

---

### STEP 5: Cart API

**Goal:** Session-based shopping cart (same as old, but via API).

**Create:**
- `app/models/cart.py` — CartItem model (session_key, product_id, quantity)
- `app/schemas/cart.py` — CartItemCreate, CartResponse
- `app/services/cart_service.py` — add, remove, update, calculate totals
- `app/routers/cart.py` — cart endpoints

**Endpoints:**
```
GET    /api/cart                    → current cart (items, totals, S3 URLs)
POST   /api/cart/items             → {product_id, quantity} → add
PUT    /api/cart/items/{id}        → {quantity} → update
DELETE /api/cart/items/{id}        → remove
POST   /api/cart/checkout          → process (placeholder for now)
```

**Session Strategy:**
- Use a simple `cart_token` header (UUID) instead of Django sessions for now
- Later can swap to JWT-based cart when auth is integrated
- Or keep using Starlette SessionMiddleware for simplicity

**Files created:**
```
app/models/cart.py                    ~25 lines
app/schemas/cart.py                   ~20 lines
app/services/cart_service.py          ~100 lines
app/routers/cart.py                   ~80 lines
```

**Test:**
```bash
# Add to cart (token generated server-side or client provides)
curl -X POST http://127.0.0.1:8000/api/cart/items \
  -H "Content-Type: application/json" \
  -d '{"product_id":1, "quantity":2}'

# View cart
curl http://127.0.0.1:8000/api/cart

# pytest
pytest tests/test_cart.py -v
```

---

### STEP 6: Admin Product CRUD

**Goal:** Manage products via API (create, read, update, delete, bulk CSV).

**Create:**
- `app/routers/admin_products.py` — admin endpoints (JWT-protected, admin role required)
- Extend `app/services/product_service.py` — add, update, delete, bulk CSV

**Endpoints:**
```
GET    /api/admin/products            → paginated list (DataTables-compatible)
GET    /api/admin/products/{id}       → single product
POST   /api/admin/products            → create product
PUT    /api/admin/products/{id}       → update product
DELETE /api/admin/products/{id}       → delete product
POST   /api/admin/products/bulk       → CSV upload (add/update_price/update_description/delete)
GET    /api/admin/products/export     → export all products as CSV
```

**Reuse from old code:**
- `fastapi_app/app.py:120-543` — all product DB functions
- `fastapi_app/app.py:1213-1604` — bulk CSV parsing logic

**Tests:**
```bash
# Create (requires admin JWT)
curl -X POST http://127.0.0.1:8000/api/admin/products \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"product_title":"Test","item_code":"T-001","main_category":"Safety","price":99.99}'

# Bulk CSV
curl -X POST http://127.0.0.1:8000/api/admin/products/bulk \
  -H "Authorization: Bearer <admin_token>" \
  -F "file=@products.csv" \
  -F "modification_type=add"

# pytest
pytest tests/test_admin.py -v
```

---

### STEP 7: Admin Orders + Dashboard

**Goal:** Order listing, dashboard stats.

**Create:**
- `app/models/order.py` — Order model
- `app/routers/admin_orders.py` — /api/admin/orders/*
- `app/routers/admin_dashboard.py` — /api/admin/dashboard

**Endpoints:**
```
GET /api/admin/orders              → list (pending + completed)
GET /api/admin/orders/pending      → pending orders only
GET /api/admin/orders/completed    → completed orders only
GET /api/admin/dashboard           → stats: sales, products, users, pending orders, category breakdown
```

**Reuse from old code:**
- `fastapi_app/db.py:467-618` — stats queries (get_total_sales, get_product_count, etc.)
- `fastapi_app/app.py:1898-2028` — order listing queries

**Files created:**
```
app/models/order.py                   ~40 lines
app/routers/admin_orders.py           ~100 lines
app/routers/admin_dashboard.py        ~80 lines
```

**Test:**
```bash
curl http://127.0.0.1:8000/api/admin/dashboard \
  -H "Authorization: Bearer <admin_token>"
```

---

### STEP 8: Admin Users + Middleware

**Goal:** User management + security middleware.

**Create:**
- `app/routers/admin_users.py` — user CRUD
- `app/middleware/security.py` — IP block, path block, rate limit

**Endpoints:**
```
GET    /api/admin/users             → list all users
POST   /api/admin/users             → create user
PUT    /api/admin/users/{id}        → update user
```

**Middleware (port from old `middleware/security_middleware.py`):**
- Same `BLOCKED_IPS` set (22 IPs)
- Same `SUSPICIOUS_PATHS` patterns
- Rate limit: 20 requests/min on `/api/auth/`, `/api/admin/`, `/api/punchout/`
- Auto-block IP after 3 suspicious attempts (5min cache)

**Files created:**
```
app/routers/admin_users.py            ~80 lines
app/middleware/__init__.py
app/middleware/security.py            ~100 lines
```

**Test:**
```bash
# Middleware tests
pytest tests/test_middleware.py -v
# → known IP blocked
# → suspicious path blocked
# → rate limit exceeded after 21 requests
```

---

### STEP 9: PunchOut cXML ⚠️ (HIGHEST RISK)

**Goal:** Full SAP Ariba PunchOut flow — exact cXML compatibility.

**Create:**
- `app/services/punchout_service.py` — cXML parsing + generation
- `app/routers/punchout.py` — /api/punchout/* endpoints
- `tests/test_punchout.py` — snapshot tests

**Endpoints:**
```
POST /api/punchout/setup          → receive cxml-urlencoded → return cXML response
POST /api/punchout/return-cart    → build PunchOutOrderMessage → return XML
GET  /api/punchout/orders         → audit trail
GET  /api/punchout/orders/{id}    → single order detail
```

**Critical: Snapshot Tests**
Before writing code, capture the old Django cXML output:
```
# Save these from old Django:
- sample_setup_request.xml        (input from Ariba)
- expected_setup_response.xml     (Django output for above)
- expected_order_message.xml      (Django output for a sample cart)
```

Then write tests that assert FastAPI output matches exactly:
```python
def test_punchout_setup_response():
    result = punchout_service.generate_setup_response(sample_session)
    assert result == expected_setup_response  # byte-for-byte
```

**Reuse from old code (almost verbatim):**
- `punchout/views.py:23-40` — `_parse_cxml()` helper
- `punchout/views.py:42-78` — `_generate_punchout_setup_response()`
- `punchout/views.py:210-330` — `_prepare_and_return_cart_to_ariba()`
- `fastapi_app/app.py:300-401` — `parse_item_properties()`

**Files created:**
```
app/services/punchout_service.py      ~300 lines
app/routers/punchout.py               ~100 lines
tests/test_punchout.py                ~100 lines
tests/fixtures/sample_setup_request.xml
tests/fixtures/expected_setup_response.xml
tests/fixtures/expected_order_message.xml
```

**Test:**
```bash
pytest tests/test_punchout.py -v
# → ALL snapshot tests must pass
# → No cXML format deviation allowed
```

---

### STEP 10: Chatbot

**Goal:** Gemini API chat via API.

**Create:**
- `app/services/chatbot_service.py` — Gemini call with history
- `app/routers/chatbot.py` — /api/chatbot/* endpoints

**Endpoints:**
```
POST /api/chatbot/message   → {message} → Gemini → {response}
POST /api/chatbot/clear     → clear history
```

**Reuse from old code:**
- `chatbot/views.py` — almost verbatim, just swap Django session for JWT context

**Files created:**
```
app/services/chatbot_service.py       ~60 lines
app/routers/chatbot.py                ~40 lines
```

---

### STEP 11: React Frontend

**Goal:** Build React SPA(s) consuming the FastAPI backend.

All old Django templates (DTL + Jinja2) are replaced with React:
- **Public catalog:** product browsing, search, category navigation, cart, checkout
- **Admin panel:** dashboard, product CRUD, bulk CSV upload, orders, users

The API is already built and returns clean JSON. React consumes `GET/POST/PUT/DELETE /api/*` directly.

No Jinja2 server-rendered templates. The frontend is a standalone SPA (in a separate folder or subproject).

---

### STEP 12: Security Audit + Hardening

**Checklist:**
```
[ ] All endpoints behind JWT (except public catalog + health)
[ ] Admin endpoints require admin role check
[ ] SQL injection: all queries parameterized ✓ (already from old code)
[ ] cXML SharedSecret not logged
[ ] .env secrets excluded from git
[ ] Rate limiting on auth + admin + punchout
[ ] IP blocking for known attackers
[ ] CORS configured (not *)
[ ] Password hashing: pbkdf2_sha256 (same as old)
[ ] No hardcoded credentials
[ ] Session tokens expire
[ ] Input validation on all POST/PUT endpoints
[ ] File upload validation (CSV only for bulk)
[ ] Error messages don't leak internals
```

---

### STEP 13: Old DB Data Migration

**Goal:** Copy production data from old `ecom_prod_catalog` to new `ecom_fastapi_dev`.

**Tables to migrate:**
```
products                  → 2,000+ rows     (catalog)
accounts_customuser       → 10-50 rows      (users)
punchout_punchoutorder    → 0-1,000 rows    (audit)
punchout_punchoutorderitem → 0-5,000 rows   (audit)
```

**Script approach:**
```python
# scripts/migrate_from_old_db.py
# 1. Connect to old DB (ecom_prod_catalog)
# 2. Connect to new DB (ecom_fastapi_dev)
# 3. Copy products table
# 4. Copy users table (keep same password hashes)
# 5. Copy punchout audit tables
# 6. Verify row counts match
```

**Rollback:**
- Old DB stays untouched during development
- If new DB has issues, old site still runs
- Switch happens only after full testing

---

### FUTURE: Cloud Run Deployment

**When backend is complete and tested:**
```
[ ] Dockerfile
[ ] Cloud SQL PostgreSQL setup
[ ] Secrets in Secret Manager
[ ] Deploy to Cloud Run
[ ] DNS switch
[ ] Take old EC2 offline
```

**Not needed until the end — ignore during development.**

---

## 4. PARALLEL DEVELOPMENT STRATEGY

```
WEEK 1:                         |  OLD DJANGO SITE
  Dev 1: Step 1 (skeleton)      |  ┌──────────────────┐
  Dev 1: Step 2 (catalog)       |  │  Running as usual  │
  Dev 1: Step 3 (S3)            |  │  kalikaindia.com   │
                                |  │  Buyers shopping   │
WEEK 2:                         |  │  PunchOut working  │
  Dev 1: Step 4 (auth)          |  │  Admin panel up    │
  Dev 1: Step 5 (cart)          |  └──────────────────┘
                                |
WEEK 3:                         |  NEW FASTAPI (dev only)
  Dev 1: Step 6 (admin products)|  ┌──────────────────┐
  Dev 1: Step 7 (orders/dash)   |  │ 127.0.0.1:8000    │
  Dev 1: Step 8 (users/middle)  |  │ Dev DB, test data │
                                |  │ Not public yet    │
WEEK 4:                         |  └──────────────────┘
  Dev 1 + 2: Step 9 (punchout) |   ⚠️ Snapshot test
  Dev 1: Step 10 (chatbot)      |
                                |
WEEK 5:                         |  INTEGRATION
  Dev 1 + 2: Step 11 (templates)|  ┌──────────────────┐
  Dev 1: Step 12 (security)     |  │ Staging server    │
  Dev 1: Step 13 (data migrate) |  │ Full data, tests  │
                                |  └──────────────────┘
```

**Key principle:** The old Django site stays up and serving customers for the entire duration. The new FastAPI backend is built silently on the side. Only switch over when everything is tested.

---

## 5. SECURITY AT EACH STEP

| Step | Security Check | How |
|------|---------------|-----|
| 1 | No secrets in code | pydantic-settings reads .env only |
| 2 | SQL injection | All queries parameterized (SQLAlchemy) |
| 3 | S3 credential leak | No logging of keys; temp presigned URLs |
| 4 | Password hashing | passlib pbkdf2_sha256 (same as old Django) |
| 5 | Cart token hijacking | UUID tokens, HTTPS-only |
| 6 | Admin auth | JWT required, admin role check |
| 7 | Order data leak | Auth on all order endpoints |
| 8 | IP/rate blocking | Middleware unit-tested |
| 9 | cXML credential leak | SharedSecret not logged; input validated |
| 10 | Gemini API key safe | From .env, not exposed |
| 11 | XSS in templates | Jinja2 auto-escapes |
| 12 | Full audit | Checklist above |

---

## 6. DATABASE STRATEGY

**During development:**
```
New FastAPI DB: ecom_fastapi_dev (PostgreSQL, can be on same server)
  └─ Fresh tables, imported sample products
  └─ No risk to production data

Old Django DB: ecom_prod_catalog (PostgreSQL, on EC2)
  └─ Untouched. Keeps serving customers.
```

**At cutover time:**
```
1. Stop writes to old DB
2. Run migration script (copy all data)
3. Verify row counts
4. Switch DNS → new FastAPI server
5. Keep old DB read-only for 1 week (rollback window)
```

---

## 7. REUSABLE CODE LIST (Copy As-Is)

These functions need ZERO logic changes — just import path updates:

| Old File | Lines | Function | New Location |
|----------|-------|----------|-------------|
| `fastapi_app/app.py` | 52-99 | `upload_image_to_s3()` | `services/s3_service.py` |
| `fastapi_app/app.py` | 120-183 | `update_product_price_in_db()`, `update_product_description_in_db()` | `services/product_service.py` |
| `fastapi_app/app.py` | 183-298 | `add_product_to_db()`, `update_product_in_db()` | `services/product_service.py` |
| `fastapi_app/app.py` | 300-401 | `parse_item_properties()`, `bulk_modify_properties_post()` | `services/product_service.py` |
| `fastapi_app/app.py` | 402-543 | `delete_product_by_identifier()`, `get_product_by_identifier()` | `services/product_service.py` |
| `fastapi_app/app.py` | 546-671 | `simulate_export()`, `initiate_export()` | `services/export_service.py` |
| `fastapi_app/app.py` | 1213-1604 | Product update/add forms, bulk CSV | `routers/admin_products.py` |
| `fastapi_app/db.py` | 24-37 | `get_db_connection()` | `database.py` |
| `fastapi_app/db.py` | 467-618 | Stats queries | `services/product_service.py` |
| `catalog/views.py` | 80-96 | `get_s3_presigned_url()` | `services/s3_service.py` |
| `catalog/context_processors.py` | 16-51 | Category builder | `services/product_service.py` |
| `punchout/views.py` | 23-40 | `_parse_cxml()` | `services/punchout_service.py` |
| `punchout/views.py` | 42-78 | `_generate_punchout_setup_response()` | `services/punchout_service.py` |
| `punchout/views.py` | 210-330 | `_prepare_and_return_cart_to_ariba()` | `services/punchout_service.py` |
| `chatbot/views.py` | 21-62 | `chat_with_gemini()` | `services/chatbot_service.py` |
| `middleware/security_middleware.py` | 32-109 | SecurityMiddleware, RateLimitMiddleware | `middleware/security.py` |

**~2,000 lines of proven, production-tested code. Zero rewrite needed.**

---

## 8. DEVELOPMENT ORDER RATIONALE

Why this order (easiest → hardest):

| # | Step | Why This Order |
|---|------|---------------|
| 1 | Skeleton | Zero dependencies. Get server running first. |
| 2 | Catalog | Independent. Read-only. No auth needed. Immediate visible progress. |
| 3 | S3 | Extension of catalog. Same pattern, well-understood. |
| 4 | Auth | Needed by everything after this. But isolated enough to build alone. |
| 5 | Cart | Depends on auth (user/cart token). Light logic. |
| 6 | Admin products | Depends on auth. Reuses catalog product code. |
| 7 | Orders/Dashboard | Depends on auth + admin. Simple stats queries. |
| 8 | Users/Middleware | Depends on auth. Well-understood security logic. |
| 9 | PunchOut | **Most complex.** Saved for last when patterns are established. |
| 10 | Chatbot | Trivial. Independent API call. |

This order ensures:
- You have a working product (catalog) by day 4
- Each step builds on proven patterns from previous steps
- The hardest part (punchout) is tackled when you're most familiar with the codebase
- Old site never breaks — zero customer impact until final cutover
