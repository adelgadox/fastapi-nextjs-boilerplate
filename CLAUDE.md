# Claude Instructions — FastAPI + Next.js Boilerplate

## Stack

- **Backend:** FastAPI + SQLAlchemy + Alembic + PostgreSQL
- **Frontend:** Next.js 15 (App Router) + Tailwind CSS + NextAuth v5
- **Auth:** JWT (PyJWT) + bcrypt, token denylist for logout revocation
- **Email:** Resend + Jinja2 templates in `backend/app/templates/emails/`
- **Alerts:** Slack Bot via `chat.postMessage` (`utils/slack.py`)
- **Error tracking:** Sentry (backend + frontend)

## Backend conventions

- All settings come from `app/config.py` (pydantic-settings). Never hardcode values.
- Rate limiting via `@limiter.limit()` on every public/auth endpoint.
- IP detection uses `utils/cloudflare.py` — always use `get_client_ip(request)`, never `request.client.host`.
- New models must be imported in `alembic/env.py` for autogenerate to work.
- Email functions go in `app/email.py`. Templates in `app/templates/emails/*.html`.
  Always add `<meta name="color-scheme" content="light">` to email templates (Gmail dark mode).
- `frontend_url` may be comma-separated (multi-origin CORS). When building URLs for emails,
  always use `settings.frontend_url.split(",")[0].strip()`.

## Frontend conventions

- All mutations go in `src/lib/actions.ts` with `"use server"`.
- API calls use `apiFetch` from `src/lib/api.ts`.
- Auth: use `auth()` from `@/auth` in Server Components, `useSession` in Client Components.
  Never use `getServerSession`.
- No test files — verify manually by running `npm run dev`.

## Git workflow

**Branch discipline — non-negotiable:**
- `main` is protected. Never commit or push directly to `main`.
- Every feature, bug fix, refactor, or chore starts from a fresh branch off `main`:
  ```
  git checkout main && git pull
  git checkout -b feat/my-feature   # or fix/, refactor/, chore/, docs/
  ```
- Branch naming: `feat/`, `fix/`, `refactor/`, `chore/`, `docs/` prefix + short slug.
- Open a PR to `main` when the work is done. Squash or merge — never force-push to main.

**Commit & push rules:**
- Commit freely and often on your branch — no approval needed.
- `git push` requires explicit user approval (may trigger Vercel deploy = cost).
- `gh pr create` requires explicit user approval (visible to others).
- After completing work, say: "Commiteado en `branch-name`. ¿Hacemos push y PR?"

## Optional layers

Available layers (off by default — enable per project):
Cloudinary, AI/OpenAI, Langfuse, Stripe, Redis, 2FA/TOTP, GeoIP/MaxMind, ElevenLabs+R2.

See `docs/optional-layers.md` for packages, env vars, and code patterns for each.
To activate: uncomment in `requirements.txt`, uncomment in `config.py`, set env vars.

## Security

See `docs/security.md` for:
- What's active by default (rate limiting, JWT denylist, security headers, etc.)
- Required per-project steps (Cloudflare-only mode, CSP headers, input sanitization)
- Pre-launch security checklist
- Optional security layers (2FA, webhook verification, Safe Browsing, etc.)

## Adding a new feature

1. Add model in `backend/app/models/` + import in `alembic/env.py`
2. Run `alembic revision --autogenerate -m "description"` + `alembic upgrade head`
3. Add router in `backend/app/routers/` + register in `main.py`
4. Add server action in `frontend/src/lib/actions.ts`
5. Add page/component in `frontend/src/app/`
6. Update `ROADMAP.md` status
