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

- Never push directly to main — always branch + PR.
- Commit freely, push only when explicitly asked.
- Every push may trigger a Vercel deploy (cost). Ask before pushing.

## Optional layers

Available layers (off by default — enable per project):
Cloudinary, AI/OpenAI, Langfuse, Stripe, Redis, 2FA/TOTP, GeoIP/MaxMind, ElevenLabs+R2.

See `docs/optional-layers.md` for packages, env vars, and code patterns for each.
To activate: uncomment in `requirements.txt`, uncomment in `config.py`, set env vars.

## Adding a new feature

1. Add model in `backend/app/models/` + import in `alembic/env.py`
2. Run `alembic revision --autogenerate -m "description"` + `alembic upgrade head`
3. Add router in `backend/app/routers/` + register in `main.py`
4. Add server action in `frontend/src/lib/actions.ts`
5. Add page/component in `frontend/src/app/`
6. Update `ROADMAP.md` status
