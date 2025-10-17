## MoodTra Backend

FastAPI backend for MoodTra: chat, mood logging, and strategy recommendations. Ships with SQL schema/seed, AI pipeline integration, and production-ready Docker image.

### Stack

- **API**: FastAPI (`api/main.py`) served by Uvicorn
- **DB**: PostgreSQL (SQLAlchemy)
- **Auth headers**: `x-account-id`, `x-session-id` (dev mocks supported)
- **AI**: Gemini 2.5 via `google-genai`, HuggingFace `transformers` emotion model

### Quickstart

1. Python 3.11+ and Postgres running locally (or Docker)
2. Create venv and install deps:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

3. Set environment variables (see Env vars).
4. Run API:

```bash
fastapi dev api/main.py
```

Open Swagger at http://127.0.0.1:8000/docs

### Env vars

- **DATABASE_URL**: SQLAlchemy URL to Postgres (required)
- **GOOGLE_API_KEY**: Required for AI `AI/pipeline.py`
- Optional (Cognito verification if used): `COGNITO_USER_POOL_ID`, `COGNITO_REGION`, `COGNITO_AUDIENCE`

### API overview

- `GET /health`: liveness check
- `POST /api/chat`: chat with AI; requires `x-account-id` and `x-session-id`
- `GET /strategy`: list all strategies
- `GET /strategy/emojis/{emoji}`: strategies for a specific emotion
- `POST /activity`, `PATCH /activity/{id}`, `GET /activity`: manage selected strategies
- `POST /mood/entries`, `PATCH /mood/entries/{date}`, `DELETE /mood/entries/{date}`: manage moodlog
- `GET /mood/entries`, `GET /mood/summary/weekly`, `GET /mood/summary/monthly`: manage emotion report

Headers commonly required:

```text (mock data)
x-account-id: 00000000-0000-0000-0000-00000000C0DE
x-session-id: 11111111-1111-1111-1111-111111111111
```

### Project layout

```text
api/
  main.py              # FastAPI app and CORS
  db.py                # SQLAlchemy engine (uses DATABASE_URL)
  deps.py              # DI: db, account/session headers (mockable)
  routers/             # chat, mood, activity, strategy, etc.
AI/
  pipeline.py          # Gemini + transformers emotion detection
sql/
  schema.sql, seed.sql # DB schema and seed data
```

### Notes

- Swagger is at `/docs`. CORS allows `localhost:3000` and production domains.
- AI requires `GOOGLE_API_KEY`. HuggingFace models download at runtime; caches redirected to tmp in Docker.
- For date ranges, weekly/monthly summaries are inclusive of the anchor date.

### License

See `LICENSE`.

