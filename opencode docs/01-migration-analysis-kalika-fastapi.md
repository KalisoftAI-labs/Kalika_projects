# Kalika E-Commerce: Full Architecture Analysis & FastAPI Migration Plan

## 1. PROJECT OVERVIEW

**Current:** Hybrid Django 4.2.7 + FastAPI 0.116 + Starlette on EC2 (Ubuntu)
**Target:** Pure FastAPI backend (Cloud Run / containerized)
**Live:** kalikaindia.com — B2B punchout catalog for SAP Ariba procurement

### Stack

| Layer | Current | Target |
|-------|---------|--------|
| Public backend | Django (WSGI via Gunicorn) | FastAPI (ASGI via Uvicorn) |
| Admin backend | FastAPI (ASGI via Uvicorn) | Same (consolidated) |
| Database | PostgreSQL 18 (on EC2) | Cloud SQL (managed) |
| Images | AWS S3 (presigned URLs) | AWS S3 (keep) |
| Frontend | Django DTL + Tailwind + Alpine.js | Same HTML / Jinja2 |
| Admin UI | Jinja2 + DataTables + Chart.js | Same (keep) |
| AI | Google Gemini 2.0 Flash | Keep |
| Protocol | cXML 1.2.014 | Keep |
| Server | Nginx → Gunicorn + Uvicorn | Uvicorn (container) |

### How It's Served Today

```
Nginx (443/80)
  ├── /static/ → staticfiles/
  ├── /admin/ → Uvicorn :8001 (FastAPI admin)
  └── / → Gunicorn (Django public)
```

ASGI entrypoint (`ecommerce/asgi.py`) mounts:
- `/fastapi-admin` → FastAPI Starlette app
- `/` → Django WSGI app
- `/static` → static files

---

## 2. CODE INVENTORY

### Django Apps (5 apps, ~20 Python files)

| App | Files | LOC | Purpose |
|-----|-------|-----|---------|
| **catalog** | 7 | ~400 | Home, product list/detail, category filter, search, S3 images, context processors |
| **cart** | 4 | ~350 | Session-based cart (add/remove/update/checkout/thankyou) |
| **accounts** | 5 | ~120 | CustomUser (role, buyer_identifier), login/register/logout, forms |
| **punchout** | 5 | ~400 | cXML PunchOutSetupRequest parse, PunchOutOrderMessage build, audit trail |
| **chatbot** | 3 | ~80 | Gemini AI chat with session history |

**Django templates:** 14 HTML files (catalog: base, home, product_list, product_detail, cart, checkout, etc.)
**Django URL routes:** 20 public routes

### FastAPI Admin Panel (exists, will be consolidated)

| File | LOC | Purpose |
|------|-----|---------|
| `fastapi_app/app.py` | 2,402 | ALL admin routes (~50 endpoints), product CRUD, bulk CSV, export, S3 upload, auth |
| `fastapi_app/db.py` | 680 | Connection helpers, table creation, stats queries, user/product seed |
| `fastapi_app/dbtest2.py` | 350 | CSV product import script |
| `fastapi_app/static/styles.css` | ~600 | Admin styling |
| `fastapi_app/templates/` | 24 HTML | Admin Jinja2 templates |

### Shared Infrastructure

- **DB:** PostgreSQL with raw psycopg2 (NOT Django ORM in admin)
- **Tables:** `products`, `accounts_customuser`, `users`, `orders`, `punchout_responses`, `punchout_punchoutorder`, `punchout_punchoutorderitem`
- **S3:** boto3 for image upload + presigned URLs
- **Session:** Django DB-backed for public; Starlette SessionMiddleware for admin
- **Auth:** Django `authenticate()` for public; raw `accounts_customuser` password verify for admin
- **Cache:** Django LocMemCache (S3 URLs, homepage, rate limiting)
- **Middleware:** IP block, path traversal block, rate limit (20 req/min)

---

## 3. TOTAL MIGRATION SCOPE

| Category | Files | LOC | Reuse % | Effort |
|----------|-------|-----|---------|--------|
| Django views/routes | 15 | ~900 | 40% | Medium |
| Django models | 5 | ~125 | 60% | Low |
| Django templates | 14 | ~2,100 | 70% | Medium |
| Django config/middleware | 6 | ~400 | 80% | Low |
| FastAPI admin (app.py) | 1 | 2,402 | 70% | High |
| FastAPI DB helpers | 2 | 1,030 | 80% | Low |
| FastAPI templates | 24 | ~3,500 | 100% | None (keep) |
| FastAPI static CSS | 1 | ~600 | 100% | None (keep) |
| Root MD docs | 7 | ~1,700 | — | Reference |
| **Total** | **~75** | **~12,700** | **~65%** | — |

