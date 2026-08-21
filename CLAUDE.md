# CLAUDE.md

Repo-wide instructions for how Claude should operate in SpaceRace (Asteroid
Belt Battleground). See `asteroid-belt-game-plan.md` for the product/architecture
overview. Backend and frontend each get their own `CLAUDE.md` with
folder-specific rules once those are defined — this file only covers what
applies across the whole repo.

## Repo layout

- `Frontend/` — Phaser.js game client
- `Backend/AuthService/`, `Backend/PlayerService/`, ... — one folder per
  microservice, Python/FastAPI
- `docker-compose.yml` — root-level orchestration for local dev
- `scripts/` — task runner scripts (no Makefile; Windows-friendly)
- `asteroid-belt-game-plan.md` — product & architecture reference, not a task list

## Git workflow

- Trunk-based development off `main`. Never push directly to `main` — always
  branch and open a PR, even for solo/small changes.
- Commit messages follow Conventional Commits: `feat:`, `fix:`, `chore:`,
  `docs:`, `refactor:`, `test:`. Scope is optional, free text.
- Full detail in `CONTRIBUTING.md`.

## Work isolation

- Do not work on `Frontend/` and `Backend/` in the same task/session. Pick
  one side and finish or pause it before switching.
- Within `Backend/`, working across multiple services (e.g. `AuthService`
  and `PlayerService`) in the same task is fine.

## Git worktrees

- Never use git worktrees for any purpose (feature isolation, parallel
  agent workspaces, etc.) — not even via a worktree-based skill or an
  agent tool's worktree isolation option. Work directly on branches
  instead.

## Repo structure changes

- Never create a new top-level directory (a sibling of `Frontend/`,
  `Backend/`, `scripts/`, etc.) without asking the user first.

## Documentation

- Docs live in a `docs/` folder unless a location is explicitly specified
  otherwise. Both `Frontend/` and `Backend/` have their own `docs/` folder
  (`Frontend/docs/`, `Backend/docs/`).
- Frontend and backend ADRs (Architecture Decision Records) are maintained
  separately: `Frontend/docs/adr/` and `Backend/docs/adr/`.
- Per-service backend ADRs (e.g. for `AuthService`, `PlayerService`) also go
  in `Backend/docs/adr/`, not inside the individual service folder — keep
  all backend ADRs together in one place.

## Secrets & environment

- Never create or commit a root-level `.env`. Each service owns its own
  `.env` (gitignored) and `.env.example` (committed).
- If asked to add a new config value, add it to the relevant service's
  `.env.example` with a placeholder, not the root.

## Scope discipline

- Backend and frontend conventions (code style, testing, framework-specific
  rules) live in their own folders and are not yet defined — don't invent
  them here. When working inside `Backend/<Service>/` or `Frontend/`, check
  for a local `CLAUDE.md`/`CONTRIBUTING.md` first.
- This is an early-stage repo (no commits yet as of setup). Prefer small,
  reviewable PRs over large speculative scaffolding.
