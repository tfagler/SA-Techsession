# Runbook

## 1) Prepare env

```bash
cp .env.example .env
```

Optional: set `LOCAL_LLM_URL`, `HOSTED_LLM_URL`, and `HOSTED_LLM_API_KEY` in `.env`.

## 2) Start stack

```bash
docker compose -f infra/docker-compose.yml up --build
```

Services:
- web: http://localhost:5173
- api: http://localhost:8000
- mysql: localhost:3306
- redis: localhost:6379

## 3) Migrate schema manually (if needed)

```bash
docker compose -f infra/docker-compose.yml exec api alembic upgrade head
```

## 4) Seed admin user

```bash
docker compose -f infra/docker-compose.yml exec api \
  env ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=admin12345 python -m app.seed
```

## 5) Quick test (API)

```bash
docker compose -f infra/docker-compose.yml exec api pytest -q
```

## 6) Manual session flow test

1. Register/login via web UI.
2. Create session.
3. Add one `rss` source and one `url` source.
4. Upload one PDF and/or add one `pdf_url` source.
5. Trigger ingest.
6. Open session and verify highlights with citations appear.
7. Generate quiz, submit answers, inspect score history.
8. Update budget/cheap mode in settings and confirm hosted calls block on budget exhaustion.

## 7) Kubernetes-ready notes

- Build images from `api/Dockerfile`, `worker/Dockerfile`, `web/Dockerfile`.
- Externalize env vars as K8s secrets/config maps.
- Use PVCs for MySQL data and documents volume.
- Run Alembic as an init job before API rollout.
