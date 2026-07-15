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
| 00.5 | `EmailStr` on auth schemas | Schemas use bare `str` for email despite `pydantic[email]` installed. Switch `UserCreate.email`, `ForgotPasswordRequest.email`, `ResendRequest.email`, `OAuthLogin.email` to `EmailStr`. | pet-portal `schemas/` | 🟢 | ⬜ Pending |
| 00.6 | `GET /v1/auth/me` endpoint | No way for a client to read the current user. A Flutter app has nothing to fetch after login. Add `/me` returning a `UserRead` schema. | bioflow `routers/profile.py` | 🟢 | ⬜ Pending |
| 00.7 | Token-denylist cleanup cron | `TokenDenylist` grows unbounded; docstring claims cleanup that doesn't exist. Enable the commented ARQ cron to purge rows past `expires_at`. | pet-portal `cleanup_expired_tokens` | 🟢 | ⬜ Pending |
| 00.8 | Fix doc/version drift | Docs say "Next.js 15" but `package.json` pins 16.x; `docs/security.md` says "add `CloudflareOnlyMiddleware`/`sanitize.py`" which already exist. Reconcile docs with code. | boilerplate | 🟢 | ⬜ Pending |
