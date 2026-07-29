# Migration Gap Analysis — Built vs Old Django Site

> Systematic comparison of what we've built vs what the old Django+FastAPI site actually does.
> Source: deep analysis of all 17 old Django/FastAPI source files.

---

## 1. COVERAGE SUMMARY

| Feature | Old Site | Our Build | Status |
|---------|----------|-----------|--------|
| Product model (29 columns) | ✅ | ✅ | **MATCH** |
| Products list paginated | ✅ | ✅ | **MATCH** |
| Product detail by ID | ✅ | ✅ | **MATCH** |
| Category tree (main→sub) | ✅ | ✅ | **OK** |
| Search (title/cat/subcat ILIKE) | ✅ | ✅ | **MATCH** |
| S3 presigned URL + cache | ✅ | ✅ | **MATCH** |
| User model (accounts_customuser) | ✅ | ✅ | **MATCH** |
| JWT login/register/refresh | ❌ (session) | ✅ | **BETTER** |
| Cart CRUD (add/remove/update) | ✅ | ✅ | **OK** |
| **Homepage rotation (9-min cycle)** | ✅ | ❌ | **MISSING** |
| **Featured products** | ✅ | ❌ | **MISSING** |
| **Hero video S3 URL** | ✅ | ❌ | **MISSING** |
| **Category: 5 product previews** | ✅ | ❌ (counts only) | **GAP** |
| **Category: main_category__icontains** | ✅ | ❌ (exact match) | **GAP** |
| **Cart checkout (dual path)** | ✅ | ❌ | **MISSING** |
| **Cart: AJAX quantity update** | ✅ | ❌ | **MISSING** |
| **PunchOut cXML (setup + return)** | ✅ | ❌ | **MISSING** |
| **Admin: product CRUD** | ✅ | ❌ | **MISSING** |
| **Admin: bulk CSV import (4 modes)** | ✅ | ❌ | **MISSING** |
| **Admin: background CSV export** | ✅ | ❌ | **MISSING** |
| **Admin: DataTables server-side** | ✅ | ❌ | **MISSING** |
| **Admin: orders/dashboard/users** | ✅ | ❌ | **MISSING** |
| **Admin: nested categories (sub-sub)** | ✅ | ❌ | **MISSING** |
| **Security middleware (22 IPs)** | ✅ | ❌ | **MISSING** |
| **Rate limiting (20 req/min)** | ✅ | ❌ | **MISSING** |
| **Chatbot (Gemini)** | ✅ | ❌ | **MISSING** |
| **Templates (36 HTML files)** | ✅ | ❌ | **MISSING** |

---

## 2. DETAILED GAP ANALYSIS

### 2.1 Homepage — Time-Based Product Rotation

**Old code:** `catalog/views.py:home()`

```python
current_minute = int(time.time() // 60)
offset = ((current_minute // 9) * 9) % max(1, total)
```

- Products rotate every **9 minutes** with a sliding window of 10
- Uses `main_category__icontains=category.split(" ")[0]` (first word ONLY, fuzzy match)
- Excludes products with `noimage.jpg` in large_image
- All categories collected into single list → S3 URLs batch-processed once
- Featured products = first 10 from "Hand & Power Tools"
- **Hero video:** S3 presigned URL for `/kalika-images/kalika-ad1.mp4`, cached 3000s
- Homepage cache key: `homepage_products_v2`, TTL 300s
- Calls `build_category_context()` for menu data

**What we built:** Basic `/api/catalog/products` list. No rotation, no featured, no hero video.

**Fix needed:** New endpoint `GET /api/catalog/home` implementing:
- Time-based offset rotation (9-min cycle)
- Fuzzy `main_category` match (first word `icontains`)
- N products per category with window+wrap
- Hero video S3 URL
- Batch S3 URL enrichment for all returned products
- Response caching

---

### 2.2 Category Tree — Missing Product Previews

**Old code:** `catalog/context_processors.py:categories()` + `catalog/views.py:build_category_context()`

```python
products = Product.objects.filter(
    main_category=main_cat,
    sub_categories=sub_cat_name
).values('item_id', 'product_title')[:5]
```

Each subcategory includes **up to 5 products** (id + title only) used in the header dropdown menu. Counts are pre-computed separately.

**What we built:** Category tree with counts only, no product previews.

---

### 2.3 Cart — Missing Checkout Flow

**Old code:** `cart/views.py:checkout()` (160+ lines)

**Two checkout paths in old Django:**

**Path A — PunchOut checkout (session has `is_punchout=True`):**
- Builds `PunchOutOrderMessage` cXML using `xml.etree.ElementTree`
- Same cXML format as punchout views but uses `xml.etree.ElementTree` NOT `lxml`
- Creates `PunchOutOrder` records (one per cart item, all with same UUID `order_id`)
- POSTs cXML to Ariba return URL via `requests.post()`
- On success (200): deletes cart, clears punchout session flags, redirects to Ariba URL
- On failure: shows error, stays on cart

