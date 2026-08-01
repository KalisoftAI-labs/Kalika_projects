# Testing Guide — ecommerce-fastapi

> How to run every test in the project, what each suite covers, and how to verify critical flows.

---

## 1. Quick Start

```bash
cd ecommerce-fastapi

# All tests (72 passing)
.\venv\Scripts\pytest.exe tests/ -v

# Single suite
.\venv\Scripts\pytest.exe tests/test_punchout.py -v

# Single test
.\venv\Scripts\pytest.exe tests/test_cart.py::test_add_to_cart_anonymous -v
```

Requires: PostgreSQL running (`ecom_fastapi_dev` DB) — tests hit the real dev database.

---

## 2. Test Suites Overview

| Suite | File | Tests | What it verifies |
|-------|------|-------|------------------|
| Health | `test_health.py` | 1 | API + DB connectivity |
| Catalog | `test_catalog.py` | 6 | Product list, search, detail, 404, categories, homepage |
| S3 | `test_s3.py` | 5 | Presigned URL, upload, fallback, enrichment (mocked boto3) |
| Auth | `test_auth.py` | 8 | Register, duplicate, login, wrong password, admin login, /me, refresh |
| Cart | `test_cart.py` | 6 | Add/get/update/remove/empty/authenticated cart |
| Checkout | `test_checkout.py` | 4 | Empty cart, standard checkout, punchout checkout, cXML structure |
| PunchOut | `test_punchout.py` | 8 | cXML parse, setup response, edit mode, wrong secret, invalid cXML |
| **DTD** | `test_dtd.py` | 2 | **Generated cXML validates against official cXML 1.2.014 DTD** |
| Admin products | `test_admin_products.py` | 11 | CRUD, bulk CSV (add/update/delete), DataTables, export, auth guard |
| Admin rest | `test_admin_rest.py` | 8 | Dashboard, orders (all/pending/completed), users CRUD |
| Chatbot | `test_chatbot.py` | 6 | Message, continuity, empty, validation, clear, no API key |
| Security | `test_security.py` | 7 | Blocked IPs, suspicious paths, rate limit (auto-reset between tests) |
| **Total** | | **72** | |

---

## 3. PunchOut Verification (pre-deployment)

The critical flow — simulates SAP Ariba end-to-end locally. **24 checks, all PASS.**

```bash
# Terminal 1 — our API
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000

# Terminal 2 — mock Ariba (simulates buyer side)
.\venv\Scripts\Activate.ps1
python -m scripts.mock_ariba          # port 9001

# Terminal 3 — full flow
python -m scripts.e2e_punchout
```

What it does:
1. Sends realistic `PunchOutSetupRequest` cXML → expects SetupResponse + StartPage URL
2. Extracts session id from StartPage
3. Adds 2 products to cart using session as cart token
4. Checks out with return URL → mock Ariba
5. Mock Ariba validates: **official DTD**, version 1.2.014, BuyerCookie round-trip, SharedSecret, sender identity, totals, item count

```bash
# DTD validation alone (2 tests, also in pytest suite)
.\venv\Scripts\pytest.exe tests/test_dtd.py -v
```

---

## 4. Security Tests

```bash
.\venv\Scripts\pytest.exe tests/test_security.py -v
```

Covers:
- 12 known malicious IPs → 403 (via `X-Forwarded-For` header)
- Suspicious paths (`.env`, `.git`, `phpinfo.php`) → 403
- 14 suspicious path patterns defined
- Auto-block: 3 suspicious attempts → IP runtime-blocked
- Rate limit: 20 req/min on `/api/auth/`, `/api/admin/`, `/api/punchout/`

Note: `conftest.py` auto-resets security state (blocked sets, counters) between tests.

---

## 5. Admin Flow Tests

```bash
.\venv\Scripts\pytest.exe tests/test_admin_products.py tests/test_admin_rest.py -v
```

Covers:
- 401 without token, admin-role gating
- Product CRUD (create → update → delete)
- Bulk CSV: add 2 items, update price, delete by id
- DataTables: `draw/start/length/search/order` contract
- CSV export with headers
- Dashboard stats, orders lists, user create/update

---

## 6. Test Data Notes

- Tests share the dev DB (`ecom_fastapi_dev`) — no isolation per test
- Admin tests create their own products/users with timestamped codes (never touch seed data)
- Seed data: `python -m scripts.import_products` (10 sample products) + `python -m scripts.seed_users` (admin/testuser)
- `conftest.py` resets security middleware state between tests
- `asyncio_mode = auto` + session-scoped event loop in `pyproject.toml`

---

## 7. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `relation "xxx" does not exist` | Run `python -m scripts.create_tables` |
| Missing sample products | `python -m scripts.import_products` |
| `No module named scripts` | Run from project root with `python -m scripts.<name>` |
| Auth tests fail | Re-run `python -m scripts.seed_users` (admin/testuser) |
| Rate limit 429 in manual testing | Wait 60s or restart server (in-memory counters) |
| Port conflicts | Mock Ariba = 9001, API = 8000; change ports in `e2e_punchout.py` if needed |
