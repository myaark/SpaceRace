# Frontend Setup Guide

How to get the Phaser.js game client running locally.

Stack: Vite + Phaser, package-managed with `pnpm` (see `pnpm-lock.yaml`).

## Prerequisites

- Node.js (recent LTS)
- `pnpm` (`npm install -g pnpm` if you don't have it)
- Backend services running if you need the client to talk to them — see
  `Backend/docs/SETUP.md`

## Setup

1. Install dependencies, from the `Frontend/` folder:

   ```bash
   cd Frontend
   pnpm install
   ```

2. Set up environment config, if `.env.example` exists:

   ```bash
   cp .env.example .env
   ```

   (No `Frontend/.env.example` exists yet as of this writing — add one if
   the client needs config such as backend API URLs, per `CONTRIBUTING.md`.)

3. Run the dev server:

   ```bash
   pnpm dev
   ```

   Vite serves the client with hot reload (default `http://localhost:5173`).

## Other commands

```bash
pnpm build      # production build
pnpm preview    # preview the production build locally
```

## Notes

- Never commit a populated `.env`; only `.env.example` is checked in.
- The frontend service is commented out in the root `docker-compose.yml`
  (dev is expected to run outside Docker via `pnpm dev`) — use the steps
  above rather than compose.
