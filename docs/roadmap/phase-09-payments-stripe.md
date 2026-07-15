# Phase 09 — Payments (Stripe)

Stripe is the chosen payment gateway. The boilerplate ships only a **minimal
recipe** in `docs/optional-layers.md` — and that recipe teaches the *insecure*
pattern (webhook with no idempotency). bioflow has a production-grade
implementation; this phase backports the robust, generic parts and fixes the
known gaps.

> **The single most important task is 09.2** — webhook idempotency. Stripe
> guarantees *at-least-once* delivery, so processing `checkout.session.completed`
> twice can grant/charge a user twice. Without a dedupe table, the recipe is a
> money bug waiting to happen.

**Do NOT copy from bioflow:** its legacy second webhook handler
(`/v1/billing/webhook`, non-idempotent), the dual pricing tiers
(`price_tier`, `_v2` price IDs — pricing-migration history), the
register+auto-verify+checkout onboarding funnel, and its link/profile-specific
perk logic. Copy the *shape*, not the domain.

**Legend** — Complexity: 🟢 Low · 🟡 Medium · 🔴 High · Status: ✅ Done · 🟡 Partial · ⬜ Pending

| # | Task | Description | Source | Complexity | Status |
|---|------|-------------|--------|------------|--------|
| 09.1 | Single canonical webhook | ONE handler: `POST /webhooks/stripe` (unversioned — Stripe calls it directly). Verify with `stripe.Webhook.construct_event(payload, sig, webhook_secret)`; 400 on `SignatureVerificationError`. Don't ship two handlers. | bioflow `webhook_service.py` | 🟡 | ⬜ Pending |
| 09.2 | `stripe_events` idempotency dedupe | **Security-critical.** `stripe_events(event_id PK, processed_at)`; insert `event["id"]` + flush; on `IntegrityError` rollback and return `{received:true}` without re-processing. DB-enforced, race-safe. | bioflow `models/stripe_event.py` | 🟡 | ⬜ Pending |
| 09.3 | Core event → plan state | Handle `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`. Map `status ∈ {active,trialing}` → `plan=pro`, else `free` + clear sub id. | bioflow `webhook_service.py` | 🟡 | ⬜ Pending |
| 09.4 | User billing columns + migration | `stripe_customer_id` (unique, indexed), `stripe_subscription_id` (unique, indexed), `subscription_price_id`, `plan`. Denormalized on `users` (no separate subscriptions table needed for a boilerplate). | bioflow `models/user.py` | 🟢 | ⬜ Pending |
| 09.5 | Backend-owned checkout | `POST /v1/billing/checkout {period}` resolves Stripe price IDs **server-side** — frontend/mobile never handle price IDs. (bioflow resolves them in the frontend; do it right from the start — their roadmap B7 wants this moved backend.) | bioflow B7 (⬜ there) | 🟡 | ⬜ Pending |
| 09.6 | Customer portal endpoint | `POST /v1/billing/portal` → `stripe.billing_portal.Session.create` for self-service manage/cancel/payment-update. | bioflow `billing_service.py` | 🟢 | ⬜ Pending |
| 09.7 | `Idempotency-Key` passthrough | Thread `Idempotency-Key` header → Stripe `Session.create(idempotency_key=...)` on checkout + portal. Mobile networks retry aggressively. Ties generic task **06.7**. | bioflow Phase 46 · C3 | 🟢 | ⬜ Pending |
| 09.8 | Never trust `customer_id` from body | Always resolve `stripe_customer_id`/`subscription_id` from the authenticated ORM user — never from the request. Checkout/portal schemas have **no** customer field. Prevents billing IDOR. | bioflow Phase 15 · M8 | 🟢 | ⬜ Pending |
| 09.9 | Redirect allow-list + deep links | Validate `success_url`/`cancel_url`/`return_url` against `frontend_url` origins + a `MOBILE_DEEP_LINK_SCHEMES` allow-list (e.g. `myapp://`) for Flutter returns. **Harden vs bioflow:** parse scheme+host, don't `startswith` (their prefix check lets `app.site.io.evil.com` pass). Ties **06.11**. | bioflow Phase 46 · C7 (+ fix) | 🟡 | ⬜ Pending |
| 09.10 | Server-side success verification | `GET /v1/billing/verify-session?session_id=` checks Stripe session `status==complete` AND metadata `user_id` ownership (403) before the UI shows success. Never trust the redirect alone. | bioflow `verify_session` | 🟡 | ⬜ Pending |
| 09.11 | Dual-source plan expiry | Belt-and-suspenders for missed webhooks: lazy expiry in `get_current_user` (revert time-limited grants) + a reconciliation cron (`expire_pro_grants`). **Subtle rule:** on transient Stripe errors, SKIP (don't downgrade) to avoid false positives; paid subs are never touched lazily. | bioflow `dependencies.py`, `internal_service.py` | 🔴 | ⬜ Pending |
| 09.12 | `revoke_pro_perks` hook | Single de-provisioning routine called from every free-downgrade path. Ship the shape (minimal/empty body) so projects fill in their own perks — keeps downgrade logic in one place. Pairs with entitlements (**06.8**). | bioflow `billing_service.py` | 🟢 | ⬜ Pending |
| 09.13 | `sync_subscription_if_missing` | Self-healing recovery: if a webhook was dropped, reconcile the user's subscription from Stripe on next authenticated access. | bioflow `billing_service.py` | 🟡 | ⬜ Pending |
| 09.14 | Webhook signature + idempotency tests | Test both the signature-verification reject path and the duplicate-delivery dedupe (bioflow has neither — add them here). | new (gap in bioflow) | 🟡 | ⬜ Pending |
| 09.15 | Env vars + graceful degradation | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_MONTHLY`, `STRIPE_PRICE_YEARLY` all default `""`; "not configured" errors when empty; document **all** in `.env.example`. | bioflow `config.py` | 🟢 | ⬜ Pending |
| 09.16 | Promo codes (optional) | Anti-TOCTOU redemption: atomic conditional `UPDATE … WHERE use_count < max_uses` + `rowcount` check + `UniqueConstraint(user_id, code_id)`. Reusable race-safe-counter pattern beyond promos. | bioflow `billing_service.py:229` | 🟡 | ⬜ Pending |