**Path B — Standard checkout:**
- Uses `proceed_to_thankyou` → clears cart → redirects to `/cart/thankyou/`

**Cart session management:**
- All cart items keyed by `request.session.session_key` (Django session)
- Creates session lazily: `request.session.create()` if missing
- AJAX support: `x-requested-with: XMLHttpRequest` header check
- **AJAX quantity update:** JSON body `{item_id, quantity}`, returns `{new_subtotal, new_total}`
- Subtotals computed via `CartItem.subtotal` model property (`quantity * product.price`)

**What we built:** Basic add/remove/update. No checkout logic, no cXML, no dual-path.

---

### 2.4 PunchOut cXML — Entirely Missing (HIGHEST RISK)

**Old code:** `punchout/views.py` (330 lines) — **CRITICAL BUSINESS LOGIC**

**Complete flow documented in `02-business-domains-workflows.md` §4.**

Key details not in our plan:

**Setup request parsing quirks:**
- XPath queries use `.//` prefix WITHOUT namespace mapping — this is actually a **bug** in the old code (would fail on properly namespaced cXML)
- `_get_cxml_text` uses `root.find(path).text` — fragile, no error handling for missing child elements
- `_parse_cxml` encodes string to UTF-8 before parsing

**Edit/Inspect mode:**
- `<ItemOut>` elements trigger immediate cart population + return to Ariba (no browsing)
- Products matched by `item_code` from `<SupplierPartID>`
- Missing products are logged and skipped (partial cart)

**Return cart:**
- Uses `lxml.etree` (not `xml.etree.ElementTree` which is used in cart/views.py checkout — **inconsistent!**)
- DOCTYPE declaration: `<!DOCTYPE cXML SYSTEM "http://xml.cXML.org/schemas/cXML/1.2.014/cXML.dtd">`
- `<Sender>` identity: `settings.PUNCHOUT_SUPPLIER_DUNS` or fallback `'kalikaindia.com'`
- `<SharedSecret>` only included if `settings.PUNCHOUT_SHARED_SECRET` is truthy
- `<Description xml:lang="en">` — includes XML `lang` attribute
- Renders `return_to_ariba.html` with hidden auto-submit form

**Audit logging:** Creates `PunchOutOrder` (1 per order) + `PunchOutOrderItem` (1 per cart item) records

**Session cleanup:** `cart_items.delete()` + `request.session.flush()` — destroys ALL session data

---

### 2.5 Admin Panel — Bulk CSV Import

**Old code:** `fastapi_app/app.py` bulk-modify routes (~400 lines)

**Four CSV import modes with detailed logic:**

1. **`add`:** Required fields `[main_category, item_code, product_title, price]`. Builds dict from 26-column master list. Special handling for `additional_images` (JSON validate→serialize) and `type` (Python keyword). Raw CSV keys cleaned: strip, spaces→underscores, BOM-remove, lowercase.

2. **`update_price`:** Reads `item_id` and `price`. Price defaults to `0.0` if missing/empty. No other fields updated.

3. **`update_description`:** Reads `item_id` and `product_description`. Description defaults to `""` if None.

4. **`delete`:** Reads `item_id`, calls `delete_product_by_identifier()`

**Second CSV endpoint (`bulk-modify-properties-column`):**
- Has explicit `header_map` mapping user-friendly column headers to DB columns
- Supports actions: `add`, `add/edit`, `update`, `delete`
- `add/edit` = upsert: if item_code exists → update, else → add
- Parses special `Item Properties` column (key-value pairs split by `, ` then ` - `)

**CSV parsing strategy:**
- Decode with `utf-8-sig` first, fallback to `latin-1`
- CSV errors caught per-row, not per-file

---

### 2.6 Admin Panel — Background Export

**Old code:** `fastapi_app/app.py` export routes (~200 lines)

- In-memory job store (`export_jobs` list, lost on restart)
- `simulate_export()` runs in `threading.Thread`
- Uses `pandas.read_sql_query()` to fetch data
- Three export options: "Export Item Information", "Export Item Price", "Export Item Properties"
- Each option maps to specific columns
- Output: CSV at `static/exports/export_{job_id}.csv`
- Download via `/admin-static/exports/export_{job_id}.csv`
- Job statuses: `Doing Job` → `Success` or `Failed`

---

### 2.7 Admin Panel — DataTables Server-Side

**Old code:** `fastapi_app/app.py:/api/products-list`

Parameters: `draw`, `start`, `length`, `search[value]`, `order[0][column]`, `order[0][dir]`
Search columns: `product_title`, `item_code`, `status`, `main_category` (all ILIKE)
Sortable: `item_id`, `product_title`, `item_code`, `status`, `last_modified`
Response: `{draw, recordsTotal, recordsFiltered, data: [items]}`

---

### 2.8 Admin Panel — Orders Queries

**Old code:** `fastapi_app/app.py` pending_orders + completed_orders

