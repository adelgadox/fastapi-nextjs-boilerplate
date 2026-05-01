# Security Layers — FastAPI + Next.js Boilerplate

This document tracks every security layer implemented in this stack. Use it as a checklist when starting a new project from this template.

---

## What the boilerplate ships by default

These are active out of the box — no configuration needed beyond env vars.

### Backend

| Layer | Location | Notes |
|-------|----------|-------|
| JWT + HS256 | `routers/auth.py` | `jti` claim on every token for revocation |
| Token denylist | `models/token_denylist.py` | Revokes tokens on logout |
| bcrypt password hashing | `routers/auth.py` | `gensalt()` per password |
| Rate limiting (slowapi) | `utils/rate_limit.py` | Per-IP, see limits below |
| Security headers middleware | `main.py` | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `X-XSS-Protection` |
| CORS | `main.py` | Locked to `FRONTEND_URL` env var |
| ProxyHeadersMiddleware | `main.py` | Trusts proxy headers from `TRUSTED_PROXY_IPS` |
| Sentry (optional) | `main.py` | Disabled if `SENTRY_DSN` not set; `send_default_pii=False` |
| Generic 500 responses | `main.py` | No stack traces exposed to clients |
| Slack alert on 500 | `main.py` | Fires to `#backend-alerts` |
| Email verification required | `routers/auth.py` | Login blocked until email verified |
| Password reset with expiry | `routers/auth.py` | 1-hour token, `secrets.token_urlsafe(32)` |
| User enumeration protection | `routers/auth.py` | Same response for existing/non-existing emails |
| SQLAlchemy ORM | throughout | Parameterized queries — no raw SQL |

**Rate limits shipped:**

| Endpoint | Limit |
|----------|-------|
| `POST /auth/register` | 5/hour |
| `POST /auth/login` | 10/5min |
| `POST /auth/logout` | 10/min |
| `POST /auth/resend-verification` | 3/hour |
| `POST /auth/forgot-password` | 3/hour |
| `POST /auth/reset-password` | 5/hour |

### Frontend

| Layer | Location | Notes |
|-------|----------|-------|
| NextAuth v5 JWT | `src/auth.ts` | Stateless sessions |
| Auth middleware | `src/middleware.ts` | Protects `/dashboard` and admin routes |
| Expired token redirect | `src/middleware.ts` | Auto-redirects to `/login` with callback URL |
| `apiFetch` wrapper | `src/lib/api.ts` | Centralized, no raw `fetch` in components |

---

## Add per project — required configuration

These are implemented but require env vars or a one-time setup step before they're active.

### 1. Cloudflare-only mode

Blocks requests that don't come through Cloudflare. Prevents direct backend URL access.

**Enable:** set `CLOUDFLARE_ONLY=true` in backend env.

Already has: `utils/cloudflare.py` (IP extraction + CIDR validation).

To activate the blocking middleware, add to `main.py` **before** CORS:

```python
class CloudflareOnlyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == "/health":
            return await call_next(request)
        if not is_cloudflare_request(request):
            return Response(status_code=403)
        return await call_next(request)
```

