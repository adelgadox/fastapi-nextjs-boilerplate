# Claude Instructions — FastAPI + Next.js Boilerplate

## REGLA #1 — Git: nunca push a main

**NUNCA hagas `git push` directamente a `main`, sin importar la situación.**

Todo cambio sigue este flujo sin excepción:

1. Crear rama desde `main`:
   ```
   git checkout main && git pull
   git checkout -b feat/mi-feature   # o fix/, refactor/, chore/, docs/
   ```
2. Hacer commits en la rama.
3. Esperar que el usuario pida explícitamente el push: `"haz push"` / `"push"`.
4. Solo entonces: `git push -u origin <rama>`.
5. El PR también requiere aprobación explícita: `"crea el PR"` / `"abre el PR"`.

**Por qué:** cada push puede disparar un deploy en Vercel (costo real). Un push a main sin PR salta el proceso de revisión.

**Comandos bloqueados sin aprobación explícita:**
- `git push` (en cualquier rama)
- `git push origin main` (absolutamente prohibido)
- `gh pr create`
- Cualquier operación destructiva de git (`reset --hard`, `branch -D`, etc.)

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

### Architecture layers

```
routers/    → thin HTTP handlers (validate input, call service, return response)
services/   → business logic (extend BaseService, inject db via constructor)
repositories/ → data access only (extend BaseRepository, no business logic)
schemas/    → Pydantic I/O models (extend StrictModel or StrictORMModel from schemas/_base.py)
```

- Never write `db.query()` in a router — use a repository method.
- Never write business logic in a router — delegate to a service.
- Services are framework-agnostic: no `Request`, `Response`, or `Depends` inside service methods.

### API versioning

All routes are mounted under `/v1`. The constant `_V1 = "/v1"` is defined in `main.py`.

```python
app.include_router(my_router, prefix=_V1)
```

Webhook routes (Stripe, etc.) that are called by third parties with a hardcoded URL remain unversioned.

### Error responses

All errors use a structured envelope — never return a plain `detail` string:

```python
from app.utils.errors import api_error

raise api_error("EMAIL_TAKEN", "Email already registered", field="email")
# → HTTP 400 { "error": { "code": "EMAIL_TAKEN", "message": "...", "field": "email", "meta": null } }
```

### Pydantic v2 strict mode

All schemas extend `StrictModel` (input) or `StrictORMModel` (ORM output) from `app/schemas/_base.py`.
This prevents silent type coercions (e.g. `"1"` auto-converted to `1`).

### Login lockout

`User` has `login_attempts` + `lockout_until` fields. `AuthService.login()` enforces
lockout after 10 consecutive failures for 15 minutes. Reset to 0 on successful login.

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
3. Add repository in `backend/app/repositories/` extending `BaseRepository`
4. Add service in `backend/app/services/` extending `BaseService`
5. Add schemas in `backend/app/schemas/` extending `StrictModel` / `StrictORMModel`
6. Add router in `backend/app/routers/` + register with `app.include_router(x.router, prefix=_V1)` in `main.py`
7. Add server action in `frontend/src/lib/actions.ts`
8. Add page/component in `frontend/src/app/`
9. Update `ROADMAP.md` status