```sql
-- Pending orders:
SELECT o.order_id, au.username AS customer_name, p.product_title,
       o.quantity, o.item_price, o.order_date, o.status
FROM orders o
JOIN accounts_customuser au ON o.user_id = au.id
JOIN products p ON o.product_id = p.item_id
WHERE o.status = 'Pending'
ORDER BY o.order_date DESC;

-- Completed orders (same query, different status):
WHERE o.status = 'Completed' OR o.status = 'Shipped'
```

---

### 2.9 Security Middleware

**Old code:** `middleware/security_middleware.py` (109 lines)

**22 hardcoded blocked IPs:**
```
216.180.246.246, 216.180.246.248, 216.180.246.201, 185.177.72.38,
4.190.210.95, 20.192.24.172, 20.89.17.172, 167.172.95.178,
141.98.11.98, 34.72.138.173, 87.121.84.125, 168.76.20.229
```

**Suspicious paths (blocked immediately):**
```
.env, .git, phpinfo.php, info.php, config.php, adminer.php,
sql.conf, db.conf, .ini, .bak, login.asp, ultra.php,
function.php, /root/.aws
```

**Rate limit:** 20 requests/min on `/admin/`, `/accounts/login/`, `/punchout/`

**Auto-block:** 3+ suspicious path attempts → IP added to blocked set (runtime only)

---

## 3. OLD CODE BUGS WE SHOULD NOT REPLICATE

| # | Old Bug | Impact | Our Fix |
|---|---------|--------|---------|
| 1 | `SessionMiddleware(secret_key=os.getenv(SECRET_KEY))` — variable not string | Auth broken | Already fixed: `settings.SECRET_KEY` |
| 2 | `_get_cxml_text` uses `find()` without namespace namespaces | cXML parse fails silently | Use proper namespace-ignoring XPath via `lxml` |
| 3 | `build_category_context()` has dead query `products_for_categories` never used | Wasted DB query | Never had this |
| 4 | `context_processors.py` runs 50+ DB queries per page | Slow page loads | Build once, cache |
| 5 | `db.py` drops `orders` table on every execution | Data loss risk | Will use migrations |
| 6 | Two user tables (`users` + `accounts_customuser`) with same data | Sync issues | Single user table |
| 7 | In-memory export jobs lost on restart | User sees lost exports | DB-backed job store |
| 8 | No CSRF on FastAPI admin forms | CSRF vulnerability | JWT already protects |
| 9 | Cart checkout uses different XML lib (`xml.etree`) than punchout (`lxml`) | Inconsistent output | Use lxml everywhere |
| 10 | PUNCHOUT_SHARED_SECRET compared with `!=` (not constant-time) | Timing attack risk | Use `compare_digest` |

---

## 4. WHAT TO PRIORITIZE NEXT

### Must-Have for Functional Equivalence

```
Priority 1 (customer-facing):
  [ ] Homepage rotation + featured products + hero video
  [ ] Category product previews (5 per subcategory)
  [ ] Cart checkout (dual path: punchout + standard)
  [ ] AJAX quantity update endpoint

Priority 2 (Ariba integration):
  [ ] PunchOut setup endpoint (cXML parse + response)
  [ ] PunchOut return cart (cXML order message)
  [ ] PunchOutOrder audit logging

Priority 3 (admin operations):
  [ ] Product CRUD (create/update/delete by id/code)
  [ ] Bulk CSV import (4 modes: add/price/desc/delete)
  [ ] DataTables server-side endpoint
  [ ] Orders list (pending + completed)
  [ ] Dashboard stats
  [ ] User CRUD
  [ ] Background CSV export

Priority 4 (infrastructure):
  [ ] Security middleware (IP block, path block, rate limit)
  [ ] Chatbot (Gemini)
  [ ] Templates (36 HTML files)
```

### Current Build Gaps (line-by-line)

| Our File | Lines | Should Be | Missing LOC |
|----------|-------|-----------|-------------|
| `routers/catalog.py` | 44 | 100+ | Homepage rotation, featured, video, category previews |
| `services/product_service.py` | 100 | 200+ | Homepage logic, rotation math, batch S3 enrichment |
| `routers/cart.py` | 55 | 150+ | Checkout dual-path, AJAX quantity |
| `services/cart_service.py` | 100 | 200+ | Checkout logic, cXML generation, order creation |
| Not built | 0 | 330 | `routers/punchout.py` + `services/punchout_service.py` |
| Not built | 0 | 400 | `routers/admin_products.py` (CRUD + bulk CSV + DataTables) |
| Not built | 0 | 200 | `routers/admin_orders.py` + `routers/admin_dashboard.py` |
| Not built | 0 | 80 | `routers/admin_users.py` |
| Not built | 0 | 100 | `middleware/security.py` |
| Not built | 0 | 80 | `routers/chatbot.py` + `services/chatbot_service.py` |
| Not built | 0 | 36 files | HTML templates (Django DTL → Jinja2) |
