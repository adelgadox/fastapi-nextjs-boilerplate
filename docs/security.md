# Security Layers — FastAPI + Next.js Boilerplate

This document tracks every security layer implemented in this stack. Use it as
a checklist when starting a new project from this template.

Everything listed under "ships by default" is **real, wired code** — this doc
is kept in sync with `main.py` and the `utils/` modules, not with aspirations.

---

## What the boilerplate ships by default

Active out of the box — no configuration needed beyond env vars.

### Backend

| Layer | Location | Notes |
|-------|----------|-------|
| JWT + HS256, 30-min access tokens | `services/auth_service.py` | `jti` claim on every token for revocation |
| **Rotating refresh tokens** | `models/refresh_token.py`, `services/auth_service.py` | SHA-256 at rest, `family_id` chains, reuse detection revokes the whole session; 10s grace window for client double-fires |
| Token denylist | `models/token_denylist.py` | Revokes access tokens on logout; purged daily by `purge_expired_tokens_cron` |
| bcrypt password hashing | `services/auth_service.py` | `gensalt()` per password; constant-time dummy hash on unknown users (timing oracle) |
| Login lockout | `services/auth_service.py` | 10 failures → 15-min lockout |
| **Rate limiting keyed by user** | `utils/rate_limit.py` | `user:<sub>` with a verified JWT, `ip:<ip>` otherwise — survives mobile CGNAT and Vercel egress; Redis storage with in-memory fallback |
| Rate-limit coverage **test** | `tests/test_rate_limit_coverage.py` | CI fails on any endpoint without `@limiter.limit()` and without a declared exemption |
| Security headers middleware | `main.py` | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `X-XSS-Protection`, HSTS, Permissions-Policy |
| Cloudflare-only origin auth | `main.py` `CloudflareOnlyMiddleware` | Shared-secret `X-Origin-Auth` header — see below. Off until `CLOUDFLARE_ONLY=true` |
| Admin IP allowlist | `main.py` `AdminIPAllowlistMiddleware` | Guards `/v1/admin/*`; off while `ADMIN_ALLOWED_IPS` is empty |
| CORS | `main.py` | Locked to `FRONTEND_URL` (comma-separated multi-origin) |
| ProxyHeadersMiddleware | `main.py` | Trusts proxy headers from `TRUSTED_PROXY_IPS` |
| Input sanitization **wired** | `schemas/auth.py` + `utils/sanitize.py` | Email normalization, username charset, password length, HTML stripping, dangerous URL schemes — enforced at the schema |
| Strict schemas + `extra="forbid"` | `schemas/_base.py` | Anti mass-assignment; `StrictUUID`/`StrictDate`/... aliases for JSON input |
| Error envelope, generic 500s | `main.py`, `utils/errors.py` | `{"error": {code, message, field, meta}}` on every error path; no stack traces to clients |
| Slack 500 alerts w/ noise budget | `main.py`, `utils/alert_budget.py` | Grouped by route+exception, 30-min window; channel from `SLACK_ALERT_CHANNEL` |
| API docs gating | `main.py` | `EXPOSE_API_DOCS=false` hides `/docs`, `/redoc`, `/openapi.json` in prod |
| Internal S2S token | `dependencies.py` `require_internal_token` | Fail-closed `X-Internal-Token`, constant-time compare; guards `/v1/auth/oauth` |
| Startup guards | `main.py` | Fail fast: short `SECRET_KEY`, `CLOUDFLARE_ONLY` without secret; warn: `DEBUG=true`, missing `ENCRYPTION_KEY` |
| Contract regression test | `tests/contract/` | Breaking `/v1` changes (removed op, newly-required field) fail CI — protects installed mobile clients |
| Email verification required | `services/auth_service.py` | Login blocked until email verified |
| Password reset with expiry | `services/auth_service.py` | 1-hour token, `secrets.token_urlsafe(32)` |
| User enumeration protection | `services/auth_service.py` | Same response for existing/non-existing emails |
| SQLAlchemy ORM | throughout | Parameterized queries — no raw SQL |
| Sentry (optional) | `main.py` + `worker.py` | Separate init per process; `send_default_pii=False` |

**Rate limits shipped:**

