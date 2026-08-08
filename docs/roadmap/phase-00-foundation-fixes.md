# Phase 00 — Foundation Fixes

Boot-blocking bugs and correctness gaps that must be green before anything else.
These make a fresh clone actually start and complete its core auth flow end-to-end.

**Legend** — Complexity: 🟢 Low · 🟡 Medium · 🔴 High · Status: ✅ Done · 🟡 Partial · ⬜ Pending

| # | Task | Description | Source | Complexity | Status |
|---|------|-------------|--------|------------|--------|
| 00.1 | Base migration creates tables | `000_initial_schema` creates `users` + `token_denylist`; `001` now chains off it. Previously `alembic upgrade head` (run in the Dockerfile CMD) failed on a fresh DB because no migration created the tables. | boilerplate | 🟡 | ✅ Done |
| 00.2 | Guard OAuth token minting | `POST /v1/auth/oauth` minted an access token for **any** email with no auth. Now behind `require_internal_token` (fail-closed `X-Internal-Token`, constant-time compare). Next.js verifies the provider, then calls server-to-server. | bioflow `routers/internal.py` | 🟡 | ✅ Done |
| 00.3 | Wire verification / reset emails | `register`, `resend_verification`, `forgot_password` had `# TODO: enqueue` — tokens were generated but never sent. Now `enqueue(...)` the ARQ task (in-process fallback when Redis is off). | boilerplate | 🟢 | ✅ Done |
| 00.4 | Ship email templates | `templates/emails/` was empty; `email.py` rendered `verification.html` / `password_reset.html` → would crash. Added both (light-mode-safe, `color-scheme` meta). | boilerplate | 🟢 | ✅ Done |
| 00.5 | Email validation on auth schemas | All email fields (`UserCreate`, `ForgotPasswordRequest`, `ResendRequest`, `OAuthLogin`) now validate format and normalize to lowercase via a shared `field_validator` (regex, ≤254 chars) in `schemas/auth.py`. | araguaney `schemas/` | 🟢 | ✅ Done |
| 00.6 | `GET /v1/auth/me` endpoint | `/me` returns `UserOut` (id, email, username, role, plan, is_verified, created_at), 120/min. | araguaney `routers/auth.py` | 🟢 | ✅ Done |
| 00.7 | Token-denylist cleanup cron | `purge_expired_tokens_cron` (daily 05:30 UTC) purges expired denylist rows AND expired refresh tokens; heartbeat-tracked. | araguaney `worker.py` | 🟢 | ✅ Done |
| 00.8 | Fix doc/version drift | `docs/security.md` rewritten from actual code (shared-secret Cloudflare mode, wired sanitization); CLAUDE.md says Next.js 16. | boilerplate | 🟢 | ✅ Done |
