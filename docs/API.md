# API Endpoints (v1)

Base URL: `http://localhost:8000`

## Auth

- `POST /auth/register`
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'
```

- `POST /auth/login`
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'
```

- `GET /auth/me`
```bash
curl http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"
```

## Sessions

- `POST /sessions` create session
- `GET /sessions` list sessions
- `GET /sessions/{session_id}` returns sources + highlights (also runs weekly check-on-open)
- `POST /sessions/{session_id}/sources` add source (`rss`, `url`, `pdf_url`)
- `POST /sessions/{session_id}/upload-pdf` upload file
- `POST /sessions/{session_id}/ingest` manual trigger

```bash
curl -X POST http://localhost:8000/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"K8s Basics","description":"week 1"}'
```

```bash
curl -X POST http://localhost:8000/sessions/1/sources \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_type":"rss","url":"https://hnrss.org/frontpage"}'
```

```bash
curl -X POST http://localhost:8000/sessions/1/upload-pdf \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./sample.pdf"
```

```bash
curl -X POST http://localhost:8000/sessions/1/ingest \
  -H "Authorization: Bearer $TOKEN"
```

## Quiz + Scores + Flashcards

- `POST /quiz/sessions/{session_id}/generate` with mode `mcq|short|flashcards`
- `POST /quiz/{quiz_id}/submit`
- `GET /quiz/sessions/{session_id}/scores`
- `GET /quiz/flashcards/due`
- `POST /quiz/flashcards/{flashcard_id}/review`

## Settings + Budgets

- `GET /settings`
- `PUT /settings`

Tracks `tokens_in` and `tokens_out` daily. Hosted mode is blocked when daily budget is exceeded. Local mode is always available. `cheap_mode=true` forces local.

## Semantic Search

- `POST /search/semantic`

```bash
curl -X POST http://localhost:8000/search/semantic \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is a Kubernetes pod?","top_k":5}'
```

Returns chunk text and citation (`url`, `title`, `header`, `snippet`).
