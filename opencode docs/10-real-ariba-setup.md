# Real SAP Ariba PunchOut — What It Takes

> Everything else (protocol, XML, DTD, flows) is verified locally. This doc covers
> the ONLY remaining step: connecting real Ariba. It's a business + credential
> process, not code.

---

## 1. THE REAL ARIRA WIRE FORMAT (now tested)

Real Ariba does **not** post raw XML. It sends:

```
POST https://<your-domain>/api/punchout/setup
Content-Type: application/x-www-form-urlencoded
body: cxml-urlencoded=<URL-encoded cXML>
```

Covered by `tests/test_ariba_wire.py` (5 tests, all PASS):
- form-encoded payload ✅
- double-URL-encoded value (proxy-safe) ✅ — **bug found & fixed here**
- edit mode over the wire format ✅
- wrong SharedSecret → 403 ✅
- missing field → 400 ✅

---

## 2. WHAT ARIBA NEEDS FROM US (supplier setup)

| Item | Value (current .env) | Status |
|------|---------------------|--------|
| Setup URL (PunchOut entry) | `https://<domain>/api/punchout/setup` | needs public URL |
| ANID (Ariba Network ID) | `AN01284122159-T` | `-T` suffix = test env — **verify with Ariba** |
| Supplier DUNS | `651009354` | **verify with Ariba** |
| SharedSecret | `test-secret` (dev) | **must be replaced with real Ariba-issued value** |
| Catalog file (CIF) | `kalika_punchout.cif` (old project) | regenerate for new product set |

---

## 3. THE BLOCKERS (in order)

### 3.1 Ariba test supplier registration — BUSINESS PROCESS
This is the actual gate. Steps:
1. Register as a supplier on **Ariba Discovery** (ariba.com)
2. Request a **test ANID + test credentials** (ANID, DUNS, SharedSecret) for the Ariba test network
3. Ariba provides: test ANID, test network SharedSecret, buyer test org to use
4. Time: days–weeks (Ariba onboarding process, may involve a partner/CSM)

**Until this exists, no deployment helps** — Ariba has no credentials to call us with.

### 3.2 Public URL — TECHNICAL (fast once 3.1 exists)
Ariba must reach our setup endpoint from its network:
- Deployed server (EC2/Cloud Run/any public host), **or**
- Tunnel (ngrok/cloudflared) for short test sessions

The StartPage URL we return must ALSO be publicly reachable (buyer's browser opens it):
`https://<public-domain>/?punchout_session=<id>` — this requires the frontend/public
catalog to be served at that domain too.

### 3.3 Buyer side — BUSINESS PROCESS
A buyer org in the Ariba test environment must:
- Enable our catalog (via the CIF upload or punchout test configuration)
- Have a test buyer user who clicks "PunchOut" to our setup URL

---

## 4. CHECKLIST — READY FOR REAL ARIBA TEST

```
[ ] Ariba test supplier registration done (ANID/DUNS/SharedSecret from Ariba)
[ ] .env updated with REAL test credentials:
      PUNCHOUT_ANID=<real-test-anid>
      PUNCHOUT_SUPPLIER_DUNS=<real-duns>
      PUNCHOUT_SHARED_SECRET=<real-shared-secret>
[ ] Public URL for /api/punchout/setup (deploy or tunnel)
[ ] Public URL for the buyer's StartPage (frontend deployed)
[ ] CIF uploaded / catalog configured in Ariba test buyer org
[ ] Test buyer created in Ariba test org
[ ] Run e2e against the PUBLIC URL (not localhost) to confirm
```

---

## 5. WHAT'S PROVEN vs WHAT REMAINS

| Layer | Status |
|-------|--------|
| cXML format (DTD-valid) | ✅ proven |
| Wire format (form-encoded, urlencoded) | ✅ proven (5 tests) |
| Full flow logic (setup → shop → return) | ✅ proven (24/24 E2E) |
| Error paths (bad secret, malformed, missing) | ✅ proven |
| Real Ariba network handshake | ❌ needs registration + public URL |

**Post-registration risk is limited to credentials/config** — protocol is done.
