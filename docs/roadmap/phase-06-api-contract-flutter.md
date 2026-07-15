# Phase 06 — API Contract & Flutter Readiness

This is *the* API-first phase. The boilerplate exists to feed a future Flutter
app (separate repo). A shipped mobile binary can't be hot-fixed like a web
deploy — the contract has to be stable, versioned, and forward-compatible.

**Legend** — Complexity: 🟢 Low · 🟡 Medium · 🔴 High · Status: ✅ Done · 🟡 Partial · ⬜ Pending

| # | Task | Description | Source | Complexity | Status |
|---|------|-------------|--------|------------|--------|
| 06.1 | Response/error envelope | Uniform `{success, data, error, meta}` on every response; `AppError` with stable branchable subcodes; safe 500s. Boilerplate has the **error** envelope — add the success envelope + subcodes. | pet-portal `core/envelope.py`+`errors.py` | 🟡 | 🟡 Partial |
| 06.2 | OpenAPI contract snapshot test | Pin `app.openapi()` to a committed `openapi_snapshot.json`; any breaking `/v1` change fails CI with added-vs-removed operation diff. Protects shipped Flutter binaries. Regenerate with `UPDATE_OPENAPI_SNAPSHOT=1`. | bioflow `tests/contract/` | 🟡 | ⬜ Pending |
| 06.3 | Cursor pagination | Standard cursor-based list envelope (not offset) for all collections a client scrolls. | bioflow Phase 46 · C, pet-portal 7.2 | 🟡 | ⬜ Pending |
| 06.4 | `response_model` everywhere | Every route declares a typed `response_model` so the OpenAPI schema (and the generated Flutter client) is exact. | both | 🟡 | ⬜ Pending |
| 06.5 | RFC 8594 deprecation headers | `Deprecation` + `Sunset` headers + a documented 6-month sunset process for `/v1`→`/v2`. `DeprecationMiddleware` + single frontend/mobile `API_VERSION` constant. | bioflow Phase 17.1, `utils/deprecation.py` | 🟡 | ⬜ Pending |
| 06.6 | Client-version force-upgrade gate | `ClientVersionMiddleware` rejects clients below `MIN_CLIENT_VERSION` with 426 `CLIENT_UPGRADE_REQUIRED` (fail-open when unconfigured). Lets you force old mobile apps to update. | bioflow `middleware/client_version.py` | 🟡 | ⬜ Pending |
| 06.7 | Idempotency keys | `Idempotency-Key` header on non-idempotent POSTs (checkout, create) to survive mobile retries on flaky networks. | bioflow Phase 46 · C, pet-portal 25.2 | 🟡 | ⬜ Pending |
| 06.8 | Entitlements endpoint | `GET /v1/me/entitlements` — single source of truth for plan caps so no client hardcodes limits. | bioflow `entitlements_service.py` | 🟡 | ⬜ Pending |
| 06.9 | tz-aware datetimes + decimal money | All timestamps tz-aware, serialized with `Z`; money as decimal strings (`Numeric`), never floats. Avoids client-side rounding/timezone bugs. | pet-portal 25.2 (`money.py`, `datetime_utc.py`) | 🟢 | ⬜ Pending |
| 06.10 | NAT-safe rate limiting | Key rate limits by authenticated user (`user:<id>`) when a Bearer is present, else IP — fair for mobile carrier NAT. Emit `X-RateLimit-*` headers. | bioflow `utils/rate_limit.py` | 🟡 | ⬜ Pending |
| 06.11 | Mobile deep-link return URLs | OAuth / checkout / verification return URLs support app deep links, not just web routes. | bioflow Phase 46 · C | 🟢 | ⬜ Pending |
| 06.12 | App-factory split | Split `main.py` into `app_factory` / `app_middleware` / `router_registry` / `logging_config` (keeps `main.py` ~4 lines, easier to test). | pet-portal `app_factory.py` | 🟡 | ⬜ Pending |