Where `is_cloudflare_request` checks `CF-Connecting-IP` header and validates source IP against Cloudflare CIDR ranges (hardcoded IPv4 + IPv6 CIDR list, update periodically from [cloudflare.com/ips](https://www.cloudflare.com/ips/)).

**Why:** Without this, the backend Railway URL is publicly accessible — rate limiting and Cloudflare WAF can be bypassed.

---

### 2. Frontend security headers (CSP + HSTS)

The backend middleware handles `X-Frame-Options` etc., but the **Next.js layer** needs its own headers for browser enforcement.

Add to `frontend/next.config.ts`:

```ts
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https:",
      "font-src 'self' data:",
      "connect-src 'self' https:",
      "frame-ancestors 'self'",
      "object-src 'none'",
    ].join("; "),
  },
];
```

Tighten `script-src` and `connect-src` once you know which third-party domains you need.

---

### 3. Input sanitization

Every project that accepts user-generated content (bios, descriptions, names) needs `strip_html()` applied at the schema layer.

Create `backend/app/utils/sanitize.py` and apply to Pydantic schemas using `@field_validator`.

Key functions:
- `strip_html(text)` — removes all HTML/XML tags, decodes entities
- `validate_username(value)` — 3–30 chars, `[a-zA-Z0-9_-]`, starts with letter/digit
- `validate_slug(value)` — 3–60 chars, lowercase alphanumeric + hyphen

---

### 4. Internal API secret

If Next.js needs to call FastAPI server-to-server (OAuth callbacks, cron endpoints, webhooks), those routes must require a shared secret.

**Set:** `INTERNAL_API_SECRET` in both backend and frontend envs.

**Backend dependency:**

```python
def _require_internal_secret(x_internal_token: str = Header(...)):
    if not secrets.compare_digest(x_internal_token, settings.internal_api_secret):
        raise HTTPException(status_code=403)
```

**Frontend usage:** pass as `X-Internal-Token` header from Server Actions only, never expose to the browser.

---

## Optional layers (by feature)

Activate these when the feature is needed. All are documented in `docs/optional-layers.md`.

| Layer | Complexity | Notes |
|-------|-----------|-------|
| 2FA / TOTP | 🟠 | `pyotp`, QR setup, two-step login flow |
| OAuth (Google, GitHub, etc.) | 🟡 | NextAuth providers + `/auth/oauth` backend endpoint |
| Stripe webhook verification | 🟡 | `stripe.Webhook.construct_event()` + idempotency table |
| Google Safe Browsing | 🟢 | URL malware check; fails open if API key absent |
| Contact form anti-spam | 🟢 | Honeypot field + per-email cooldown + URL count limit |
| GeoIP / MaxMind | 🟠 | Capture country/city at registration |
| Redis session store | 🟡 | Replace JWT denylist table with Redis for scale |

---

## Checklist — new project from this template

Run through this before launch:

### Auth
- [ ] `SECRET_KEY` is a random 32-byte hex string (`openssl rand -hex 32`)
- [ ] `ACCESS_TOKEN_EXPIRE_MINUTES` set appropriately (default 1440 = 24h)
- [ ] Email verification email is wired up (uncomment TODO in `register`)
- [ ] Password reset email is wired up (uncomment TODO in `forgot_password`)

### Infrastructure
- [ ] `TRUSTED_PROXY_IPS=*` on Railway (containers are behind proxy)
- [ ] `CLOUDFLARE_ONLY=true` once Cloudflare is in front of the backend
- [ ] `DEBUG=false` in production
- [ ] `SENTRY_DSN` set in both backend and frontend

### Headers
- [ ] Frontend security headers added to `next.config.ts`
- [ ] CSP `script-src` tightened to actual third-party domains used

### Rate limiting
- [ ] All public/auth endpoints have `@limiter.limit()` annotations
- [ ] Limits reviewed against expected traffic (adjust defaults if needed)

### Input validation
- [ ] `strip_html()` applied to all user-facing text fields
- [ ] Username/slug validators applied where applicable
- [ ] File uploads (if any) validate MIME type, not just extension

### Secrets
- [ ] No hardcoded values in `config.py` — all from env vars
- [ ] `.env` is in `.gitignore`
- [ ] Secrets rotated if accidentally committed

### CORS
- [ ] `FRONTEND_URL` set to the exact production domain (no trailing slash)
- [ ] Multi-origin (e.g. `app.domain.com,www.domain.com`) comma-separated if needed

### Monitoring
- [ ] Slack `SLACK_BOT_TOKEN` + `SLACK_CHANNEL_ID` set so 500 alerts fire
- [ ] Sentry source maps uploading in frontend CI

---

## Reference implementations

- `backend/app/utils/cloudflare.py` — Cloudflare IP extraction + CIDR validation
- `backend/app/utils/sanitize.py` — input sanitization helpers (create per project)
- `frontend/next.config.ts` — security headers including CSP and HSTS
