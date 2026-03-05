# SA-Techsession

Container-first multi-user study app that ingests RSS/HTML/PDF sources into sessions, builds educational outputs (summary, lesson points, glossary, quiz), and supports quiz practice with score tracking.

## What The App Does

- User registration/login (JWT auth)
- Create study sessions and attach sources:
  - RSS feed URL
  - Website URL
  - PDF upload
  - PDF URL
- Trigger ingest jobs through Celery worker
- Extract and clean readable content into chunks
- Generate education output schema per session:
  - `summary`
  - `key_points`
  - `glossary`
  - `quiz`
- Generate quiz attempts and track score history
- Optional Ollama-powered generation (`USE_OLLAMA=true`)

## Architecture

```text
+---------+        HTTP         +---------+
|   web   | <-----------------> |   api   |
| React   |                     | FastAPI |
+---------+                     +----+----+
                                     |
                                     | enqueue jobs / cache
                                     v
                               +-----+-----+
                               |   redis   |
                               +-----+-----+
                                     |
                                     | consume jobs
                                     v
                               +-----+-----+
                               |  worker   |
                               |  Celery   |
                               +-----+-----+
                                     |
                           read/write| schema/data
                                     v
                               +-----+-----+
                               |   mysql   |
                               +-----------+

Optional LLM path:
worker/api --HTTP--> ollama (/api/generate)
```

## Setup (Docker Compose)

1. Copy env file:

```bash
cp .env.example .env
```

2. Start stack:

```bash
docker compose -f infra/docker-compose.yml up --build
```

3. Optional: start with local Ollama container profile:

```bash
docker compose -f infra/docker-compose.yml --profile ollama up --build
```

4. Open UI:
- Web: http://localhost:5173
- API: http://localhost:8000

## Sessions, Sources, Ingest Flow

1. Create session in Dashboard.
2. Add source(s) in Session page.
   - URL sources can crawl up to N levels with configurable limits (depth/pages/links/domain/path filters/concurrency/delay).
3. Click `Trigger Ingest`.
4. Session status transitions:
- `queued`
- `running`
- `done` or `failed`
5. UI polls while queued/running and renders:
- Summary
- Lesson key points
- Glossary
- Education quiz

## Ollama Integration

- Enabled by `LOCAL_LLM_ENABLED=true` (or per-user preference in Settings).
- Uses:
  - `OLLAMA_BASE_URL`
  - `OLLAMA_MODEL`
  - `OLLAMA_TIMEOUT_SECONDS`
- Each request is logged with endpoint, model, latency, and char counts.
- `OLLAMA_BASE_URL` should be root host URL (example `http://192.168.252.6:11434`).
- If `/api` is included by mistake, the app normalizes it to root and calls `{base}/api/generate`.
- If disabled (`USE_OLLAMA=false`), deterministic local generation is used.

## Env Vars

- `DATABASE_URL` async runtime DB URL (e.g. `mysql+aiomysql://...`)
- `REDIS_URL`
- `JWT_SECRET`
- `JWT_ALGORITHM`
- `JWT_EXPIRE_MINUTES`
- `DOCS_DIR`
- `CORS_ORIGINS`
- `EMBED_DIM`
- `USE_OLLAMA` (`true|false`)
- `OLLAMA_BASE_URL` (default `http://host.docker.internal:11434`)
- `OLLAMA_MODEL` (default `llama3.1`)
- `OLLAMA_TIMEOUT_SECONDS` (default `180`)
- `LOCAL_LLM_URL` (default `http://host.docker.internal:11434`, primary env default source for local LLM endpoint)
- `LOCAL_LLM_MODEL` (primary env default source for local LLM model)
- `LOCAL_LLM_ENABLED` (`true|false`, explicit env control for local LLM default enable)
- `LOCAL_LLM_CONTEXT_TOKENS` (context limit hint for prompt budgeting)
- `LOCAL_LLM_PROMPT_BUDGET_TOKENS` (max estimated prompt tokens before truncate/reject)
- `LOCAL_LLM_PROMPT_POLICY` (`truncate` or `reject`)
- `OLLAMA_TIMEOUT_CONNECT_SECONDS`, `OLLAMA_TIMEOUT_READ_SECONDS`, `OLLAMA_TIMEOUT_WRITE_SECONDS`, `OLLAMA_TIMEOUT_POOL_SECONDS`
  - Default read timeout is `180s` for long local generations.
