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
| 03.3 | Wire input sanitization | `strip_html` + username/scheme validators applied via `field_validator` on all auth schemas (email normalize, username charset, password length, full_name HTML strip, avatar_url scheme block). 7 tests. | araguaney | 🟢 | ✅ Done |
| 03.4 | Frontend CSP + HSTS | `next.config.ts` is empty. Add security headers (HSTS `max-age=63072000; includeSubDomains; preload`, Permissions-Policy) + per-request CSP in `middleware.ts`. Snippet already in `docs/security.md`. | bioflow / pet-portal `next.config.ts` | 🟡 | ⬜ Pending |
| 03.5 | Prod-safety startup assertions | Hard-fail on `SECRET_KEY` <32B and `CLOUDFLARE_ONLY` without secret; warn on `DEBUG=true` and missing `ENCRYPTION_KEY`. Remaining: hard-fail `DEBUG` in prod-detected environments. | pet-portal `config.py:103` | 🟢 | 🟡 Partial |
| 03.6 | Enforce internal secret everywhere | `secrets.compare_digest` on all server-to-server routes (already added for `/auth/oauth`; apply pattern to future `/internal/*`). | pet-portal `routers/internal.py` | 🟢 | 🟡 Partial |
| 03.7 | Activate Cloudflare-only + admin IP allowlist | Middleware now validates the `X-Origin-Auth` Transform-Rule shared secret (constant-time; NO CIDR check — blocks 100% behind Railway's proxy). Startup guard, `.env.example` runbook with zero-downtime activation order, `docs/security.md` section, 8 tests. | araguaney `main.py` | 🟢 | ✅ Done |
| 03.8 | Secrets rotation runbook | `docs/secrets-rotation.md`: Postgres roles, `SECRET_KEY`, Cloudinary/Resend/Google/NextAuth rotation steps. | pet-portal `docs/secrets-rotation.md` | 🟢 | ⬜ Pending |
| 03.9 | Real IP through Vercel→Railway hop | Trust `X-Real-Visitor-IP` only when paired with `X-Internal-Token`; keep `get_client_ip()` as the single source. | bioflow `auth.py:_get_client_ip` | 🟡 | ⬜ Pending |
