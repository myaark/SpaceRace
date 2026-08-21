# CLAUDE.md (Backend)

Folder-specific instructions for working in `Backend/`. See the root
`CLAUDE.md` for repo-wide conventions (git workflow, work isolation,
secrets, docs layout).

## Tooling

- Each service (`AuthService/`, `PlayerService/`, `MatchmakingService/`,
  `GameSessionService/`, `LeaderboardService/`) is a Python/FastAPI app.
- Use the `fastapi` skill when necessary for FastAPI-specific work in any
  of these services (path operations, dependencies, Pydantic models,
  responses, streaming, etc.) — don't reinvent guidance the skill already
  covers.
- Lint/format: `ruff` (lint + format, replaces flake8/isort/black) in every
  service. Prefer per-file ignores in `pyproject.toml`/`ruff.toml` over
  scattered `# noqa` comments — a mismatched local vs. pinned ruff version
  can silently drop per-line directives.
- Tests: `pytest` in every service. Add a test per implementation step in a
  multi-step feature (validation → persistence → response), not only a
  final end-to-end test. No CI workflow runs these yet (deferred as of
  2026-08-21) — until one exists, `ruff check`/`ruff format --check` and
  `pytest` must be run manually before opening a PR.
- DB migrations: no migration tool (e.g. Alembic) yet for the
  Postgres-backed services (`AuthService`, `PlayerService`,
  `LeaderboardService`) — deliberately deferred until their schemas
  stabilize (decided 2026-08-21). Once a service's schema is no longer
  actively changing shape, add Alembic to that service before its next
  schema change, rather than continuing with ad hoc DDL.

## Auth verification across services

JWTs are stateless and signed with a shared secret — a service that needs
to check a caller's token verifies the signature **locally**, without
calling `AuthService` at request time. `AuthService` is the sole *issuer*;
it is never a runtime dependency for other services' request handling
(that would make it a synchronous single point of failure for every
request in every service). See `Backend/docs/adr/0001-jwt-verification.md`
for the full rationale.

The verification dependency (decode + validate the JWT, raise 401 on
failure) lives in one shared internal package, not copy-pasted per
service. Any service that needs to authenticate a caller depends on that
package rather than reimplementing `python-jose` decoding itself.
