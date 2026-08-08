# Installation Guide

## Option A — Docker (recommended, matches production)

Requirements: Docker + Docker Compose.

```bash
cd docker
docker compose up --build
```

This starts Postgres 16 and the backend. The backend container runs
`alembic upgrade head` automatically before starting Uvicorn, so the
schema is created on first boot with no manual steps.

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Postgres: `localhost:5432` / user `aiwse` / password `aiwse_password` / db `aiwse_db`

To stop: `docker compose down`. To also wipe the database volume:
`docker compose down -v`.

## Option B — Local (no Docker)

Requirements: Python 3.12+, a running PostgreSQL 14+ instance.

```bash
# 1. Create the database and user
psql -U postgres -c "CREATE USER aiwse WITH PASSWORD 'aiwse_password';"
psql -U postgres -c "CREATE DATABASE aiwse_db OWNER aiwse;"

# 2. Set up the backend
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# edit .env — set DATABASE_URL to point at your Postgres instance
# (change POSTGRES_HOST=db to POSTGRES_HOST=localhost, or whatever your host is)

# 4. Run migrations
alembic upgrade head

# 5. Start the server
uvicorn app.main:app --reload
```

## Environment variables (`backend/.env`)

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Full Postgres connection string | — |
| `JWT_SECRET_KEY` | Shared signing secret with the token issuer (Module 1 in the full platform) | must be set |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `GEMINI_API_KEY` | Leave empty to use the built-in mock AI provider; set it to switch to real Gemini calls | empty |
| `GEMINI_MODEL` | Gemini model name | `gemini-1.5-pro` |
| `ENVIRONMENT` | Free-text env label, surfaced at `/health` | `development` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:5173,http://localhost:3000` |

## Verifying the install

```bash
curl http://localhost:8000/health
# {"status":"ok","environment":"development"}
```

Then mint a test JWT and call `/api/generate` — see the root `README.md`
"Try it" section for the exact commands.

## Running tests

```bash
psql -U postgres -c "CREATE DATABASE aiwse_test_db OWNER aiwse;"
cd backend && pip install -r requirements.txt
cd .. && pytest -v
```

Tests run against a real Postgres database (`aiwse_test_db`) — nothing is
mocked at the DB layer.
