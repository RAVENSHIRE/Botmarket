# Botmarket

What happens when machines create their own economy? BOTMARKET is a fictional autonomous economic simulation where digital agents—not humans—control the market ecosystem. The goal is to simulate an evolving digital society where agents trade, communicate, form alliances, disagree, and create emergent market behavior.

> **Status:** MVP foundation. This phase delivers a working AI-agent ecosystem
> prototype (FastAPI backend + Next.js dashboard). Blockchain, real AI models
> and an external agent SDK are intentionally deferred behind clean interfaces —
> see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## What's inside

| Area | Stack | Location |
|---|---|---|
| Backend API | Python 3.12, FastAPI, SQLAlchemy | [`backend/`](backend/) |
| Agents | Trader · Meme · Analyst archetypes | [`backend/app/agents/`](backend/app/agents/) |
| Simulation | Tick-based engine + market/events | [`backend/app/simulation/`](backend/app/simulation/) |
| Frontend | Next.js, TypeScript, Tailwind CSS | [`frontend/`](frontend/) |
| Tests | pytest | [`tests/`](tests/) |

### API endpoints
`GET /health` · `GET /agents` · `POST /agents` · `GET /agents/{id}` ·
`GET /feed` · `GET /leaderboard` · `POST /simulation/tick` ·
`GET /simulation/state`

## Running locally

### Option A — Docker (full stack)

Brings up backend, frontend, PostgreSQL and Redis:

```bash
cp .env.example .env
docker compose up --build
```

- Dashboard: http://localhost:3000
- API docs:  http://localhost:8000/docs

### Option B — Backend only (SQLite, zero setup)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# (optional) create a starter roster of agents
python backend/seed.py

# run the API
uvicorn app.main:app --reload --app-dir backend
```

Then advance the world:

```bash
curl -X POST http://localhost:8000/simulation/tick
curl http://localhost:8000/feed
```

### Frontend (dev)

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

Set `NEXT_PUBLIC_API_URL` if the backend is not on `http://localhost:8000`.

## Testing

```bash
source .venv/bin/activate
pip install -r requirements.txt
pytest -q            # from the repository root
```

Tests cover agent creation, simulation ticks, API endpoints and database
models, and run against an isolated temporary SQLite database.

## Project layout

```
backend/app/
  main.py            FastAPI app + startup
  config.py          settings (env-driven)
  database.py        SQLAlchemy engine/session (SQLite ⇄ Postgres)
  models.py          Agent · Post · Event · Transaction · Reputation
  agents/            base_agent · personality · memory · strategies · types
  simulation/        engine · events · market
  social/            posts · conversations
  api/routes.py      HTTP endpoints
frontend/            Next.js dashboard (feed · agents · simulation · leaderboard)
docs/                architecture notes
tests/               pytest suite
```

## License

MIT — see [LICENSE](LICENSE).
