# React Frontend Plan — ecommerce-react

> Step 13: Build a standalone React SPA consuming the FastAPI backend at `/api/*`.
> No server-rendered templates — the API is the single source of truth.

---

## 1. DECISION

**Two frontends in one React app:**

| Area | Path prefix | Auth |
|------|-------------|------|
| Public catalog | `/` (home, products, cart, checkout) | None (cart via token) |
| Admin panel | `/admin/*` | JWT + role=Admin required |

Single Vite + React + TypeScript app, two route groups.

---

## 2. TECH STACK

| Tool | Why |
|------|-----|
| Vite | Fast dev server, dev proxy to API |
| React 18 + TypeScript | Type safety for API responses |
| react-router-dom v6 | Routing (public + admin) |
| Tailwind CSS | Styling (same as old site look) |
| TanStack Query | Server state: caching, retry, invalidation |
| axios (or fetch) | API calls with JWT interceptors |
| Chart.js | Dashboard charts (same as old admin) |
| react-data-table-component (or AG Grid) | Admin product table (DataTables replacement) |

---

## 3. FOLDER STRUCTURE

```
ecommerce-react/
├── src/
│   ├── main.tsx                # App entry + Router
│   ├── App.tsx                 # Route definitions
│   │
│   ├── api/
│   │   ├── client.ts           # axios instance + baseURL + auth interceptor
│   │   ├── auth.ts             # login/register/refresh/me
│   │   ├── catalog.ts          # products, categories, homepage, search
│   │   ├── cart.ts             # cart CRUD + checkout
│   │   ├── admin.ts            # admin products/users/orders/dashboard
│   │   └── chatbot.ts          # chat message + clear
│   │
│   ├── auth/
│   │   ├── AuthContext.tsx     # token state, login/logout, role
│   │   └── ProtectedRoute.tsx  # redirect if not admin
│   │
│   ├── pages/                  # Public pages
│   │   ├── HomePage.tsx        # rotation products, hero video, featured
│   │   ├── ProductListPage.tsx # all products + search + pagination
│   │   ├── ProductDetailPage.tsx
│   │   ├── CategoryPage.tsx    # main + sub category
│   │   ├── CartPage.tsx        # cart items, quantity update, totals
│   │   ├── CheckoutPage.tsx    # standard or punchout return
│   │   ├── LoginPage.tsx
│   │   └── RegisterPage.tsx
│   │
│   ├── admin/                  # Admin pages (protected)
│   │   ├── AdminLayout.tsx     # sidebar nav + guard
│   │   ├── DashboardPage.tsx   # stats + Chart.js
│   │   ├── ProductsPage.tsx    # table + search + CRUD modal
│   │   ├── ProductEditPage.tsx # full form (29 fields) + image upload
│   │   ├── BulkImportPage.tsx  # CSV upload (4 modes)
│   │   ├── OrdersPage.tsx      # pending/completed lists
│   │   └── UsersPage.tsx       # user CRUD
│   │
│   ├── components/
│   │   ├── Header.tsx          # nav + cart badge + login state
│   │   ├── CategoryNav.tsx     # dropdown menu (10 cats + previews)
│   │   ├── ProductCard.tsx     # image, title, price, add-to-cart
│   │   ├── ChatWidget.tsx      # floating chatbot
│   │   └── Footer.tsx
│   │
│   ├── hooks/
│   │   ├── useCart.ts          # cart state + X-Cart-Token handling
│   │   └── useAuth.ts
│   │
│   └── utils/
│       └── currency.ts         # INR formatting
│
├── public/
├── package.json
├── tsconfig.json
├── vite.config.ts              # proxy /api → http://localhost:8000
└── tailwind.config.js
```

---

## 4. API INTEGRATION MAP

### Public endpoints used

| Page | Endpoint |
|------|----------|
| Home | `GET /api/catalog/home` |
| Product list | `GET /api/catalog/products?page=&search=` |
| Product detail | `GET /api/catalog/products/{id}` |
| Category | `GET /api/catalog/categories/{main}` |
| Search | `GET /api/catalog/products?search=` |
| Cart | `GET/POST/PUT/DELETE /api/cart/*` |
| Checkout | `POST /api/cart/checkout` |
| Login/Register | `POST /api/auth/*` |
| Chatbot | `POST /api/chatbot/*` |

