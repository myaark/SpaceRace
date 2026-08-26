# GameSessionService Controller Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `Backend/GameSessionService` into the routes/controllers/models
layout required by `Backend/CLAUDE.md`, and fix the remaining review findings:
instance-based logging, typed websocket messages, session/task cleanup on empty
rooms, game-loop error resilience, single-connection-per-room ownership, and
belt geometry exposed via `GameSettings` + the init message.

**Architecture:** `app/main.py` shrinks to app creation + router inclusion.
`app/routes/game_session.py` wires HTTP/WS to a `SessionManager` in
`app/controllers/game_session.py`, which owns session/task lifecycle and the
per-connection receive loop. `app/models/messages.py` holds Pydantic models
for the websocket wire format. `app/session.py` and `app/game_loop.py` get
targeted fixes (geometry, logger, error handling) without changing their
core physics logic.

**Tech Stack:** Python, FastAPI, Pydantic v2, pymunk, pytest + pytest-asyncio.

**Spec:** `Backend/docs/superpowers/specs/2026-08-26-gamesession-controller-refactor-design.md`

## Global Constraints

- Follow `Backend/CLAUDE.md`'s routes/controllers/models layering.
- Lint/format with `ruff` (lint + `ruff format --check`); run before every commit.
- Run `pytest` from `Backend/GameSessionService/` before every commit; all
  tests must pass.
