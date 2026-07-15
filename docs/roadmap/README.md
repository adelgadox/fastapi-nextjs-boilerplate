# Boilerplate Roadmap

Hardening & maturity roadmap for this API-first FastAPI + Next.js boilerplate,
backported from two production projects on the same stack (**bioflow** and
**pet-portal**). The goal: a new project starts day 1 on a robust, secure,
mobile-ready foundation — the API feeds a future **Flutter** app in a separate repo.

Every task carries a **Source** column pointing at the exact file/phase to port
from, so implementing a phase is a lookup, not a redesign.

## Progress

```mermaid
pie showData
  title Roadmap tasks (94 total)
  "Done" : 8
  "Partial" : 9
  "Pending" : 77
```

| Phase | Focus | Done | Partial | Pending | Total | % |
|-------|-------|------|---------|---------|-------|---|
| [00 — Foundation Fixes](phase-00-foundation-fixes.md) | Boot-blocking bugs, end-to-end auth | 4 | 0 | 4 | 8 | 50% |
| [01 — Auth & Mobile Tokens](phase-01-auth-mobile-tokens.md) | Refresh rotation, 2FA, sessions | 3 | 1 | 6 | 10 | 30% |
| [02 — Media & Storage](phase-02-media-storage.md) | R2 docs + Cloudinary images | 0 | 0 | 8 | 8 | 0% |
| [03 — Security Hardening](phase-03-security-hardening.md) | RLS, RBAC, CSP, prod asserts | 0 | 1 | 8 | 9 | 0% |
| [04 — Observability](phase-04-observability.md) | Request-ID, JSON logs, health | 0 | 2 | 7 | 9 | 0% |
| [05 — Scalability & Async](phase-05-scalability-async.md) | Caching, async, indexes, pooling | 0 | 3 | 5 | 8 | 0% |
| [06 — API Contract & Flutter](phase-06-api-contract-flutter.md) | Envelope, OpenAPI, versioning | 0 | 1 | 11 | 12 | 0% |
| [07 — Data Lifecycle & GDPR](phase-07-data-lifecycle-gdpr.md) | Soft-delete, erasure, cascade | 0 | 0 | 6 | 6 | 0% |
| [08 — Testing & CI](phase-08-testing-ci.md) | pytest, drift guard, coverage | 1 | 1 | 6 | 8 | 13% |
| [09 — Payments (Stripe)](phase-09-payments-stripe.md) | Webhook idempotency, checkout, plan state | 0 | 0 | 16 | 16 | 0% |
| **Total** | | **8** | **9** | **77** | **94** | **9%** |

## Suggested order

Phases are numbered in rough build order, but they're independent enough to
pull out of sequence:

1. **00** — already mostly done in this PR; finish `/me`, `EmailStr`, denylist cron.
2. **01** — refresh tokens are the biggest blocker for the Flutter client. Do this early.
3. **04** + **08** — observability + tests before you build features on top (cheap insurance).
4. **02**, **03**, **05**, **06**, **07** — pull in per project need.

## Legend

- **Complexity** — 🟢 Low · 🟡 Medium · 🔴 High
- **Status** — ✅ Done · 🟡 Partial · ⬜ Pending

## Editing rules

- Keep the **Source** column accurate — it's the whole point (backport, don't redesign).
- When a task lands, flip its Status and update this index's counts + mermaid pie.
- New hardening work from bioflow/pet-portal → add a row to the matching phase, not a new phase, unless it's a genuinely new domain.
- Convert relative dates to absolute in task descriptions.

## Reference projects

- **bioflow** — most mature (46 phases). Best source for: observability, API contract, deprecation, audit mixin, ARQ crons.
- **pet-portal** — best source for: storage `StoragePort`, RLS, refresh-token rotation, GDPR deletion, app-factory split, prod-safety asserts, CI drift guard.
