# Phase 08 — Testing & CI

The boilerplate ships **zero tests** and CI only runs CVE audits. For a
foundation that every future project inherits, this is the highest-leverage
debt: a bug in the boilerplate is a bug in every child project.

**Legend** — Complexity: 🟢 Low · 🟡 Medium · 🔴 High · Status: ✅ Done · 🟡 Partial · ⬜ Pending

| # | Task | Description | Source | Complexity | Status |
|---|------|-------------|--------|------------|--------|
| 08.1 | pytest harness vs real Postgres | Run tests against a real Postgres service container (never SQLite), each test in a rolled-back transaction; `scripts/test.py` resets a throwaway DB. | pet-portal `scripts/test.py`, `conftest.py` | 🟡 | ⬜ Pending |
| 08.2 | Unit tests for auth/services | 42 tests shipped: refresh-token rotation/reuse (8), Cloudflare middleware (8), rate-limit key (6) + coverage meta-tests (6), alert budget (6), schema sanitization (7), contract (2). Remaining: login/register/reset verticals. | araguaney `tests/` | 🟡 | 🟡 Partial |
| 08.3 | Integration tests for routes | Real route + SQL tests through the ASGI app with `FakeStorage` override. | pet-portal `tests/`, bioflow Phase 46 · F | 🔴 | ⬜ Pending |
| 08.4 | CI: migration drift guard | Fresh `alembic upgrade head` (fatal on failure) + `alembic check` asserting model↔migration parity and **exactly one head**. | both CI | 🟢 | ⬜ Pending |
| 08.5 | CI: ruff + mypy gate | Wire ruff (lint) + mypy (types) into the pipeline. | both Phase 46 · E1 (⬜) / pet-portal | 🟢 | ⬜ Pending |
| 08.6 | CI: test job | `backend-tests.yml` runs pytest + coverage on every PR touching `backend/**`. Service containers to be added when DB-integration tests land (08.1). | araguaney CI | 🟢 | ✅ Done |
| 08.7 | Coverage gate 80% | Coverage reporting wired in CI (currently ~48%). Raise to a `--cov-fail-under` floor as the suite grows toward 80%. | user standard | 🟢 | 🟡 Partial |
| 08.8 | Strict-schema test | Assert every schema extends `StrictModel`/`StrictORMModel` (prevents silent type coercion regressions). | bioflow `test_strict_schemas.py` | 🟢 | ⬜ Pending |