- No CI runs these yet — manual verification is required for every task.
- Multi-ship-per-room, Frontend changes, reconnect-with-grace-period, and
  game-loop retry/backoff are explicitly out of scope (see spec's "Out of
  scope" section).
- Work stays inside `Backend/GameSessionService/` only (repo rule: don't mix
  Frontend/Backend work in one task).

---

### Task 1: Belt geometry moves into `GameSettings`

**Files:**
- Modify: `Backend/GameSessionService/app/game_settings.py`
- Modify: `Backend/GameSessionService/app/session.py`
- Modify: `Backend/GameSessionService/tests/test_session.py`
- Test: `Backend/GameSessionService/tests/test_game_settings.py`

**Interfaces:**
- Produces: `GameSettings.belt_center: tuple[float, float]`,
  `GameSettings.spawn_offset: tuple[float, float]`,
  `GameSettings.inner_fence_r: float`, `GameSettings.outer_fence_r: float`.
  `GameSession` gains instance attributes `self._belt_center: pymunk.Vec2d`,
  `self._spawn: pymunk.Vec2d`, `self._inner_fence_r: float`,
  `self._outer_fence_r: float`, all set in `__init__` from `game_settings`.

- [ ] **Step 1: Write the failing test for the new `GameSettings` fields**

Add to `Backend/GameSessionService/tests/test_game_settings.py`:

```python
def test_defaults_include_belt_geometry() -> None:
    defaults = GameSettings()

    assert defaults.belt_center == (-200.0, 1500.0)
    assert defaults.spawn_offset == (924.0, -1182.0)
    assert defaults.inner_fence_r == 1420.0
    assert defaults.outer_fence_r == 1760.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Backend/GameSessionService && pytest tests/test_game_settings.py::test_defaults_include_belt_geometry -v`
Expected: FAIL with `AttributeError: 'GameSettings' object has no attribute 'belt_center'`

- [ ] **Step 3: Add the fields to `GameSettings`**

In `Backend/GameSessionService/app/game_settings.py`, add (after the
`asteroid_placement_attempts` field, before the `game_settings = GameSettings()`
line):

```python
    # Belt boundary geometry. Must match Frontend/src/scenes/BeltScene.js's
    # BELT_CENTER / OUTER_FENCE_R / INNER_FENCE_R — there is no shared-schema
    # mechanism enforcing this, so keep the two in sync by hand.
    belt_center: tuple[float, float] = (-200.0, 1500.0)

    # Offset from belt_center to Frontend/src/scenes/BeltScene.js's SHIP
    # constant (724, 318). The ship must spawn exactly here — it's the only
    # point the frontend draws before the first server state arrives, so any
    # mismatch makes the ship appear to teleport/disappear on the first
    # broadcast.
    spawn_offset: tuple[float, float] = (924.0, -1182.0)
    inner_fence_r: float = 1420.0
    outer_fence_r: float = 1760.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Backend/GameSessionService && pytest tests/test_game_settings.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Update `GameSession` to read geometry from `game_settings`**

In `Backend/GameSessionService/app/session.py`, remove the module-level
`BELT_CENTER`, `OUTER_FENCE_R`, `INNER_FENCE_R`, `SPAWN_OFFSET` constants
(lines 13-24), and change `GameSession.__init__` (currently lines 30-56) to:

```python
    def __init__(self, room_id: str) -> None:
        self.room_id = room_id
        self.space = pymunk.Space()
        self.space.gravity = (0, 0)
        self.space.damping = game_settings.space_damping

        self._belt_center = pymunk.Vec2d(*game_settings.belt_center)
        self._inner_fence_r = game_settings.inner_fence_r
        self._outer_fence_r = game_settings.outer_fence_r
        self._spawn = self._belt_center + pymunk.Vec2d(*game_settings.spawn_offset)

        self.ship = Ship("ship-1", (self._spawn.x, self._spawn.y))
        self.space.add(self.ship.body, self.ship.shape)

        layout = generate_asteroid_layout(
            (self._belt_center.x, self._belt_center.y),
            self._inner_fence_r,
            self._outer_fence_r,
            (self._spawn.x, self._spawn.y),
        )
        self.asteroids: dict[str, Asteroid] = {}
        for asteroid_id, x, y, r, drift, period in layout:
            asteroid = Asteroid(asteroid_id, (x, y), r, drift, period)
            self.space.add(asteroid.body, asteroid.shape)
            self.asteroids[asteroid_id] = asteroid

        self.connections: set[WebSocket] = set()
        self.latest_input: dict[WebSocket, dict] = {}
        self._active_client: WebSocket | None = None
        self.tick_count = 0
        self._elapsed_ms = 0.0
```

Then update `_clamp_to_belt` (currently lines 89-106) to use the instance
attributes instead of the removed module constants:

```python
    def _clamp_to_belt(self, body: pymunk.Body) -> None:
        offset = body.position - self._belt_center
        distance = offset.length

        if self._inner_fence_r <= distance <= self._outer_fence_r:
            return

        past_outer = distance > self._outer_fence_r
        clamped_distance = self._outer_fence_r if past_outer else self._inner_fence_r
        radial_dir = offset.normalized() if distance > 1e-6 else pymunk.Vec2d(1, 0)

        body.position = self._belt_center + radial_dir * clamped_distance
        radial_velocity = body.velocity.dot(radial_dir)
        # Only kill the component still pushing past this fence, so a body
        # that has reversed course back toward the belt isn't stuck there.
        still_escaping = radial_velocity > 0 if past_outer else radial_velocity < 0
        if still_escaping:
            body.velocity = body.velocity - radial_dir * radial_velocity
```

- [ ] **Step 6: Update `tests/test_session.py` to source geometry from `game_settings`**

Replace the import block (currently lines 1-11):

```python
import pymunk
import pytest

from app.game_settings import game_settings
from app.session import GameSession

BELT_CENTER = pymunk.Vec2d(*game_settings.belt_center)
INNER_FENCE_R = game_settings.inner_fence_r
OUTER_FENCE_R = game_settings.outer_fence_r
SPAWN_OFFSET = pymunk.Vec2d(*game_settings.spawn_offset)
```

No other lines in the file change — every test already references
`BELT_CENTER`/`INNER_FENCE_R`/`OUTER_FENCE_R`/`SPAWN_OFFSET` by name only.

- [ ] **Step 7: Run the full test suite to verify it passes**

Run: `cd Backend/GameSessionService && pytest -v`
Expected: PASS (all tests, including `test_session.py` and `test_game_settings.py`)

- [ ] **Step 8: Lint and format**

Run: `cd Backend/GameSessionService && ruff check . && ruff format --check .`
Expected: no errors (run `ruff format .` to fix formatting if the check fails,
then re-run both commands)

- [ ] **Step 9: Commit**

```bash
git add Backend/GameSessionService/app/game_settings.py Backend/GameSessionService/app/session.py Backend/GameSessionService/tests/test_game_settings.py Backend/GameSessionService/tests/test_session.py
git commit -m "refactor: move belt geometry constants into GameSettings"
```

---

### Task 2: Instance-based logger on `GameSession`

**Files:**
- Modify: `Backend/GameSessionService/app/session.py`
- Test: `Backend/GameSessionService/tests/test_session.py`

**Interfaces:**
- Consumes: nothing new from Task 1.
- Produces: `GameSession.__init__(self, room_id: str, logger: logging.Logger | None = None)`.
  `self._logger` used internally by `broadcast()`.

- [ ] **Step 1: Write the failing test**

Add to `Backend/GameSessionService/tests/test_session.py`:

```python
import asyncio
import logging


def test_broadcast_uses_injected_logger_on_dropped_client(caplog) -> None:
    class _FailingWebSocket:
        async def send_json(self, data: dict) -> None:
            raise RuntimeError("send failed")

    custom_logger = logging.getLogger("test-custom-logger")
    session = GameSession("test-room", logger=custom_logger)
    session.connections.add(_FailingWebSocket())

    with caplog.at_level(logging.INFO, logger="test-custom-logger"):
        asyncio.run(session.broadcast())

    assert len(caplog.records) == 1
    assert caplog.records[0].name == "test-custom-logger"
    assert "test-room" in caplog.records[0].getMessage()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Backend/GameSessionService && pytest tests/test_session.py::test_broadcast_uses_injected_logger_on_dropped_client -v`
Expected: FAIL with `TypeError: GameSession() got an unexpected keyword argument 'logger'`

- [ ] **Step 3: Implement the instance logger**

In `Backend/GameSessionService/app/session.py`, remove the module-level
`logger = logging.getLogger(__name__)` line (currently line 11). Change the
`__init__` signature (from Task 1's version) to:

```python
    def __init__(self, room_id: str, logger: logging.Logger | None = None) -> None:
        self.room_id = room_id
        self._logger = logger or logging.getLogger(f"{__name__}.{room_id}")
        self.space = pymunk.Space()
        ...
```

(keep the rest of `__init__` body from Task 1 unchanged, this only adds the
`logger` param and `self._logger` line before `self.space = pymunk.Space()`)

Then update `broadcast()` (currently lines 162-174) to use `self._logger`
instead of the removed module `logger`:

```python
    async def broadcast(self) -> None:
        if not self.connections:
            return
        message = self.to_broadcast_message()
        dead: list[WebSocket] = []
        for websocket in self.connections:
            try:
                await websocket.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                self._logger.info("Dropping disconnected client from room %s", self.room_id)
                dead.append(websocket)
        for websocket in dead:
            self.unregister(websocket)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Backend/GameSessionService && pytest tests/test_session.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Lint and format**

Run: `cd Backend/GameSessionService && ruff check . && ruff format --check .`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add Backend/GameSessionService/app/session.py Backend/GameSessionService/tests/test_session.py
git commit -m "refactor: make GameSession logger instance-based, not module-global"
```

---

### Task 3: Typed websocket messages (`app/models/messages.py`)

**Files:**
- Create: `Backend/GameSessionService/app/models/__init__.py`
- Create: `Backend/GameSessionService/app/models/messages.py`
- Test: `Backend/GameSessionService/tests/test_messages.py`

**Interfaces:**
- Produces:
  - `InputMessage(BaseModel)` — fields `type: Literal["input"]`, `thrust: int`, `turn: int`;
    `thrust`/`turn` validated to be one of `{-1, 0, 1}`.
  - `ShipState(BaseModel)` — fields `id: str`, `x: float`, `y: float`, `rotation: float`, `vx: float`, `vy: float`.
  - `AsteroidInit(BaseModel)` — fields `id: str`, `x: float`, `y: float`, `r: float`.
  - `InitMessage(BaseModel)` — fields `type: Literal["init"] = "init"`, `belt_center_x: float`,
    `belt_center_y: float`, `spawn_x: float`, `spawn_y: float`, `inner_r: float`, `outer_r: float`,
    `asteroids: list[AsteroidInit]`.
  - `StateMessage(BaseModel)` — fields `type: Literal["state"] = "state"`, `tick: int`,
    `ship: ShipState`, `asteroids: list[ShipState]`.

- [ ] **Step 1: Write the failing tests**

Create `Backend/GameSessionService/app/models/__init__.py` (empty file).

Create `Backend/GameSessionService/tests/test_messages.py`:

```python
import pytest
from pydantic import ValidationError

from app.models.messages import InputMessage


def test_valid_input_message_parses() -> None:
    msg = InputMessage.model_validate_json('{"type": "input", "thrust": 1, "turn": -1}')
    assert msg.thrust == 1
    assert msg.turn == -1


@pytest.mark.parametrize("thrust", [2, -2, 99])
def test_out_of_range_thrust_is_rejected(thrust: int) -> None:
    with pytest.raises(ValidationError):
        InputMessage.model_validate_json(f'{{"type": "input", "thrust": {thrust}, "turn": 0}}')


def test_wrong_type_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        InputMessage.model_validate_json('{"type": "ping", "thrust": 0, "turn": 0}')


def test_malformed_json_is_rejected() -> None:
    with pytest.raises(ValidationError):
        InputMessage.model_validate_json("not json")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd Backend/GameSessionService && pytest tests/test_messages.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 3: Implement the models**

Create `Backend/GameSessionService/app/models/messages.py`:

```python
from typing import Literal

from pydantic import BaseModel, field_validator

VALID_INPUT_VALUES = (-1, 0, 1)


class InputMessage(BaseModel):
    """Incoming websocket message: a player's current thrust/turn input."""

    type: Literal["input"]
    thrust: int
    turn: int

    @field_validator("thrust", "turn")
    @classmethod
    def _validate_range(cls, value: int) -> int:
        if value not in VALID_INPUT_VALUES:
            raise ValueError(f"must be one of {VALID_INPUT_VALUES}")
        return value


class ShipState(BaseModel):
    id: str
    x: float
    y: float
    rotation: float
    vx: float
    vy: float


class AsteroidInit(BaseModel):
    id: str
    x: float
    y: float
    r: float


class InitMessage(BaseModel):
    """One-time layout message sent right after a client connects."""

    type: Literal["init"] = "init"
    belt_center_x: float
    belt_center_y: float
    spawn_x: float
    spawn_y: float
    inner_r: float
    outer_r: float
    asteroids: list[AsteroidInit]


class StateMessage(BaseModel):
    """Per-tick broadcast of authoritative physics state."""

    type: Literal["state"] = "state"
    tick: int
    ship: ShipState
    asteroids: list[ShipState]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd Backend/GameSessionService && pytest tests/test_messages.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Lint and format**

Run: `cd Backend/GameSessionService && ruff check . && ruff format --check .`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add Backend/GameSessionService/app/models/ Backend/GameSessionService/tests/test_messages.py
git commit -m "feat: add typed Pydantic models for websocket messages"
```

---

### Task 4: `GameSession` emits typed init/state messages

**Files:**
- Modify: `Backend/GameSessionService/app/session.py`
- Modify: `Backend/GameSessionService/tests/test_session.py`

**Interfaces:**
- Consumes: `InitMessage`, `AsteroidInit`, `StateMessage`, `ShipState` from
  `app.models.messages` (Task 3).
- Produces: `GameSession.to_init_message() -> InitMessage`,
  `GameSession.to_broadcast_message() -> StateMessage`. `broadcast()` now
  calls `.model_dump()` before `send_json`.

- [ ] **Step 1: Write the failing tests**

Add to `Backend/GameSessionService/tests/test_session.py`:

```python
from app.models.messages import InitMessage, StateMessage


def test_to_init_message_includes_belt_geometry_and_asteroids(
    session: GameSession,
) -> None:
    init = session.to_init_message()

    assert isinstance(init, InitMessage)
    assert init.belt_center_x == pytest.approx(BELT_CENTER.x)
    assert init.belt_center_y == pytest.approx(BELT_CENTER.y)
    assert init.spawn_x == pytest.approx((BELT_CENTER + SPAWN_OFFSET).x)
    assert init.spawn_y == pytest.approx((BELT_CENTER + SPAWN_OFFSET).y)
    assert init.inner_r == INNER_FENCE_R
    assert init.outer_r == OUTER_FENCE_R
    assert len(init.asteroids) == len(session.asteroids)


def test_to_broadcast_message_returns_typed_state(session: GameSession) -> None:
    state = session.to_broadcast_message()

    assert isinstance(state, StateMessage)
    assert state.tick == session.tick_count
    assert state.ship.id == session.ship.id
    assert len(state.asteroids) == len(session.asteroids)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd Backend/GameSessionService && pytest tests/test_session.py::test_to_init_message_includes_belt_geometry_and_asteroids tests/test_session.py::test_to_broadcast_message_returns_typed_state -v`
Expected: FAIL — `init.belt_center_x` etc. don't exist because `to_init_message()` still returns a plain dict

- [ ] **Step 3: Implement the typed messages**

In `Backend/GameSessionService/app/session.py`, add the import:

```python
from app.models.messages import AsteroidInit, InitMessage, ShipState, StateMessage
```

Replace `to_init_message` (currently lines 137-152):

```python
    def to_init_message(self) -> InitMessage:
        """One-time layout message: asteroid radius never changes, but since
        the layout is now server-generated (not a hand-copied frontend
        constant), the client needs it sent explicitly on connect."""
        return InitMessage(
            belt_center_x=self._belt_center.x,
            belt_center_y=self._belt_center.y,
            spawn_x=self._spawn.x,
            spawn_y=self._spawn.y,
            inner_r=self._inner_fence_r,
            outer_r=self._outer_fence_r,
            asteroids=[
                AsteroidInit(
                    id=a.id, x=a.body.position.x, y=a.body.position.y, r=a.radius
                )
                for a in self.asteroids.values()
            ],
        )
```

Replace `to_broadcast_message` (currently lines 154-160):

```python
    def to_broadcast_message(self) -> StateMessage:
        return StateMessage(
            tick=self.tick_count,
            ship=ShipState(**self.ship.to_state()),
            asteroids=[ShipState(**a.to_state()) for a in self.asteroids.values()],
        )
```

Update `broadcast()` to serialize the model before sending:

```python
    async def broadcast(self) -> None:
        if not self.connections:
            return
        message = self.to_broadcast_message().model_dump()
        dead: list[WebSocket] = []
        for websocket in self.connections:
            try:
                await websocket.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                self._logger.info("Dropping disconnected client from room %s", self.room_id)
                dead.append(websocket)
        for websocket in dead:
            self.unregister(websocket)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd Backend/GameSessionService && pytest tests/test_session.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Lint and format**

Run: `cd Backend/GameSessionService && ruff check . && ruff format --check .`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add Backend/GameSessionService/app/session.py Backend/GameSessionService/tests/test_session.py
git commit -m "feat: GameSession emits typed InitMessage/StateMessage"
```

---

### Task 5: Game-loop error resilience

**Files:**
- Modify: `Backend/GameSessionService/app/game_loop.py`
- Test: `Backend/GameSessionService/tests/test_game_loop.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `run_game_loop(session)` no longer raises on a per-tick exception;
  it logs (with traceback) and continues.

- [ ] **Step 1: Write the failing test**

Create `Backend/GameSessionService/tests/test_game_loop.py`:

```python
import asyncio
import logging

import pytest

from app.config import settings
from app.game_loop import run_game_loop


class _ExplodingOnceSession:
    def __init__(self) -> None:
        self.room_id = "test-room"
        self.step_calls = 0
        self.broadcast_calls = 0

    def step(self, dt: float) -> None:
        self.step_calls += 1
        if self.step_calls == 1:
            raise RuntimeError("boom")

    async def broadcast(self) -> None:
        self.broadcast_calls += 1


@pytest.mark.asyncio
async def test_loop_survives_one_bad_tick_and_logs_it(monkeypatch, caplog) -> None:
    monkeypatch.setattr(settings, "tick_rate_hz", 1000)
    session = _ExplodingOnceSession()
    task = asyncio.create_task(run_game_loop(session))

    with caplog.at_level(logging.ERROR):
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert session.step_calls >= 2
    assert session.broadcast_calls >= 1
    assert "Unhandled error in game loop" in caplog.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Backend/GameSessionService && pytest tests/test_game_loop.py -v`
Expected: FAIL — the unhandled `RuntimeError` propagates out of the task,
so `session.step_calls` never reaches 2 (the loop dies on the first tick)

- [ ] **Step 3: Implement error handling**

Replace `Backend/GameSessionService/app/game_loop.py` in full:

```python
import asyncio
import logging

from app.config import settings
from app.session import GameSession

logger = logging.getLogger(__name__)


async def run_game_loop(session: GameSession) -> None:
    """Fixed-tick server-authoritative loop for a single game session.

    Each tick: apply the latest buffered input, step physics, enforce the
    belt boundary, then broadcast the resulting state to connected clients.
    An exception during a single tick is logged and does not stop the loop —
    other rooms have their own independent task and are unaffected either way.
    """
    tick_interval = 1 / settings.tick_rate_hz
    while True:
        await asyncio.sleep(tick_interval)
        try:
            session.step(tick_interval)
            await session.broadcast()
        except Exception:
            logger.exception(
                "Unhandled error in game loop for room %s", session.room_id
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Backend/GameSessionService && pytest tests/test_game_loop.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `cd Backend/GameSessionService && pytest -v`
Expected: PASS (all tests)

- [ ] **Step 6: Lint and format**

Run: `cd Backend/GameSessionService && ruff check . && ruff format --check .`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add Backend/GameSessionService/app/game_loop.py Backend/GameSessionService/tests/test_game_loop.py
git commit -m "fix: game loop logs and survives per-tick exceptions instead of dying"
```

---

### Task 6: `SessionManager` controller (lifecycle, ownership, cleanup)

**Files:**
- Create: `Backend/GameSessionService/app/controllers/__init__.py`
- Create: `Backend/GameSessionService/app/controllers/game_session.py`
- Test: `Backend/GameSessionService/tests/test_controller.py`

**Interfaces:**
- Consumes: `GameSession` (`app.session`), `run_game_loop` (`app.game_loop`),
  `InputMessage` (`app.models.messages`, Task 3).
- Produces: `SessionManager` with `get_or_create(room_id: str) -> GameSession`,
  `remove(room_id: str) -> None`,
  `async handle_connection(websocket: WebSocket, room_id: str) -> None`.
  `ROOM_FULL_CLOSE_CODE = 4409`.

- [ ] **Step 1: Write the failing tests**

Create `Backend/GameSessionService/app/controllers/__init__.py` (empty file).

Create `Backend/GameSessionService/tests/test_controller.py`:

```python
import asyncio
import json

import pytest
from starlette.websockets import WebSocketDisconnect

from app.controllers.game_session import ROOM_FULL_CLOSE_CODE, SessionManager


class FakeWebSocket:
    """Minimal async double for fastapi.WebSocket, driven by tests."""

    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self.closed_code: int | None = None
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._disconnect = asyncio.Event()

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    async def receive_text(self) -> str:
        queue_get = asyncio.ensure_future(self._queue.get())
        disconnect_wait = asyncio.ensure_future(self._disconnect.wait())
        done, pending = await asyncio.wait(
            {queue_get, disconnect_wait}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        if disconnect_wait in done:
            raise WebSocketDisconnect()
        return queue_get.result()

    async def close(self, code: int = 1000) -> None:
        self.closed_code = code

    def send_input(self, raw: str) -> None:
        self._queue.put_nowait(raw)

    def disconnect(self) -> None:
        self._disconnect.set()


@pytest.mark.asyncio
async def test_get_or_create_reuses_existing_session() -> None:
    manager = SessionManager()
    s1 = manager.get_or_create("room-1")
    s2 = manager.get_or_create("room-1")

    assert s1 is s2
    manager.remove("room-1")


@pytest.mark.asyncio
async def test_second_connection_to_owned_room_is_rejected() -> None:
    manager = SessionManager()
    ws1 = FakeWebSocket()
    task1 = asyncio.create_task(manager.handle_connection(ws1, "room-1"))
    await asyncio.sleep(0.02)

    ws2 = FakeWebSocket()
    await manager.handle_connection(ws2, "room-1")

    assert ws2.closed_code == ROOM_FULL_CLOSE_CODE
    assert ws2.sent[-1]["reason"] == "room_full"

    ws1.disconnect()
    await task1


@pytest.mark.asyncio
async def test_session_and_task_removed_when_room_becomes_empty() -> None:
    manager = SessionManager()
    ws = FakeWebSocket()
    task = asyncio.create_task(manager.handle_connection(ws, "room-1"))
    await asyncio.sleep(0.02)

    ws.disconnect()
    await task

    assert manager.get_or_create("room-1") is not None  # creates a fresh one
    manager.remove("room-1")


@pytest.mark.asyncio
async def test_malformed_input_is_ignored_connection_stays_open() -> None:
    manager = SessionManager()
    ws = FakeWebSocket()
    task = asyncio.create_task(manager.handle_connection(ws, "room-1"))
    await asyncio.sleep(0.02)

    ws.send_input("not json")
    await asyncio.sleep(0.02)
    ws.send_input(json.dumps({"type": "input", "thrust": 99, "turn": 0}))
    await asyncio.sleep(0.02)
    ws.send_input(json.dumps({"type": "input", "thrust": 1, "turn": 0}))
    await asyncio.sleep(0.02)

    ws.disconnect()
    await task  # must complete cleanly, not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd Backend/GameSessionService && pytest tests/test_controller.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.controllers'`

- [ ] **Step 3: Implement `SessionManager`**

Create `Backend/GameSessionService/app/controllers/game_session.py`:

```python
import asyncio
import logging

from fastapi import WebSocket
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.game_loop import run_game_loop
from app.models.messages import InputMessage
from app.session import GameSession

ROOM_FULL_CLOSE_CODE = 4409


class SessionManager:
    """Owns GameSession + game-loop-task lifecycle for every room."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._loop_tasks: dict[str, asyncio.Task] = {}
        self._logger = logger or logging.getLogger(__name__)

    def get_or_create(self, room_id: str) -> GameSession:
        session = self._sessions.get(room_id)
        if session is None:
            session = GameSession(room_id)
            self._sessions[room_id] = session
            self._loop_tasks[room_id] = asyncio.create_task(run_game_loop(session))
        return session

    def remove(self, room_id: str) -> None:
        task = self._loop_tasks.pop(room_id, None)
        if task is not None:
            task.cancel()
        self._sessions.pop(room_id, None)

    async def handle_connection(self, websocket: WebSocket, room_id: str) -> None:
        await websocket.accept()
        session = self.get_or_create(room_id)

        if session.connections:
            await websocket.send_json({"type": "error", "reason": "room_full"})
            await websocket.close(code=ROOM_FULL_CLOSE_CODE)
            return

        session.register(websocket)
        await websocket.send_json(session.to_init_message().model_dump())
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = InputMessage.model_validate_json(raw)
                except ValidationError:
                    self._logger.warning(
                        "Malformed input message on room %s: %r", room_id, raw
                    )
                    continue
                session.set_input(websocket, message.thrust, message.turn)
        except WebSocketDisconnect:
            pass
        finally:
            session.unregister(websocket)
            if not session.connections:
                self.remove(room_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd Backend/GameSessionService && pytest tests/test_controller.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Run the full test suite**

Run: `cd Backend/GameSessionService && pytest -v`
Expected: PASS (all tests)

- [ ] **Step 6: Lint and format**

Run: `cd Backend/GameSessionService && ruff check . && ruff format --check .`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add Backend/GameSessionService/app/controllers/ Backend/GameSessionService/tests/test_controller.py
git commit -m "feat: add SessionManager controller (ownership + lifecycle cleanup)"
```

---

### Task 7: Routes layer + slim `main.py`

**Files:**
- Create: `Backend/GameSessionService/app/routes/__init__.py`
- Create: `Backend/GameSessionService/app/routes/game_session.py`
- Modify: `Backend/GameSessionService/app/main.py`
- Test: `Backend/GameSessionService/tests/test_routes.py`

**Interfaces:**
- Consumes: `SessionManager` (`app.controllers.game_session`, Task 6).
- Produces: `app.routes.game_session.router: APIRouter`,
  `app.routes.game_session.session_manager: SessionManager` (module-level
  singleton the websocket route delegates to).

- [ ] **Step 1: Write the failing test**

Create `Backend/GameSessionService/tests/test_routes.py`:

```python
from app.routes.game_session import router, session_manager


def test_router_registers_health_and_websocket_routes() -> None:
    paths = {route.path for route in router.routes}
    assert "/health" in paths
    assert "/ws/{room_id}" in paths


def test_session_manager_is_a_shared_singleton() -> None:
    from app.controllers.game_session import SessionManager

    assert isinstance(session_manager, SessionManager)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Backend/GameSessionService && pytest tests/test_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.routes'`

- [ ] **Step 3: Implement the routes module**

Create `Backend/GameSessionService/app/routes/__init__.py` (empty file).

Create `Backend/GameSessionService/app/routes/game_session.py`:

```python
from fastapi import APIRouter, WebSocket

from app.config import settings
from app.controllers.game_session import SessionManager

router = APIRouter()
session_manager = SessionManager()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "room_id": settings.room_id,
    }


@router.websocket("/ws/{room_id}")
async def match_socket(websocket: WebSocket, room_id: str):
    await session_manager.handle_connection(websocket, room_id)
```

Replace `Backend/GameSessionService/app/main.py` in full:

```python
from fastapi import FastAPI

from app.routes.game_session import router

app = FastAPI(title="Game Session Service")
app.include_router(router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Backend/GameSessionService && pytest tests/test_routes.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Run the full test suite**

Run: `cd Backend/GameSessionService && pytest -v`
Expected: PASS (all tests across every test file)

- [ ] **Step 6: Lint and format**

Run: `cd Backend/GameSessionService && ruff check . && ruff format --check .`
Expected: no errors

- [ ] **Step 7: Manual smoke check**

Run: `cd Backend/GameSessionService && python -m uvicorn app.main:app --port 8000`
then in another terminal: `curl http://localhost:8000/health`
Expected: `{"status":"ok","service":"game-session-service","room_id":"unassigned"}`
Stop the server (Ctrl+C) when done.

- [ ] **Step 8: Commit**

```bash
git add Backend/GameSessionService/app/routes/ Backend/GameSessionService/app/main.py Backend/GameSessionService/tests/test_routes.py
git commit -m "refactor: slim main.py down to app creation + router inclusion"
```

---

## Final check

After Task 7, re-run the full suite once more from a clean state to confirm
nothing regressed across tasks:

```bash
cd Backend/GameSessionService && ruff check . && ruff format --check . && pytest -v
```

All 8 review findings covered by this plan (item 2 was already fixed prior
to this plan): items 1, 3, 4, 5, 6, 7, 8, 9 are addressed by Tasks 1-7 above.