### Admin endpoints used

| Page | Endpoint |
|------|----------|
| Dashboard | `GET /api/admin/dashboard` |
| Products table | `GET /api/admin/products/datatables?draw=&start=&length=` |
| Product CRUD | `GET/POST/PUT/DELETE /api/admin/products*` |
| Bulk import | `POST /api/admin/products/bulk` |
| Export | `GET /api/admin/products/export/csv` |
| Orders | `GET /api/admin/orders*` |
| Users | `GET/POST/PUT /api/admin/users*` |

---

## 5. KEY IMPLEMENTATION DETAILS

### Cart token handling (anonymous)
- On first add-to-cart: API returns `cart_token`
- Store in `localStorage` → send as `X-Cart-Token` header on all cart calls
- On login: optionally merge anonymous cart to user cart

### JWT handling
- `access_token` in memory + `refresh_token` in localStorage
- axios interceptor: attach `Authorization: Bearer` header
- On 401: try refresh → retry request; else redirect to `/login`
- Admin routes guarded by `ProtectedRoute` checking `role === "Admin"`

### PunchOut flow (critical)
- `POST /api/punchout/setup` is called **by Ariba**, not by the browser
- Buyer enters via StartPage URL: `https://site/?punchout_session={id}`
- Frontend reads `punchout_session` query param → uses it as cart token (`X-Cart-Token`)
- Checkout sends `{punchout_return_url, buyer_cookie}` from session data
- Edit mode: Ariba sends ItemOut → our API populates cart → browser opens → buyer reviews → checkout returns

### Homepage
- Render `products_by_category` sections (max 10 each)
- Hero video from `hero_video_url`
- Featured from `featured_products`
- Category nav from `categories` (10 cats, subcats with 5 previews)

### S3 images
- `s3_image_url` already resolved server-side — plain `<img src>`
- Fallback `noimage.jpg` handled by API

---

## 6. IMPLEMENTATION PHASES

```
Phase A — Scaffold (0.5 day)
  [ ] npm create vite@latest ecommerce-react -- --template react-ts
  [ ] Tailwind setup
  [ ] axios client + proxy config
  [ ] react-router with public/admin layouts

Phase B — Public catalog (2 days)
  [ ] Header + CategoryNav + Footer
  [ ] HomePage (rotation + hero + featured)
  [ ] ProductList + ProductDetail + Category pages
  [ ] Cart page (add/update/remove + token persistence)
  [ ] Checkout page (standard + punchout return)

Phase C — Auth (0.5 day)
  [ ] Login/Register pages
  [ ] AuthContext + ProtectedRoute
  [ ] axios interceptors (token attach + refresh)

Phase D — Admin (2 days)
  [ ] AdminLayout + sidebar
  [ ] Dashboard (stats + Chart.js)
  [ ] Products table (datatables endpoint) + CRUD modal
  [ ] Product edit form (29 fields) + S3 image upload
  [ ] Bulk CSV import page
  [ ] Orders + Users pages

Phase E — Chatbot + polish (0.5 day)
  [ ] ChatWidget (floating, conversation_id in sessionStorage)
  [ ] Responsive fixes, loading states, error toasts

Total: ~5.5 days
```

---

## 7. DEV WORKFLOW

```bash
# Terminal 1 — API
cd ecommerce-fastapi
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000

# Terminal 2 — React
cd ecommerce-react
npm install
npm run dev            # http://localhost:5173 (proxies /api → :8000)

# Build
npm run build           # dist/ → deployable static site
```

Vite proxy config:
```ts
// vite.config.ts
server: {
  proxy: {
    '/api': 'http://localhost:8000',
  },
}
```

---

## 8. DEPLOYMENT (later, in Step 14)

- `npm run build` → `dist/` served by Nginx/Cloud Run static hosting
- SPA fallback: all routes → index.html
- API stays separate (FastAPI server)
- CORS: allow frontend origin (or serve same-origin via proxy)