---

## 4. CRITICAL COMPLEXITY AREAS

### 4.1 PunchOut cXML Flow (HIGHEST RISK)

Exact SAP Ariba cXML 1.2.014 format must be preserved:

1. Ariba POSTs `cxml-urlencoded` to `/punchout/setup/`
2. Parse: `<SharedSecret>` verify, `<From><Identity>`, `<BuyerCookie>`, `<BrowserFormPost><URL>`
3. Get-or-create `CustomUser` by `buyer_identifier`
4. If `<ItemOut>` elements: edit mode — populate cart, immediately return
5. If setup mode: return `PunchOutSetupResponse` with `<StartPage><URL>`
6. Buyer shops → checkout → build `PunchOutOrderMessage` with `<ItemIn>` per cart item
7. POST cXML to Ariba return URL; log `PunchOutOrder` + `PunchOutOrderItem`

**Must NOT change:** XML structure, DOCTYPE, attribute names, namespace handling, DTD reference.

### 4.2 Auth Dual-System

- Django public: `django.contrib.auth` (password hashing, sessions, CSRF)
- FastAPI admin: raw `passlib.verify(password, hash)` against `accounts_customuser.password`
- Both must remain compatible with same `accounts_customuser` table
- **Migration target:** JWT (access + refresh tokens) for both public API and admin

### 4.3 Session Sharing

- Public cart uses Django session (DB-backed)
- PunchOut flow relies on Django session: `is_punchout`, `punchout_return_url`, `punchout_buyer_cookie`
- Admin uses Starlette SessionMiddleware (separate)
- **Migration target:** Stateless JWT for API; database sessions for cart if needed

### 4.4 S3 Presigned URLs

- Generated per-product with 1hr expiry
- Cached in dedicated `product_images` LocMemCache (10k entries, 1hr TTL)
- Fallback to default `noimage.jpg`
- Used extensively in catalog views, cart views, admin
- **Migration target:** Keep same logic as a utility service

---

## 5. DATABASE SCHEMA

### Tables to Migrate

| Table | Source | Rows | Notes |
|-------|--------|------|-------|
| `products` | DB + CSV import | ~2,000+ | Main catalog, ~28 columns |
| `accounts_customuser` | Django auth | ~10-50 | CustomUser with role, buyer_identifier |
| `users` | Raw SQL table | ~10-50 | For orders FK (parallel to accounts_customuser) |
| `orders` | Raw SQL table | ~100-500 | Order records, FK to users |
| `punchout_responses` | FastAPI admin | ~0-50 | cXML response audit |
| `punchout_punchoutorder` | Django model | ~100-1,000 | PunchOut order audit trail |
| `punchout_punchoutorderitem` | Django model | ~500-5,000 | Per-item punchout detail |
| `django_session` | Django | Variable | Can be dropped after migration |

### products Table (28 columns)

```sql
item_id (SERIAL PK), action, main_category, sub_categories, item_code (UNIQUE),
product_title, product_description, upc, brand, department, type, tag,
list_price (DECIMAL), price (DECIMAL), inventory (BIGINT), min_order_qty (BIGINT),
available, large_image, additional_images (JSON text), status,
last_modified (TIMESTAMP), lead_time, length, material_type,
sys_discount_group, sys_num_images, sys_product_type, unit_of_measure, unspsc
```

---

## 6. REUSABLE CODE (can copy with minimal changes)

1. **cXML generators** (`punchout/views.py:42-78`, `210-330`) — pure lxml XML building
2. **Product DB operations** (`fastapi_app/app.py:120-543`) — raw SQL, parameterized
3. **DB connection** (`fastapi_app/db.py:24-37`) — psycopg2 connection factory
4. **S3 upload + presigned URL** (`fastapi_app/app.py:52-99`, `catalog/views.py:80-96`)
5. **Admin HTML templates** (24 files) — already Jinja2
6. **Security middleware** (`middleware/security_middleware.py:109`) — pure logic
7. **Category/context building** (`catalog/context_processors.py`) — pure query logic
8. **Bulk CSV parsing** (`fastapi_app/app.py` bulk-modify sections)
9. **Chatbot Gemini** (`chatbot/views.py`) — model call + session history
