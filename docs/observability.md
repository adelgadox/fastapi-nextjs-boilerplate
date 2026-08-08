# Observability — FastAPI + Next.js Boilerplate

Policy in one sentence: **every failure has exactly one recipient, and every
signal states its consequence, not its exception.**

All of this is optional by design — the app runs with none of it configured.
That creates the one risk this document exists to name: **a misconfigured
channel looks identical to a healthy system.** Verification is its own task,
not an assumption (see the runbook at the end).

---

## Signal → destination → expected action

| Signal | Where it lands | What the reader should do |
|--------|----------------|---------------------------|
| Unhandled 500 | Slack `SLACK_ALERT_CHANNEL` + Sentry | Triage: the alert includes Railway/Vercel platform status, so "is it even our code?" is pre-answered |
| ARQ task gave up (3 tries) | Slack | The work was left undone — re-run or fix, the queue will not retry again |
| Cron failed | Slack | The alert states the *consequence* (what stops happening), act on that |
| Cron stopped running | Slack (hourly watchdog) + `/health/jobs` 503 | Check the worker process on Railway |
| Frontend error | Sentry (via `/monitoring` tunnel) | Session replay attached on errors |

## The noise budget

`utils/alert_budget.py`. The first occurrence of a problem goes out in full;
repetitions within 30 minutes are silenced. Grouping is by **problem
identity**, not message text:

| Signal | Identity key |
|--------|--------------|
| Backend 500 | `500:{METHOD path}:{ExceptionType}` |
| Task gave up | `job:{task_name}:{ExceptionType}` |
| Cron failed | `cron:{cron_name}:{ExceptionType}` |
| Stale crons | `heartbeat:{comma-joined names}` |

A different problem always sounds. Without Redis the budget **fails open** and
everything is sent: between a noisy channel and a mute one, the noisy one can
be fixed by reading it.

## Background work: the two decorators

Both live in `app/worker.py` and are applied **at the registration site**
(`WorkerSettings.functions` / the cron definitions) — a single place that
guarantees nothing is registered without an alert path.

- **`alert_on_final_failure`** (tasks): alerts only when ARQ gives up
  (attempt 3 of 3), then always re-raises. Alerting on every attempt would
  triple the noise of a transient timeout that resolves on retry #2.
- **`alert_on_cron_failure`** (crons): alerts and **swallows**. Retrying a
  purge could run it twice, and propagating leaves the failure with no
  recipient at 5am. Alerts state the human consequence from `_CRON_PROMISES`
  ("token tables grow unbounded"), not the exception type.

The worker has its **own Sentry init** — it's a separate process; without it,
worker exceptions only exist in the Railway log.

## The heartbeat: detecting what stops happening

Everything above fires when something fails. A cron that **never runs** raises
nothing — perfect silence while the work goes undone.

- Every successful cron writes a row in `cron_runs` (`services/cron_heartbeat.py`).
- `heartbeat_watchdog_cron` (hourly) alerts when any cron exceeds its window
  in `CRON_MAX_AGE`. Windows live in code, not env: they belong to each cron's
  schedule and change in the same commit that changes the schedule.
- **A watchdog cannot detect its own death.** If the worker never boots, the
  watchdog dies with it. That's why `GET|HEAD /health/jobs` exists: public,
  rate-limited, returns **503 when anything is stale** — point a free uptime
  monitor at it, and the question "is background work running?" gets asked
  from outside the process that might be dead. It deliberately says *that*
  something is behind, never *what*.

Adding a cron = 3 edits, all in the same commit: the cron function
(decorated), its `CRON_MAX_AGE` window, its `_CRON_PROMISES` consequence.

## Sentry

- **Backend** (`main.py`): FastAPI + SQLAlchemy integrations,
  `traces_sample_rate=0.1`, `send_default_pii=False`.
- **Worker** (`worker.py`): separate init, same DSN.
- **Frontend**: three files, all load-bearing —
  - `instrumentation.ts` — server/edge init + `onRequestError` (the only path
    server render errors reach Sentry).
  - `instrumentation-client.ts` — **this filename is required**: Sentry 10+
    no longer reads `sentry.client.config.ts`; with the old name the file
    exists, looks right, and never loads.
  - `src/lib/sentry-environment.ts` — env cascade so preview-branch errors
    don't pollute production (`NODE_ENV` is `"production"` in previews).
  - `tunnelRoute: "/monitoring"` in `next.config.ts`: ad-blockers filter the
    Sentry ingest domain, and the loss is non-random — you lose exactly the
    ad-blocker-using segment, leaving a biased picture that looks complete.
  - The build **fails loudly** when `SENTRY_AUTH_TOKEN` is set without
    `SENTRY_ORG`/`SENTRY_PROJECT` — that silent misconfiguration once cost a
    month of un-uploaded source maps.

## Configuration

| Env var | Effect when unset |
|---------|-------------------|
| `SLACK_BOT_TOKEN` | Alerts stay in the log |
| `SLACK_ALERT_CHANNEL` | Alerts stay in the log (lives in env, not code: a fork must not inherit anyone's channel) |
| `SENTRY_DSN` (backend) | No error tracking, app unaffected |
| `NEXT_PUBLIC_SENTRY_DSN` | No frontend tracking |
| `REDIS_URL` | Noise budget fails open (every alert sends); rate limits per-process |

## What is NOT covered (known gaps)

- No request-ID correlation across services (roadmap 04.1)
- No structured JSON logging (roadmap 04.2)
- `/health` does not check DB readiness (roadmap 04.3)
- No audit log (roadmap 04.8)
- No metrics/dashboards — this layer is alerts + errors only

## Runbook: verify the pipeline end-to-end

Observability that was never tested is indistinguishable from none. After
configuring:

1. **Slack**: `python -c` a direct `notify_slack("test", settings.slack_alert_channel)`
   — confirm delivery; the bot must be invited to the channel.
2. **500 path**: hit a temporary route that raises; confirm the Slack alert
   (with infra status block) and the Sentry event.
3. **Budget**: hit it twice; the second must NOT alert (requires Redis).
4. **Heartbeat**: run the worker once, check `cron_runs` has rows; stop the
   worker, curl `/health/jobs` after a window passes → expect 503.
5. **Frontend**: throw in a client component in preview; confirm the event
   arrives tagged with the preview environment, not production.

Record the date of the last successful verification here: **(not yet run)**
