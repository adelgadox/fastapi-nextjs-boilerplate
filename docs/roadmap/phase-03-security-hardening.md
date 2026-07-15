# Phase 03 — Security Hardening

Day-1 footing. Most of these ship *inactive* in the boilerplate already
(middleware and utils exist) — this phase is about **wiring them in** and adding
the ones that are missing, so a new project starts hardened rather than
retrofitting later.

**Legend** — Complexity: 🟢 Low · 🟡 Medium · 🔴 High · Status: ✅ Done · 🟡 Partial · ⬜ Pending

| # | Task | Description | Source | Complexity | Status |
|---|------|-------------|--------|------------|--------|
| 03.1 | Row-Level Security (RLS) | Postgres RLS as defence-in-depth: non-superuser `app` role, `owner_isolation` policies (`pet_id IN (SELECT … WHERE user_id = current_setting(...))`), `RLSContextMiddleware` + `get_db` `SET LOCAL app.current_user_id`. **Gotcha:** superusers bypass RLS even with FORCE — the migration role must be non-superuser. | pet-portal migration `0009`, `RLSContextMiddleware` | 🔴 | ⬜ Pending |
| 03.2 | RBAC roles/permissions tables | `roles / permissions / role_permissions / user_roles`; `require_permission("x")` default-deny guard + `:own`/`:any` split; per-request cache on `request.state`. The boilerplate has `get_current_admin` deps but no route uses them. | pet-portal `core/rbac.py` | 🔴 | ⬜ Pending |
| 03.3 | Wire input sanitization | `strip_html` + username/slug/scheme validators into Pydantic validators on user-facing schemas (registration, names, addresses, reviews). Helpers exist in `utils/sanitize.py` but aren't applied. | pet-portal `core/sanitize.py`, bioflow | 🟢 | ⬜ Pending |
| 03.4 | Frontend CSP + HSTS | `next.config.ts` is empty. Add security headers (HSTS `max-age=63072000; includeSubDomains; preload`, Permissions-Policy) + per-request CSP in `middleware.ts`. Snippet already in `docs/security.md`. | bioflow / pet-portal `next.config.ts` | 🟡 | ⬜ Pending |
| 03.5 | Prod-safety startup assertions | `assert_debug_safe_for_production`: hard-fail boot when `DEBUG=True`, `SECRET_KEY==default/<32B`, or `REDIS_URL` unset in prod. Boilerplate checks `SECRET_KEY` length only. | pet-portal `config.py:103` | 🟢 | ⬜ Pending |
| 03.6 | Enforce internal secret everywhere | `secrets.compare_digest` on all server-to-server routes (already added for `/auth/oauth`; apply pattern to future `/internal/*`). | pet-portal `routers/internal.py` | 🟢 | 🟡 Partial |
| 03.7 | Activate Cloudflare-only + admin IP allowlist | Middlewares exist and are off by default — document the per-project switch and set the env vars for prod. | boilerplate + bioflow | 🟢 | ⬜ Pending |
| 03.8 | Secrets rotation runbook | `docs/secrets-rotation.md`: Postgres roles, `SECRET_KEY`, Cloudinary/Resend/Google/NextAuth rotation steps. | pet-portal `docs/secrets-rotation.md` | 🟢 | ⬜ Pending |
| 03.9 | Real IP through Vercel→Railway hop | Trust `X-Real-Visitor-IP` only when paired with `X-Internal-Token`; keep `get_client_ip()` as the single source. | bioflow `auth.py:_get_client_ip` | 🟡 | ⬜ Pending |
