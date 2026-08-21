# Contributing

Repo-wide rules. Backend and frontend each have their own conventions in
`Backend/*/CONTRIBUTING.md` and `Frontend/CONTRIBUTING.md` (added separately) —
those take precedence within their folder for anything not covered here.

## Branching & merging

- Trunk-based: `main` is always deployable. No `develop` branch.
- Work on short-lived feature branches, e.g. `matchmaking-queue`, `fix-respawn-timer`.
- All changes land via pull request — no direct pushes to `main`, even solo.
  Self-review and merge your own PRs; the point is a reviewable diff and a
  clean history, not gatekeeping.

## Commit messages — Conventional Commits

Format: `<type>: <short summary>`

Types:
- `feat` — new feature
- `fix` — bug fix
- `chore` — tooling, deps, config, non-code changes
- `docs` — documentation only
- `refactor` — code change that neither fixes a bug nor adds a feature
- `test` — adding or correcting tests

Scope is optional free text in parentheses when it helps, e.g. `fix(auth): handle expired token refresh`.
No enforced scope list — use whatever's clearest for the change.

## Environment & secrets

- Each service (`Frontend/`, `Backend/AuthService/`, `Backend/PlayerService/`, ...)
  owns its own `.env`, which is gitignored.
- Each service commits a `.env.example` listing the variables it needs, with
  placeholder/dummy values.
- Never commit a populated `.env`. If one is committed by accident, rotate the
  secrets — don't just delete the file.
- `docker-compose.yml` at the repo root references each service's `.env` via
  `env_file`; it does not define a shared/global env file.

## Local development

Common tasks are plain scripts in `scripts/`, not a Makefile (no `make`
dependency assumed on Windows). See `scripts/README.md`.

## Adding a new service

1. Create `Backend/<ServiceName>/` (or under `Frontend/` if it's a frontend concern).
2. Add its own `.env.example`, `.gitignore` (if it needs entries beyond the root one), and `CONTRIBUTING.md` once conventions for that layer are defined.
3. Wire it into root `docker-compose.yml`.
4. Add a corresponding `scripts/` entry if it needs its own dev/test command.
