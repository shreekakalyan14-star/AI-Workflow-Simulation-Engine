# Deployment Guide

## Container image

The backend `Dockerfile` builds a standalone image (`python:3.12-slim`
base) that runs migrations then starts Uvicorn:

```bash
cd backend
docker build -t aiwse-backend:latest .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@your-db-host:5432/aiwse_db \
  -e JWT_SECRET_KEY=<shared-secret-with-token-issuer> \
  -e GEMINI_API_KEY=<your-key-or-empty> \
  aiwse-backend:latest
```

## Production checklist

- **Database**: use a managed Postgres (RDS, Cloud SQL, etc.) rather than
  the container in `docker-compose.yml`, which is for local dev only.
  Point `DATABASE_URL` at it and run `alembic upgrade head` as a release
  step (the Dockerfile's `CMD` already does this on every boot, which is
  safe — Alembic no-ops if already at head).
- **Secrets**: `JWT_SECRET_KEY` must match whatever service issues tokens
  in the parent platform (Module 1). Never commit it; inject via your
  orchestrator's secret manager.
- **Gemini**: set `GEMINI_API_KEY` in production to move off the mock AI
  provider — no code changes required, `get_ai_service()` in
  `app/services/ai_service.py` picks it up automatically.
- **CORS**: set `CORS_ORIGINS` to your real frontend origin(s), not
  `localhost`.
- **Process manager**: run Uvicorn behind Gunicorn with the Uvicorn worker
  class for multi-process concurrency in production, e.g.:
  ```bash
  gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000
  ```
  (add `gunicorn` to `requirements.txt` when you adopt this).
- **Reverse proxy / TLS**: terminate TLS at a load balancer or reverse
  proxy (nginx, ALB, etc.) in front of the container; the app itself
  serves plain HTTP.
- **Migrations on scale-out**: if running multiple replicas, run
  `alembic upgrade head` as a separate one-shot job/init container rather
  than relying on every replica's boot command racing each other. Alembic
  migrations are wrapped in transactions, so concurrent `upgrade head`
  calls are safe but redundant — a dedicated migration step is cleaner.
- **Health checks**: point your orchestrator's liveness/readiness probe at
  `GET /health`.

## Scaling

The service is stateless aside from the database — horizontal scaling is
just running more backend replicas behind a load balancer, all pointed at
the same Postgres instance.
