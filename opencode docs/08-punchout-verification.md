# PunchOut Verification Guide — Test Locally Before Frontend/Deployment

> How to verify the SAP Ariba PunchOut integration works **without deploying**.
> Answer: YES, it's testable locally with realistic cXML — with one caveat (see §4).

---

## 1. WHAT CAN BE TESTED LOCALLY (100%)

| Flow | How | Tool |
|------|-----|------|
| Ariba → Us (Setup) | Craft realistic PunchOutSetupRequest cXML → POST to our API | `scripts/e2e_punchout.py` |
| Us → Ariba (Return cart) | Checkout POSTs PunchOutOrderMessage to a mock Ariba receiver | `scripts/mock_ariba.py` (port 9001) |
| **XML correctness** | Validate generated cXML against the **official cXML 1.2.014 DTD** from xml.cXML.org | `tests/fixtures/cXML.dtd` + `tests/test_dtd.py` |
| Business rules | BuyerCookie round-trip, SharedSecret, sender identity, totals, item count, UNSPSC | Mock Ariba's `_check_punchout_order_message` |

## 2. WHAT CANNOT BE TESTED WITHOUT DEPLOYMENT

| Flow | Why | When it works |
|------|-----|---------------|
| **Real Ariba-initiated PunchOut** | Ariba sends the SetupRequest from ITS network to a public URL. Localhost is unreachable. | After deployment (any URL) + Ariba test supplier registration (business process, not technical) |
| Ariba test environment (`open.test.ariba.com`) | Requires a test buyer org configured with our supplier credentials | Same as above |

**Bottom line:** the *protocol logic* is fully verifiable now. The only untestable part is Ariba's own network/browser handshake, which happens after deployment.

---

## 3. HOW TO RUN (3 terminals)

```bash
# Terminal 1 — our API
cd ecommerce-fastapi
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000

# Terminal 2 — mock Ariba (simulates the buyer side)
.\venv\Scripts\Activate.ps1
python -m scripts.mock_ariba          # listens on 9001

# Terminal 3 — run the full flow
python -m scripts.e2e_punchout
```

**Expected output (verified 31-Jul, 24/24 PASS):**

```
[1] Ariba -> Kalika: PunchOutSetupRequest
  [PASS] Setup endpoint responds 200
  [PASS] Response is XML
  [PASS] Response has DOCTYPE
  [PASS] Response has PunchOutSetupResponse
  [PASS] Response has StartPage URL
  [PASS] StartPage URL contains session id
[2] Buyer shops: adds items to cart
  [PASS] Add product 1 x2
  [PASS] Add product 6 x1
  [PASS] Cart has expected items
[3] Buyer checks out -> cXML POSTed to Ariba (mock)
  [PASS] Checkout succeeds
  [PASS] Order persisted with items
  [PASS] cXML payload returned
  [PASS] cXML has BuyerCookie round-trip
  [PASS] cXML has UNSPSC classification
[4] Mock Ariba validates received PunchOutOrderMessage
  [PASS] Ariba received the return POST
  [PASS] DTD valid (official cXML 1.2.014)
  [PASS] Version 1.2.014
  [PASS] BuyerCookie matches setup
  [PASS] Sender identity present
  [PASS] SharedSecret present
  [PASS] operationAllowed=create
  [PASS] Total money present
  [PASS] 2 items in message
  [PASS] All required fields complete
RESULT: 24 passed, 0 failed
```

---

## 4. WHAT THE DTD CHECK MEANS

- `tests/fixtures/cXML.dtd` is the **official DTD** downloaded from `xml.cXML.org/schemas/cXML/1.2.014/cXML.dtd` (131 KB, self-contained — no external refs).
- Ariba's parser validates incoming cXML against this DTD. **Our generated XML passing it means Ariba will accept the format.**
- Covered by `tests/test_dtd.py` in the normal pytest suite:
  ```bash
  pytest tests/test_dtd.py -v   # → 2 passed
  ```

---

## 5. ADDITIONAL REALISM CHECKS

- **Edit mode** (Ariba sends `<ItemOut>` with an existing requisition): covered in `tests/test_punchout.py::test_setup_endpoint_edit_mode`
- **Wrong SharedSecret** → 403: `test_setup_endpoint_missing_secret`
- **Malformed cXML** → 400: `test_setup_endpoint_invalid_cxml`
- **Sample CIF** (`ecommerce_project/ecommerce/kalika_punchout.cif`): the catalog file Ariba uses for supplier onboarding — item codes there can be cross-checked against our `products.item_code` values.

---

## 6. AFTER DEPLOYMENT (real Ariba test)

1. Point `PUNCHOUT_ANID`, `PUNCHOUT_SUPPLIER_DUNS`, `PUNCHOUT_SHARED_SECRET` in `.env` to the real Ariba test credentials
2. Give Ariba the public setup URL: `https://<domain>/api/punchout/setup`
3. Buyer in Ariba test clicks PunchOut → browser opens our StartPage URL
4. Buyer shops → checkout → Ariba receives PunchOutOrderMessage → requisition appears
5. Failures at this stage would be **credential/config issues, not protocol** — the protocol is proven by the local E2E + DTD validation
