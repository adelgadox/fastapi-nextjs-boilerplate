# Phase 01 — Auth Completeness & Mobile Tokens

The single biggest API-first gap: a 24h access token with no refresh. A Flutter
client needs a short-lived access token + a long-lived, rotating refresh token.
This phase makes the auth vertical production- and mobile-complete.

**Legend** — Complexity: 🟢 Low · 🟡 Medium · 🔴 High · Status: ✅ Done · 🟡 Partial · ⬜ Pending

| # | Task | Description | Source | Complexity | Status |
|---|------|-------------|--------|------------|--------|
| 01.1 | Refresh-token rotation | 30-min access + 30-day refresh stored as SHA-256 hash, grouped by `family_id`, `replaced_by` chain. `POST /v1/auth/refresh`. Token response carries `expires_in`. | araguaney `auth_service.py` | 🔴 | ✅ Done |
| 01.2 | Refresh reuse detection | Replaying a rotated token revokes the whole `family_id` chain (theft response) — with a 10s grace window (`_is_benign_reuse`) tolerating concurrent client double-fires. `revoke_family` on logout. 8 tests. | araguaney `auth_service.py` | 🟡 | ✅ Done |
| 01.3 | Shorten access TTL | `access_token_expire_minutes` dropped from 1440 to 30. | araguaney `config.py` | 🟢 | ✅ Done |
| 01.4 | Revocable device sessions | `issue_session_token()` writes a `user_sessions` row (jti, ip, user_agent, expires_at). `GET /auth/sessions`, `DELETE /auth/sessions/{jti}`, `DELETE /auth/sessions/others`. Lets a mobile user see/revoke devices. | bioflow `auth_service.issue_session_token` | 🟡 | ⬜ Pending |
| 01.5 | TOTP 2FA in login flow | `pyotp` (RFC 6238). Setup returns QR (base64 PNG) + secret; login returns a 5-min partial token with `scope="2fa_pending"` when TOTP is enabled, exchanged for a full token after code verification. | bioflow / pet-portal `totp_service.py`, `core/totp.py` | 🔴 | ⬜ Pending |
| 01.6 | TOTP backup codes | 8 single-use codes stored bcrypt-hashed. `POST /auth/2fa/verify-backup` (5/hour). Brute-force limiter (5 fails / 300s → 15-min lockout). | bioflow / pet-portal | 🟡 | ⬜ Pending |
| 01.7 | Force 2FA for admin/staff | RBAC guard 403s an admin/superadmin without `totp_enabled`. | pet-portal `core/rbac.py:27` | 🟢 | ⬜ Pending |
| 01.8 | Server-verified OAuth | Replace client-asserted `{email,name}` with real provider verification (Google id_token) on the Next.js side before the internal call; keep `X-Internal-Token` (Phase 00.2). | pet-portal Phase 8.3 (⬜ there too) | 🟡 | ⬜ Pending |
| 01.9 | Password-changed email | Confirmation email after a successful reset (the removed `# TODO` in `reset_password`). | bioflow | 🟢 | ⬜ Pending |
| 01.10 | JWT invalidation on password change | Deny all existing jti / bump a token-version claim when the password changes. | bioflow Phase 15 · M12 | 🟡 | ⬜ Pending |
