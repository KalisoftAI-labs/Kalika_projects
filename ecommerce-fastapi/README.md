# Kalika E-Commerce FastAPI Backend API

## What is this?

New FastAPI backend for **kalikaindia.com** — a B2B e-commerce punchout catalog that connects with **SAP Ariba** procurement systems.

We're **migrating** from the old Django site (`ecommerce_project/`) to a single FastAPI backend (`ecommerce-fastapi/`).

---

## Folder Structure

```
Kalika_projects/
├── ecommerce_project/       ← OLD Django site (still running in production)
│   └── ecommerce/           Django + FastAPI hybrid
│       ├── catalog/         Public product browsing
│       ├── cart/            Shopping cart
│       ├── accounts/        User auth
│       ├── punchout/        SAP Ariba cXML integration
│       ├── chatbot/         Gemini AI chat
│       └── fastapi_app/     Admin panel (FastAPI)
│
└── ecommerce-fastapi/       ← NEW FastAPI backend (in development)
    └── app/
        ├── models/          Database models
        ├── routers/         API endpoints
        ├── services/        Business logic
        └── middleware/      Security
```

---

## What's Running

### Old Site (kalikaindia.com)
- **Nginx** → Django (Gunicorn) for public pages + FastAPI (Uvicorn) for admin
- PostgreSQL on EC2, images on AWS S3
- Still serving customers, running in parallel

### New API (localhost dev)
- Single FastAPI server, one `/api/*` prefix for everything
- Fresh PostgreSQL database (`ecom_fastapi_dev`) — no risk to prod data
- Same S3 bucket for images

---

## Current Progress (7/14 steps)

| Built | Next |
|-------|------|
| Products list, search, detail | PunchOut cXML setup |
| Categories with product previews | Admin CRUD + bulk CSV |
| S3 image URLs with caching | Admin orders/dashboard |
| JWT auth (login/register/refresh) | Security middleware |
| Cart (add/remove/update/checkout) | Chatbot + templates |
| Homepage rotation (9-min cycle) | Old DB data migration |
| cXML order generation + audit | |

---

## How to Run

```bash
cd ecommerce-fastapi
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

API docs at http://127.0.0.1:8000/docs

---

## Key Design Choices

- **Single API** — No separate `/admin` prefix; admin features are just role-gated endpoints
- **JWT auth** replaces Django sessions + old FastAPI session auth
- **Fresh DB** during development — old production DB untouched
- **Same S3 bucket** — images unaffected by migration
- **69% less code** for same backend logic (no Django boilerplate)

---

## Status

⚠️ **In development.** Old site keeps running. Switch over only after all 14 steps tested.
