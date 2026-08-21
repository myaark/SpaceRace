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
