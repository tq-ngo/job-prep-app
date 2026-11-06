# JobPrep

A full-stack platform that helps software engineers find internships. It crawls SWE internship postings from curated GitHub repositories and LinkedIn, extracts and sanitizes each posting's full description, links duplicates across sources, enriches listings with Google Gemini (skills, pay, embeddings) and pushes new roles to the browser live. A tech-news radar summarizes industry articles alongside the board.

## Features

- **Job board**: search and filter (category, source, remote) with a list beside the selected job's details, or one at a time on phones. Filters, page and selected job live in the URL.
- **Live updates**: new postings arrive over Server-Sent Events.
- **AI enrichment**: Gemini extracts skills, compensation and seniority; pgvector powers semantic search.
- **News radar**: daily LinkedIn headlines plus any article URL you paste, summarized by Gemini.
- **Accounts**: email/password or Google sign-in, with HttpOnly cookie sessions and tracked skills for alerts.

## Architecture

```text
browser ──► nginx :80 ──┬──► Next.js frontend (SSR, route guard)
                        └──► FastAPI /api ──► PostgreSQL 16 (pgvector, pg_trgm)
                                          └──► Redis 7 (cache, dedup, sessions, event stream)
                        Celery worker + beat ──► GitHub / LinkedIn / news sites, Gemini
```

| Part     | Stack                                                                                     |
| :------- | :---------------------------------------------------------------------------------------- |
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, TanStack Query            |
| API      | FastAPI, Python 3.11, SQLModel / SQLAlchemy 2 (asyncpg), Alembic                          |
| Workers  | Celery 5 + Beat on Redis; `curl_cffi` scraping, `nh3` sanitization, `google-genai`        |
| Data     | PostgreSQL 16 with pgvector (HNSW) and pg_trgm; Redis 7                                   |
| Edge     | nginx: single origin, rate limits, security headers, unbuffered SSE                       |

## Quick start (Docker)

Requires Docker with Compose v2.

```bash
cp .env.example .env
```

Edit `.env` and replace every `CHANGE_ME` value. The Redis password must also appear in the three `redis://:<password>@…` URLs, and the Postgres password in `DATABASE_URL`. Generate `SECRET_KEY` with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Then start the stack:

```bash
docker compose up --build -d
```

| URL                           | What                                                                 |
| :---------------------------- | :------------------------------------------------------------------- |
| http://localhost              | The app (through nginx)                                              |
| http://127.0.0.1:8000/docs    | API docs (dev only; disabled when `APP_ENV=production`)              |
| http://127.0.0.1:5555         | Flower, the Celery dashboard (dev only; `FLOWER_BASIC_AUTH` login)   |

Migrations run automatically when the backend starts. The board fills as Celery Beat runs the crawlers (GitHub every 6 hours, LinkedIn daily), or immediately with **Refresh** on the Jobs page.

AI features stay off until `GEMINI_API_KEY` is set. Google sign-in stays off until `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set; register the redirect URI `http://localhost/api/v1/auth/google/callback`.

### Dev vs. production compose

`docker-compose.override.yml` is applied automatically and adds the development conveniences: loopback ports for Postgres, Redis, the API and the frontend, a live-reloading backend, and Flower. For the production shape (only nginx exposed, no bind mounts, no Flower):

```bash
docker compose -f docker-compose.yml up --build -d
```

For production also set `APP_ENV=production`, `COOKIE_SECURE=true`, your domain in `SERVER_NAME`, `CORS_ORIGINS` and `FRONTEND_URL`, and terminate TLS in front of nginx. `infra/nginx/tls.conf.example` is a starting point.

## Local development without Docker for the apps

Start only the data services from compose (`docker compose up -d postgres redis`), then:

```bash
# API
cd backend
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Workers (separate terminals)
celery -A app.tasks.celery_app worker --loglevel=info -Q default,scraping,ai
celery -A app.tasks.celery_app beat --loglevel=info --schedule /tmp/celerybeat-schedule

# Frontend: proxies /api to INTERNAL_API_URL (default http://localhost:8000)
cd frontend
npm ci
npm run dev
```

The backend reads a `.env` from its working directory (`backend/`), not the repository root. Copy the root `.env` to `backend/.env` and point `DATABASE_URL` and the three Redis URLs at `localhost` instead of the compose service names (`postgres`, `redis`).

## Testing

```bash
# Backend: unit, integration and pipeline tests (SQLite + fakeredis, no services needed)
cd backend && pytest -m "not pg"

# Backend: tests against a real, migrated PostgreSQL with pgvector
PG_TEST_URL=postgresql+asyncpg://user:pass@localhost:5432/jobprep_test pytest -m pg
alembic check   # models and migrations agree

# Frontend
cd frontend
npm run lint && npx tsc --noEmit && npm test
npm run check:contrast   # WCAG contrast audit of the colour tokens
npm run build
```

GitHub Actions runs all of these on every pull request (`.github/workflows/ci.yml`), and validates the compose files, nginx config and Docker images when infrastructure changes (`docker.yml`).

## Configuration

Every variable is listed with comments in [`.env.example`](.env.example). The ones you'll usually touch:

| Variable                                          | Purpose                                                                   |
| :------------------------------------------------ | :------------------------------------------------------------------------ |
| `SECRET_KEY`                                      | Signs session tokens (32+ characters; also used by the frontend's guard)  |
| `POSTGRES_PASSWORD`, `REDIS_PASSWORD`             | Data-service credentials (also embedded in the connection URLs)           |
| `GEMINI_API_KEY`                                  | Enables AI enrichment, summaries and semantic search                      |
| `GEMINI_REQUESTS_PER_MINUTE`                      | Shared Gemini call budget; keep it under your API quota                   |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`        | Enables "Continue with Google"                                            |
| `APP_ENV`, `COOKIE_SECURE`, `SERVER_NAME`, `FRONTEND_URL` | Production settings (see above)                                   |

## Project layout

```text
backend/    FastAPI app (app/), Alembic migrations, Celery tasks, tests
frontend/   Next.js app (src/app), UI components (src/components), hooks, tests
infra/      nginx config and templates, Postgres init script
.github/    CI workflows
```
