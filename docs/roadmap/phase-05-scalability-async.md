# Phase 05 — Scalability: Caching, Async & Database

Performance and correctness under load: a Redis caching strategy, fixing the
sync-engine-under-async trap, connection pooling for PgBouncer, and the index
patterns both reference repos use on hot read paths.

**Legend** — Complexity: 🟢 Low · 🟡 Medium · 🔴 High · Status: ✅ Done · 🟡 Partial · ⬜ Pending

| # | Task | Description | Source | Complexity | Status |
|---|------|-------------|--------|------------|--------|
| 05.1 | Two-tier caching strategy | Redis (shared across workers, TTL matched to frontend ISR) + per-process `TTLCache` fallback, unified invalidation with version-bump keys. Boilerplate has `utils/cache.py` (no-op when Redis unset) — extend to the listing/profile pattern. | bioflow `utils/cache.py`+`profile_cache.py`, pet-portal `core/cache.py` | 🟡 | 🟡 Partial |
| 05.2 | Redis as rate-limit + 2FA store | Point slowapi `storage_uri` at `REDIS_URL` (in-memory today → per-worker, unfair). Back the 2FA attempt limiter with Redis + in-memory fallback (shared across workers). | pet-portal `app_factory.py`, `core/totp.py` | 🟡 | ⬜ Pending |
| 05.3 | Fix sync-engine-under-async | Audit `async def` handlers doing blocking DB/bcrypt/HTTP work. Convert to `def` (threadpool) or `AsyncSession`; wrap bcrypt in `asyncio.to_thread`. The boilerplate is sync SQLAlchemy under async FastAPI throughout. | bioflow Phase 46 · D1/D2, pet-portal | 🔴 | ⬜ Pending |
| 05.4 | PgBouncer two-mode pooling | `PGBOUNCER_MODE=true` → `NullPool` + `prepare_threshold=None`; else `pool_size=5, max_overflow=10, pool_pre_ping, pool_recycle=300`; TCP keepalives to survive Railway idle-drop; Alembic uses the direct URL. Boilerplate has the two modes — document + verify keepalives. | both `database.py` | 🟢 | 🟡 Partial |
| 05.5 | Performance indexes | Create indexes `CONCURRENTLY` inside `autocommit_block()` with `if_not_exists`: composite on hot read paths (e.g. `(user_id, position)`), partial `WHERE is_active`, `pg_trgm` GIN for ILIKE search. Document the "why" in each migration. | bioflow `0070_*`, `0068_*`; pet-portal `0013` | 🟡 | ⬜ Pending |
| 05.6 | ARQ durable queue + crons | Boilerplate has `arq_pool.py` + `worker.py` (in-process fallback). Add the cron scheduler pattern (denylist cleanup, digests, expiry) each wrapped with a Slack failure alert. Deploy a **separate worker service** on Railway. | both `worker.py`, `docs/ops/arq-worker.md` | 🟡 | 🟡 Partial |
| 05.7 | Index benchmark script | `scripts/bench_catalog.py` — `EXPLAIN ANALYZE` before/after, N=100k, to justify each index. | pet-portal `scripts/bench_catalog.py` | 🟢 | ⬜ Pending |
| 05.8 | Migrations out of boot loop | Move `alembic upgrade head` from the container CMD to a Railway release step so >1 replica doesn't race. Use a `pg_advisory_lock` in `env.py` to serialize. | pet-portal `env.py`, bioflow Phase 46 · E3 | 🟡 | ⬜ Pending |
