# [Project Name]

> [One-line description of the project]

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + SQLAlchemy + Alembic |
| Frontend | Next.js 15 + Tailwind CSS |
| Auth | NextAuth v5 (JWT) + bcrypt |
| Database | PostgreSQL |
| Email | Resend + Jinja2 templates |
| Storage | Cloudinary (images) |
| Error tracking | Sentry (backend + frontend) |
| Alerts | Slack Bot (`chat.postMessage`) |
| Hosting | Railway (backend + DB) · Vercel (frontend) |

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── routers/          # FastAPI route handlers
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── utils/            # Shared utilities (rate_limit, slack, cloudflare)
│   │   ├── templates/
│   │   │   └── emails/       # Jinja2 HTML email templates
│   │   ├── config.py         # Pydantic settings — reads from .env
│   │   ├── database.py       # SQLAlchemy engine + session + Base
│   │   ├── dependencies.py   # Auth dependencies (get_current_user, etc.)
│   │   ├── email.py          # Resend send functions
│   │   └── main.py           # App factory, middleware, routers
│   ├── alembic/              # Database migrations
│   │   └── versions/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/              # Next.js App Router pages
│       ├── components/       # Shared UI components
│       ├── lib/
│       │   ├── actions.ts    # Server actions ("use server")
│       │   └── api.ts        # apiFetch typed helper
│       └── types/            # Shared TypeScript interfaces
├── docker-compose.yml        # Local dev: backend + frontend + PostgreSQL
├── .env.example              # All env vars documented
└── ROADMAP.md                # Project roadmap template
```

## Getting Started

### Prerequisites
- Docker + Docker Compose
- Node.js 20+
- Python 3.12+

### Local development with Docker (recommended)

```bash
# 1. Copy and fill env vars
cp .env.example backend/.env
cp .env.example frontend/.env.local
# Edit both files

# 2. Start all services
docker compose up --build

# 3. Run migrations (first time only)
docker compose exec backend alembic upgrade head
```

### Without Docker

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
cp ../.env.example .env.local
npm run dev
```

## Environment Variables

See `.env.example` for all variables with descriptions.

### Backend (`backend/.env`)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing secret (`openssl rand -hex 32`) |
| `FRONTEND_URL` | Frontend URL(s) for CORS — comma-separated |
| `INTERNAL_API_SECRET` | Shared secret for server-to-server endpoints |
| `RESEND_API_KEY` | Resend API key for transactional email (optional) |
| `SENTRY_DSN` | Sentry DSN — backend error tracking (optional) |
| `SLACK_BOT_TOKEN` | Slack Bot OAuth token `xoxb-...` (optional) |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|----------|-------------|
| `NEXTAUTH_SECRET` | NextAuth signing secret |
| `API_URL` | FastAPI base URL — server-side calls |
| `NEXT_PUBLIC_API_URL` | FastAPI base URL — client-side calls |
| `INTERNAL_API_SECRET` | Same value as backend |

## Database Migrations

```bash
# Generate a new migration from model changes
alembic revision --autogenerate -m "add users table"

# Apply all pending migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

## Deployment

| Service | Platform | Notes |
|---------|----------|-------|
| Backend | Railway | Set env vars, run `alembic upgrade head` on release |
| Frontend | Vercel | Connect repo, set env vars in dashboard |
| Database | Railway PostgreSQL addon | Auto-injects `DATABASE_URL` |

## What's included

- JWT auth with token denylist (logout revocation)
- Email + password register with email verification flow
- Password reset flow
- Role-based access control (`user` / `admin` / `superadmin`)
- Rate limiting on all sensitive endpoints (slowapi + Cloudflare IP detection)
- Security headers middleware (X-Frame-Options, CSP-ready, etc.)
- Sentry error tracking wired on backend and frontend
- Slack Bot alert on unhandled 500 errors (`#backend-alerts`)
- GZip compression
- CORS configured for multi-origin (comma-separated `FRONTEND_URL`)
- PgBouncer-compatible connection pooling mode
- Alembic migrations with autogenerate
- Docker Compose for full local stack