| Endpoint | Limit |
|----------|-------|
| `POST /v1/auth/register` | 5/hour |
| `POST /v1/auth/login` | 10/5min |
| `POST /v1/auth/refresh` | 30/min |
| `POST /v1/auth/logout` | 10/min |
| `GET /v1/auth/me` | 120/min |
| `POST /v1/auth/resend-verification` | 3/hour |
| `POST /v1/auth/forgot-password` | 3/hour |
| `POST /v1/auth/reset-password` | 5/hour |
| `GET /v1/client/version` | 60/min |
| `GET /health/jobs` | 30/min |

### Frontend

| Layer | Location | Notes |
|-------|----------|-------|
| NextAuth v5 JWT | `src/auth.ts` | Session cookie = refresh lifetime; access rotated underneath with 60s skew; refresh token never exposed to the client |
| Server-side revocation | `src/auth.ts` `signOut` event | Backend refresh family revoked on logout |
| Auth middleware | `src/middleware.ts` | Protects `/dashboard`; `no-store` on authed shells (bfcache) |
| Security headers + CSP | `next.config.ts` | HSTS preload, Permissions-Policy, CSP with computed `img-src` from the API origin |
| Origin-auth interceptor | `src/lib/backend-origin-auth.ts` | Adds `X-Origin-Auth` to server-to-server backend calls — see Cloudflare section |
| `apiFetch` + `ApiError` | `src/lib/api.ts` | Centralized; carries `status` + machine-readable `code` |
| Sentry 3-file wiring | `instrumentation.ts`, `instrumentation-client.ts` | Tunnel route `/monitoring` (ad-blockers); build fails loud on half-configured source-map upload |

---

## Cloudflare-only mode — how it actually works

Blocks requests that don't come through Cloudflare, so the Railway origin URL
can't be hit directly (bypassing the WAF, bot fight mode, and rate limiting).

**Mechanism: a shared secret, NOT IP ranges.** A Cloudflare Transform Rule
injects `X-Origin-Auth: <secret>` on every proxied request;
`CloudflareOnlyMiddleware` validates it with a constant-time compare.

> **Why not validate the connecting IP against Cloudflare's published CIDR
> ranges?** On Railway (and any PaaS with an internal proxy), the raw TCP peer
> the app sees is always the platform's own proxy — never a Cloudflare edge
> IP. A CIDR check therefore blocks **100% of traffic**, including login. This
> is not hypothetical: it was a production incident (2026-07-02, araguaney).
> A presence-only check of `CF-Connecting-IP` fails in the opposite direction:
> anyone hitting the origin directly can set that header themselves.

Two exemptions, both principled:
- `/health` — the platform's liveness probe doesn't come through Cloudflare.
- `/webhooks/*` — third parties (Stripe, Resend/Svix) can't send the
  Transform-Rule header; they authenticate via their own signatures.

**Server-to-server calls from Next.js** go direct to Railway (not through
Cloudflare), so the frontend installs a global fetch interceptor
(`src/lib/backend-origin-auth.ts`, installed from `instrumentation.ts`) that
adds the same header to every request whose URL starts with the backend
origin. One interceptor instead of one header per handler, because a security
control you must remember at every call site gets forgotten at call site #55.

**Zero-downtime activation order:**
1. Generate the secret: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Deploy the frontend with `CLOUDFLARE_SHARED_SECRET` set (interceptor is a
   no-op until the backend enforces).
3. Cloudflare dashboard → Rules → Transform Rules → Modify Request Header:
   when hostname equals your API hostname, set static header `X-Origin-Auth`
   to the secret.
4. Set `CLOUDFLARE_SHARED_SECRET` on the backend (Railway).
5. Only then flip `CLOUDFLARE_ONLY=true`. The app refuses to boot if the
   secret is missing while the flag is on.

**Why the frontend is NOT behind Cloudflare:** Railway ships no WAF or rate
limiting, so Cloudflare adds protection there. Vercel already runs its own
firewall; putting a proxy in front of it degrades its detection signals and
challenges legitimate users. In front of Railway, Cloudflare adds; in front of
Vercel, it subtracts.

---

## Add per project — required configuration

### 1. Internal API secret

