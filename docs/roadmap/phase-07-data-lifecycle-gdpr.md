# Phase 07 — Data Lifecycle & GDPR

Legal/compliance footing from day 1: soft-delete, right-to-erasure, and clean
cascade behavior. pet-portal already implements a full GDPR account-deletion
flow — this phase backports it as a reusable boilerplate pattern.

**Legend** — Complexity: 🟢 Low · 🟡 Medium · 🔴 High · Status: ✅ Done · 🟡 Partial · ⬜ Pending

| # | Task | Description | Source | Complexity | Status |
|---|------|-------------|--------|------------|--------|
| 07.1 | Soft-delete pattern | `deleted_at` timestamp column + repository base filters that exclude soft-deleted rows by default; a mixin so any model opts in. | bioflow Phase 46 · D, pet-portal | 🟡 | ⬜ Pending |
| 07.2 | GDPR account deletion | `DELETE /v1/profile/me`: re-auth by password, anonymize orders/reviews, hard-delete carts, cascade dependents, revoke all refresh + access tokens, purge R2 documents (best-effort). Bypass RLS with `SET LOCAL app.current_user_id=''` for self-service erasure. | pet-portal `profile_service.py:63` | 🔴 | ⬜ Pending |
| 07.3 | FK cascade audit | Review every foreign key: `ON DELETE CASCADE` vs `SET NULL` vs `RESTRICT`, so deletion doesn't orphan or over-delete. | bioflow Phase 46 · D | 🟡 | ⬜ Pending |
| 07.4 | Data-export (portability) | `GET /v1/profile/me/export` returning the user's data as JSON (GDPR right to portability). | pet-portal Phase 21 (⬜) | 🟡 | ⬜ Pending |
| 07.5 | Retention / purge crons | Scheduled purge of expired tokens, soft-deleted rows past a grace window, and audit rows past retention. | bioflow `worker.py` crons | 🟢 | ⬜ Pending |
| 07.6 | Legal docs surface | Privacy policy / ToS routes + a `docs/legal/` home, referenced by the roadmap index editing rules. | both Phase 9 / 21 | 🟢 | ⬜ Pending |
