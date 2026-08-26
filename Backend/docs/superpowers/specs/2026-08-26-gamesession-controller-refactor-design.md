# GameSessionService: controller refactor & review fixes

Date: 2026-08-26
Status: Approved for implementation

## Context

A code review of `Backend/GameSessionService` surfaced 9 findings. One
(hardcoded physics constants) was already resolved by the prior
`game-settings-migration` work. This spec covers the remaining 8:

1. No routes/controllers/models layering — violates `Backend/CLAUDE.md`.
2. ~~Physics constants hardcoded~~ — already fixed, not in scope.
3. Module-level logger instead of instance-based.
4. Loose dict typing for websocket input/messages.
5. Sessions/game-loop tasks never cleaned up when a room empties.
6. No error handling around the game loop task.
7. Single-ship/`_active_client` model ambiguous under multiple connections.
8. Frontend/backend geometry sync (`BELT_CENTER`, `SPAWN_OFFSET`) enforced
   only by comments.
9. No tests for `main.py` (websocket handler) or `game_loop.py`.

## Decisions

- **Ship ownership (item 7):** a room accepts exactly one connection.
  Multi-ship-per-room is planned future work but explicitly out of scope
  here. A second connection attempt to an already-owned room is accepted
  at the transport level, sent an error message, then closed with code
  `4409`, without being registered on the session. This keeps the future
  multi-ship change localized: that check is later replaced with "add a
  new ship for this connection" instead of "reject."
- **Session/task cleanup (item 5):** immediate teardown, no grace period.
  When a room's connection set becomes empty, its loop task is cancelled
  and both the session and task are dropped. A later reconnect creates a
  fresh session (new asteroid layout) — there is no reconnect-continuity
  requirement today.
- **Game loop error handling (item 6):** log the exception (with
  traceback) and keep looping; do not tear down the room. Tradeoff
  accepted: if the exception leaves physics state corrupted, the same
  error may repeat every tick. Acceptable for now — no retry/backoff
  logic is added.
- **Geometry sync (item 8):** backend-only prep, no Frontend changes in
  this task (repo rule: don't mix Frontend/Backend work in one task).
  `BELT_CENTER`/`SPAWN_OFFSET`/`INNER_FENCE_R`/`OUTER_FENCE_R` move from
  module constants in `session.py` into `GameSettings`, and are included
  in `to_init_message()`. A future Frontend-side task can consume them
  instead of hardcoding; that consumption is explicitly not part of this
  spec.

## Design

### Layout (item 1)

Following the `Backend/CLAUDE.md` routes/controllers/models convention,
adapted for a websocket-first service (one resource: `game_session`):

- `app/routes/game_session.py` — `APIRouter` with `GET /health` and
  `WS /ws/{room_id}` only. The websocket route accepts the connection and
  delegates the entire connection lifecycle to a controller function. No
  business logic here.
- `app/controllers/game_session.py` — a `SessionManager` class replacing
  today's two module-level `sessions`/`loop_tasks` dicts:
  - `get_or_create(room_id) -> GameSession`
  - `remove(room_id) -> None`
  - `handle_connection(websocket, room_id) -> None` — owns accept/register
    flow, the receive loop (parse → validate → `session.set_input`), and
    the reject-second-connection check (item 7).
  This is also where cleanup-on-empty (item 5) is triggered, from the
  `finally` block after a websocket disconnects.
- `app/models/messages.py` — Pydantic models for the websocket wire
  format:
  - `InputMessage` (`type: Literal["input"]`, `thrust: int`, `turn: int`,
    with a validator restricting `thrust`/`turn` to `{-1, 0, 1}`) —
    replaces the manual `VALID_INPUT_VALUES` dict-digging in `main.py`.
  - `InitMessage` / `StateMessage` — typed replacements for the dicts
    currently returned by `GameSession.to_init_message()` /
    `to_broadcast_message()`.
- `app/main.py` shrinks to `app = FastAPI(...)` plus
  `app.include_router(...)`.

### Ship ownership (item 7)

`SessionManager` tracks one owning `WebSocket` per room (on the
`GameSession`, or in the manager — whichever keeps `GameSession` simplest;
implementer's call). On a new connection to a room that already has an
owner: accept the websocket, send a JSON error message
(`{"type": "error", "reason": "room_full"}`), then
`await websocket.close(code=4409)`, and return without calling
`session.register()`.

### Lifecycle cleanup (item 5)

In `SessionManager.handle_connection`'s `finally` block: call
`session.unregister(websocket)`, then if `session.connections` is empty,
call `SessionManager.remove(room_id)`, which cancels the room's loop task
and pops both the session and task from their dicts.

### Game loop error handling (item 6)

In `run_game_loop`, wrap the per-tick body (`session.step` +
`session.broadcast`) in `try/except Exception`, logging with `exc_info`,
and continue the `while True` loop (no teardown, no backoff).

### Logger (item 3)

`GameSession.__init__` and `SessionManager.__init__` accept an optional
`logger: logging.Logger | None = None` param, defaulting to
`logging.getLogger(f"{__name__}.{room_id}")` (per-session) and
`logging.getLogger(__name__)` (manager), stored as an instance attribute
(`self._logger`) rather than read from a shared module global. Tests can
inject a fake/mock logger and assert on calls without monkeypatching.

### Geometry in GameSettings + init message (item 8)

Move `BELT_CENTER`, `SPAWN_OFFSET`, `INNER_FENCE_R`, `OUTER_FENCE_R` from
module constants in `session.py` into `GameSettings` fields (matching
every other physics constant). `to_init_message()` gains the belt
geometry (center x/y, spawn x/y, inner/outer radius) alongside the
existing asteroid layout.

### Typing (item 4)

Covered by the `app/models/messages.py` Pydantic models above. Incoming
raw text is parsed via `InputMessage.model_validate_json(raw)` inside a
try/except `ValidationError` (replacing manual `json.loads` +
`isinstance`/dict-key checks). `latest_input: dict[WebSocket, dict]`
becomes `dict[WebSocket, InputMessage]` (or a lighter dataclass — same
`{thrust, turn}` shape) instead of a bare `dict`.

### Tests (item 9)

New tests:
- `tests/test_controller.py` (or similar) — `SessionManager`:
  create-on-first-connection, reuse-on-second-request-for-same-room,
  reject-second-connection-to-owned-room (assert close code 4409),
  cleanup-on-last-disconnect (session/task removed from manager state).
- `tests/test_game_loop.py` — one bad tick (mock `session.step` to raise)
  is logged and the loop continues to the next tick without raising.

Existing `test_entities.py` and `test_game_settings.py` are unaffected.
`test_session.py` needs updates: `to_init_message()`'s shape changes
(belt geometry fields added), and any direct references to the
module-level `BELT_CENTER`/`SPAWN_OFFSET` constants move to
`game_settings`.

## Out of scope

- Multi-ship-per-room support (future work; this spec keeps the door
  open per the ship-ownership design above).
- Any Frontend changes to consume the new init-message geometry fields.
- Reconnect-with-grace-period session continuity.
- Retry/backoff logic for game-loop errors.
