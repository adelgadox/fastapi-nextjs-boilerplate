# Phase 04 — Observability

You can't operate an API you can't see. Correlation IDs + structured logs +
real health checks are what let you debug a mobile client's failing request in
production. Both reference repos treat this as table stakes.

**Legend** — Complexity: 🟢 Low · 🟡 Medium · 🔴 High · Status: ✅ Done · 🟡 Partial · ⬜ Pending

| # | Task | Description | Source | Complexity | Status |
|---|------|-------------|--------|------------|--------|
| 04.1 | Request-ID middleware | Accept/generate `X-Request-ID` (regex-validated, ≤64 chars), bind to a `ContextVar` + log filter (`%(request_id)s` on every line), tag Sentry scope, echo in response + expose header. | both `middleware/request_id.py` | 🟡 | ⬜ Pending |
| 04.2 | Structured JSON logging | `JsonFormatter` — one JSON object/line (`ts, level, logger, request_id, user_id, msg, exc`), `LOG_FORMAT=json` default (reversible to text), SQLAlchemy engine logs pinned to WARNING. | both `utils/log_config.py` | 🟡 | ⬜ Pending |
| 04.3 | Split `/ping` + `/health` | `/ping` = liveness (always 200); `/health` = readiness (200 only if `SELECT 1` succeeds). Railway waits on `/health` before routing traffic during rolling restarts. Boilerplate `/health` is a static `{"status":"ok"}`. | both | 🟢 | ⬜ Pending |
| 04.4 | Wire Sentry properly | Backend `FastApiIntegration` + `SqlalchemyIntegration` (already present); add frontend client/server/edge configs with Session Replay (`replaysOnErrorSampleRate=1.0`, `maskAllText`), `release=RAILWAY_GIT_COMMIT_SHA`. | both | 🟢 | 🟡 Partial |
| 04.5 | `DBRetryMiddleware` | Retry once on transient Postgres/PgBouncer errors, distinguishing pre-connect (retry any method) vs mid-request (retry idempotent GET/HEAD only) → 503 + enriched Slack alert on failure. | bioflow `main.py` | 🟡 | ⬜ Pending |
| 04.6 | Slack alerting + infra status | 500 handler posts to `SLACK_ALERT_CHANNEL` (env, not hardcoded), enriched with Railway/Vercel incident status, deduped through the noise budget (04.10). | araguaney `main.py` | 🟢 | ✅ Done |
| 04.7 | Compact tracebacks for log caps | `_compact_exc()` one-line app-frame traceback to stay under Railway's 500-logs/sec cap (one unhandled 500 emitted ~185 lines). | bioflow | 🟢 | ⬜ Pending |
| 04.8 | Audit log via SQLAlchemy events | `AuditedMixin` — tag a model with `__audit_entity__`/`__audit_fields__`, get before/after snapshots into `activity_log` via `after_flush`/`after_commit`, in an isolated session so audit failures never poison user txns. | bioflow `models/audit_mixin.py`, pet-portal `core/audit.py` | 🔴 | ⬜ Pending |
| 04.9 | Uptime monitoring | UptimeRobot on frontend + `/health` + `/health/jobs` at 5-min intervals. | both | 🟢 | ⬜ Pending |
| 04.10 | Alert noise budget | `utils/alert_budget.py`: Redis `SET NX EX` dedup keyed by problem identity (`500:{route}:{ExcType}`, `job:...`, `cron:...`), 30-min window, fails open (a mute channel is worse than a noisy one). 6 tests. | araguaney `utils/alert_budget.py` | 🟢 | ✅ Done |
| 04.11 | Cron heartbeat + `/health/jobs` | `cron_runs` table + `record_success`/`stale_crons`; worker decorators `alert_on_final_failure` (task gives up → alert, re-raise) and `alert_on_cron_failure` (alert, swallow, heartbeat on success only) applied at registration site; `_CRON_PROMISES` states human consequences; hourly `heartbeat_watchdog_cron`; public `GET\|HEAD /health/jobs` → 503 when stale (a watchdog can't detect its own death). | araguaney `worker.py`, `cron_heartbeat.py` | 🟡 | ✅ Done |