- `CRAWL_DEPTH`, `CRAWL_MAX_PAGES`, `CRAWL_MAX_LINKS_PER_PAGE`
- `CRAWL_ALLOWED_DOMAINS`, `CRAWL_INCLUDE_PDFS`
- `CRAWL_INCLUDE_PATHS`, `CRAWL_EXCLUDE_PATHS`
- `CRAWL_RESPECT_ROBOTS`, `CRAWL_CONCURRENCY`, `CRAWL_REQUEST_DELAY_MS`

## Tests / Quality

Run API tests:

```bash
docker compose -f infra/docker-compose.yml exec api pytest -q
```

No dedicated lint script is configured yet.

## Troubleshooting

- `404 Not Found` on Ollama `/api/generate`:
  - Ensure `OLLAMA_BASE_URL` points to root URL, not `/api/generate`.
  - From inside worker, verify Ollama endpoints:
    - `docker compose -f infra/docker-compose.yml exec worker sh -lc "curl -sS http://192.168.252.6:11434/api/version"`
    - `docker compose -f infra/docker-compose.yml exec worker sh -lc "curl -sS http://192.168.252.6:11434/api/tags"`
    - `docker compose -f infra/docker-compose.yml exec worker sh -lc "curl -sS -X POST http://192.168.252.6:11434/api/generate -H 'Content-Type: application/json' -d '{\"model\":\"llama3\",\"prompt\":\"hello\",\"stream\":false}'"`
  - App now builds endpoint URLs via URL parsing/joining and will fallback to `/api/chat` if `/api/generate` returns `404`.
  - App probes `/api/version` and `/api/tags` and retries generation with backoff.
  - To set URL/model in compose, use `.env` values consumed by `infra/docker-compose.yml`:
    - `OLLAMA_BASE_URL=http://192.168.252.6:11434`
    - `OLLAMA_MODEL=llama3`
  - Settings page shows effective local LLM URL/model and source (`user_pref` vs `env_default` vs `fallback`).
- `Future attached to a different loop` in worker:
  - Worker now runs `-P solo --concurrency=1` and task creates DB engine/session per execution context.
- Ingest fails with unreadable PDF text:
  - Chunks with PDF structure tokens/non-printable junk are filtered.
  - If all chunks are filtered, session status becomes `failed` with `ingest_error`.
- PDF URL returns `304 Not Modified` and ingest fails:
  - Worker now uses local cached PDF bytes when available.
  - If no local bytes are cached, it retries once with `Cache-Control: no-cache` and `Pragma: no-cache`.
- Crawl appears too small:
  - Increase `crawl_depth`, `max_pages`, and `max_links_per_page` in source crawl config.
  - Check session ingest metrics and skip reasons in UI (`external_domain`, `already_seen`, `excluded_pattern`, etc.).
- Quiz contains `%PDF-` artifacts:
  - PDF ingestion extracts text via `pypdf.extract_text()` and removes low-quality/PDF-structure chunks before quiz generation.
- Education output not shown:
  - Check session `ingest_status` and `ingest_error` / `education_error` in Session page.
  - If Ollama fails, session is marked `failed` and error is stored.
- API cannot reach DB at startup:
  - MySQL healthcheck gates API/worker startup.
- No LLM output:
  - Verify `USE_OLLAMA=true` and reachable `OLLAMA_BASE_URL`, or use deterministic fallback with `USE_OLLAMA=false`.
  - Check logs for `final_prompt_char_len` and `estimated_token_len`; prompts are capped by policy to reduce timeouts.
- Auth 401 in logs while UI stays on page:
  - Frontend now auto-logs out and redirects to sign-in when API returns 401.

## Changelog (Latest Fixes)

- Fixed worker loop-context reliability for ingest tasks.
- Added session ingest lifecycle fields and UI polling (`queued/running/done/failed`).
- Reworked extraction to keep only cleaned, high-quality human-readable chunks.
- Prevented quiz generation from PDF/binary junk chunks.
- Added structured education output persistence and UI rendering.
- Added optional Ollama integration with explicit request logging and fallback mode.