Server-to-server routes (OAuth minting, future `/internal/*`) require
`INTERNAL_API_SECRET` in both backend and frontend envs. The backend guard is
`require_internal_token` in `dependencies.py` (fail-closed: unset secret
blocks the route entirely). Send as `X-Internal-Token` from Server Actions
only — never expose to the browser.

### 2. CSP allowlist

`next.config.ts` ships a strict CSP with `img-src` computed from
`NEXT_PUBLIC_API_URL`. When you add third-party services (Cloudinary,
analytics, Turnstile), add their origins to the relevant directives — don't
loosen to wildcards.

### 3. New endpoints

- Every public/auth endpoint needs `@limiter.limit()` —
  `tests/test_rate_limit_coverage.py` fails CI otherwise. Deliberate
  exemptions go in its `EXEMPT` set with a written reason.
- Every schema extends `StrictModel`/`StrictORMModel`; user-supplied text
  fields get `strip_html`/validators from `utils/sanitize.py`.
- User-supplied URLs must pass `utils/url_security.validate_url()` (SSRF)
  before storing or fetching.

---

## Optional layers (by feature)

Activate when the feature is needed. Documented in `docs/optional-layers.md`.

| Layer | Complexity | Notes |
|-------|-----------|-------|
| 2FA / TOTP | 🟠 | `pyotp`, QR setup, two-step login flow |
| OAuth (Google, GitHub, etc.) | 🟡 | NextAuth providers + `/auth/oauth` backend endpoint |
| Stripe webhook verification | 🟡 | `stripe.Webhook.construct_event()` + idempotency table |
| Google Safe Browsing | 🟢 | URL malware check; fails open if API key absent |
| GeoIP / MaxMind | 🟠 | Capture country/city at registration |
| Fernet column encryption | 🟢 | `utils/crypto.py` — encrypt API keys/tokens at rest; set `ENCRYPTION_KEY` |

---

## Checklist — new project from this template

### Auth
- [ ] `SECRET_KEY` is a random 32-byte hex string (`openssl rand -hex 32`)
- [ ] `ACCESS_TOKEN_EXPIRE_MINUTES=30` (short — clients refresh) and `REFRESH_TOKEN_EXPIRE_DAYS=30`
- [ ] `ENCRYPTION_KEY` set (dedicated key, not the fallback to `SECRET_KEY`)

### Infrastructure
- [ ] `TRUSTED_PROXY_IPS=*` on Railway (containers are behind proxy)
- [ ] Cloudflare-only mode activated in the 5-step order above
- [ ] `ADMIN_ALLOWED_IPS` set if `/v1/admin/*` routes exist
- [ ] `DEBUG=false` and `EXPOSE_API_DOCS=false` in production
- [ ] `SENTRY_DSN` set in both backend and frontend

### Rate limiting
- [ ] `REDIS_URL` set in prod so limits are shared across replicas
- [ ] Limits reviewed against expected traffic

### Monitoring
- [ ] `SLACK_BOT_TOKEN` + `SLACK_ALERT_CHANNEL` set so 500/cron alerts fire
- [ ] External uptime monitor on `/health` AND `/health/jobs` (503 = background work stalled)
- [ ] Sentry source maps uploading in frontend CI (`SENTRY_ORG` + `SENTRY_PROJECT` + `SENTRY_AUTH_TOKEN` — build fails loud if half-set)

### CORS
- [ ] `FRONTEND_URL` set to the exact production domain (no trailing slash)
- [ ] Multi-origin comma-separated if needed

---

## Reference implementations

- `backend/app/main.py` — `CloudflareOnlyMiddleware` (shared secret), security headers, startup guards
- `backend/app/utils/cloudflare.py` — visitor IP extraction (deliberately NO CIDR validation — see above)
- `backend/app/utils/rate_limit.py` — user-keyed rate limiting
- `backend/app/utils/sanitize.py` + `backend/app/schemas/auth.py` — sanitization wired into schemas
- `backend/tests/test_rate_limit_coverage.py` — the convention as a test
- `frontend/src/lib/backend-origin-auth.ts` — origin-auth fetch interceptor
- `frontend/next.config.ts` — security headers, CSP, Sentry build guard
