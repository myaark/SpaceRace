# Backend Setup Guide

How to get the backend services running locally, both via Docker Compose
(recommended for running everything together) and standalone without Docker
(for working on a single service).

Services: `AuthService`, `PlayerService`, `MatchmakingService`,
`GameSessionService`, `LeaderboardService`. All are Python 3.12 / FastAPI,
served with `uvicorn app.main:app` on container port 8000.

| Service | Host port (compose) | Depends on |
|---|---|---|
| auth-service | 8001 | postgres |
| player-service | 8002 | postgres |
| matchmaking-service | 8003 | redis |
| game-session-service | 8004 | redis |
| leaderboard-service | 8005 | postgres, redis |

## Prerequisites

- Docker + Docker Compose (for the compose path)
- Python 3.12 (for the no-Docker path)
- `git`

## Option A — Docker Compose (all services + infra)

This is the default way to run the full backend locally: it starts Postgres,
Redis, and every service together, wired up per `docker-compose.yml`.

1. From the repo root, create each service's `.env` from its example:

   ```bash
   for svc in AuthService PlayerService MatchmakingService GameSessionService LeaderboardService; do
     cp "Backend/$svc/.env.example" "Backend/$svc/.env"
   done
   ```

   Adjust values as needed (defaults work for local dev against the
   compose Postgres/Redis containers).

2. Bring up the stack:

   ```bash
   ./scripts/dev.sh
   ```

   This runs `docker compose up --build` from the repo root. Services come
   up on `localhost:8001`–`8005`; Postgres on `5432`, Redis on `6379`.

3. Tear down when done:

   ```bash
   ./scripts/down.sh
   ```

To run only a subset (e.g. one service plus the infra it needs), use
`docker compose up --build <service-name> <its-deps>`, e.g.:

```bash
docker compose up --build postgres auth-service
```

## Option B — Generic no-Docker setup (any single service)

Use this when iterating on one service without spinning up the whole
compose stack. The steps are the same shape for every service — swap in
the service's folder name.

1. **Provide infra it depends on.** Each service's `.env.example` tells you
   what it needs (`DATABASE_URL` → Postgres, `REDIS_URL` → Redis — see the
   table above for which). Either:
   - point `.env` at infra you already have running locally, or
   - start just the infra containers from compose: `docker compose up postgres redis`.

2. **Create a virtualenv and install dependencies**, from inside the
   service folder:

   ```bash
   cd Backend/<ServiceName>
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

   If the service has a `requirements-dev.txt` (adds test/lint deps on top
   of `requirements.txt`), install that instead when doing dev work:

   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Set up its `.env`:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` so `DATABASE_URL` / `REDIS_URL` (whichever apply) point at
   infra reachable from your machine — e.g. `localhost` instead of the
   compose service names (`postgres`, `redis`), since you're running
   outside the compose network:

   ```
   DATABASE_URL=postgresql+psycopg2://spacerace:spacerace@localhost:5432/spacerace
   REDIS_URL=redis://localhost:6379/0
   ```

4. **Run it:**

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

   `--reload` is optional but useful for local dev. Pick a free host port
   per service to avoid clashes if running more than one this way (e.g.
   `--port 8001` for auth, `--port 8004` for game-session, matching the
   compose table above).

5. **Run tests**, if the service has a `tests/` folder and
   `requirements-dev.txt` (e.g. `GameSessionService`):

   ```bash
   pytest
   ```

## Notes

- Never commit a populated `.env`; only `.env.example` is checked in
  (see `CONTRIBUTING.md`).
- Don't create a root-level `.env` — each service owns its own.
