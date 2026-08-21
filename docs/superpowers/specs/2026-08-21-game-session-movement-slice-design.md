# Game Session Movement Slice — Design

Status: approved for planning
Date: 2026-08-21

## Context

`asteroid-belt-game-plan.md` already establishes the repo's high-level
architecture: server-authoritative game state, FastAPI + WebSockets,
pymunk physics, a fixed-tick game loop, and a belt-shaped movement
boundary. That plan is a reference, not an implementation.

Current code state:

- **Frontend** (`Frontend/src/scenes/BeltScene.js`) is a static art
  mockup: hardcoded asteroid positions, one non-moving ship, decorative
  tweens. No entity model, no input handling, no networking.
- **Backend** (`Backend/GameSessionService/app/`) is a FastAPI skeleton:
  `/ws/{room_id}` accepts a connection and does nothing; `game_loop.py`
  is an empty tick stub. No entities, no physics, no state broadcast.

This spec designs the first real slice of game logic: a single ship
that a player can move, with the server as the authority, wired
end-to-end from keyboard input to rendered position. It intentionally
excludes asteroids, combat, scoring, respawn, and matchmaking — those
are later slices building on this foundation.

## Goals

- Establish how game objects are represented on the backend and mirrored
  on the frontend, as a pattern later slices (asteroids, projectiles,
  other players) will reuse.
- Prove the full pipeline: keyboard input → WebSocket → server physics →
  belt boundary enforcement → state broadcast → client render.
- Keep the slice small enough to implement and verify independently on
  each side of the stack.

## Non-goals

- Multiple simultaneous players / other players' ships.
- Client-side prediction or reconciliation (deferred per the game-plan
  doc's Decision 1 trade-off note).
- Matchmaking Service integration — the client connects to a fixed dev
  room.
- Asteroids, projectiles, combat, scoring, respawn.
- Delta-compressed state broadcasts (full state is sent every tick, per
  the game-plan doc).

## Object representation

**Server defines, client mirrors.** The backend owns authoritative
entity state as Python objects. There is no shared schema/codegen
between languages — the JSON broadcast shape is an informal contract,
documented in this spec, matching the project's preference for minimal
tooling at this scale.

- Backend: a `Ship` class wraps a pymunk `Body` + `Circle` shape (mass,
  moment, position, velocity, angle). It exposes `.to_state()`,
  returning the JSON-serializable dict sent to clients.
- Frontend: an independent `RemoteShip` Phaser object with no physics of
  its own. It only reads server-provided fields and updates its
  sprite's position/rotation via `.applyState()`.

### Protocol (this slice)

**Client → Server**, sent on input change (not every frame):

```json
{ "type": "input", "seq": 0, "thrust": -1 | 0 | 1, "turn": -1 | 0 | 1 }
```

**Server → Client**, broadcast every tick (~20 Hz):

```json
{
  "type": "state",
  "tick": 0,
  "ship": { "id": "string", "x": 0, "y": 0, "rotation": 0, "vx": 0, "vy": 0 }
}
```

Single-ship only in this slice, so no entity list or diffing is needed
yet — `ship` is one object, not an array.

### Shared boundary constants

The belt geometry (`BELT_CENTER`, `INNER_FENCE_R`, `OUTER_FENCE_R`) must
agree between the server's authoritative clamp and the client's visual
rendering in `BeltScene.js`. This is the first concrete case of FE/BE
needing to agree on a number; call it out explicitly in code comments on
both sides rather than leaving it to coincidence, since there's no
shared-schema mechanism enforcing it.

## Backend architecture (this slice)

New files under `Backend/GameSessionService/app/`:

- **`entities.py`** — `Ship` class wrapping a pymunk `Body`+`Circle`.
  Holds `id`; exposes `.to_state()`.
- **`session.py`** — `GameSession` class: owns the pymunk `Space`, the
  single `Ship` instance for this slice, the set of connected
  WebSockets, and a `latest_input` buffer keyed by client. Replaces the
  TODOs in `game_loop.py`'s `run_game_loop()`: each tick, apply the
  latest buffered input as a force/impulse on the ship body,
  `space.step()`, clamp position into the belt annulus (zero out the
  radial velocity component if the ship would exit the ring, per
  game-plan Section 7), then broadcast `.to_state()` to all connected
  sockets.

Changes to `main.py`: the `/ws/{room_id}` handler creates or attaches to
a `GameSession` (created on first connect, since matchmaking isn't
wired up yet), reads incoming `input` messages into
`session.latest_input`, and stays open until disconnect.

## Frontend architecture (this slice)

New files under `Frontend/src/`:

- **`net/GameSocket.js`** — WebSocket wrapper: connects to a dev room
  URL, exposes `sendInput({thrust, turn})` and an `onState(callback)`
  subscription. Retries once on unexpected disconnect.
- **`entities/RemoteShip.js`** — wraps the existing hull/thruster
  graphics (currently inline in `drawPlayerShip()`) as a Phaser
  container with `.applyState({x, y, rotation})`, updating position
  directly from server state. No client-side prediction.

Changes to `BeltScene.js`: `create()` instantiates `GameSocket` and one
`RemoteShip` instead of calling `drawPlayerShip()` directly; keyboard
input (arrow keys/WASD) is read each frame, diffed against last-sent
input, and `sendInput()` is called only on change; the `onState()`
callback calls `remoteShip.applyState(msg.ship)`. All decorative
belt/asteroid/salvage/hostile drawing is untouched.

## Flow

1. Client connects → server creates or attaches to the dev
   `GameSession`, spawning the ship at a fixed start point.
2. Client sends `input` messages on key-state change.
3. Server buffers the latest input per tick.
4. Tick loop: apply input to the pymunk body → `space.step()` → clamp to
   belt boundary → broadcast `state`.
5. Client applies `state` directly to `RemoteShip` (no interpolation or
   prediction in this slice).

## Error handling (minimal, this slice)

- Malformed input messages are logged and ignored, not treated as fatal.
- On WebSocket disconnect, the server drops the client reference; the
  tick loop keeps running (the ship stops receiving input and coasts to
  rest under drag, or just stops).
- The client's `GameSocket` retries the connection once on drop.
- Full reconnection UX and session lifecycle (idle cleanup,
  matchmaking-driven creation/teardown) are out of scope — deferred to
  the matchmaking-integration slice.

## Testing

- **Backend**: pytest tests against `GameSession`/`Ship` directly (no
  real WebSocket needed) — a boundary-clamp test (ship pushed radially
  outward stays within `[INNER_FENCE_R, OUTER_FENCE_R]`) and an
  input-applies-velocity test.
- **Frontend**: manual verification — run the dev server, confirm
  keyboard input moves the ship and the boundary is respected, per this
  repo's UI-testing convention (no automated frontend test harness
  exists yet).

## Sequencing

Per `CLAUDE.md`'s work-isolation rule (no mixing Frontend/ and Backend/
work in one session), this is implemented as two separate efforts,
backend first:

1. **Backend session**: `entities.py`, `session.py`, `main.py` wiring,
   pytest tests. Verifiable standalone with a throwaway WebSocket test
   client confirming state broadcasts.
2. **Frontend session**: `GameSocket.js`, `RemoteShip.js`,
   `BeltScene.js` wiring, manual browser verification against the
   now-working backend.

## Deferred (future slices)

- Multiple players / other-player ships in the state broadcast.
- Client-side prediction and server reconciliation.
- Matchmaking Service integration (dynamic room creation, session
  lifecycle).
- Asteroids as entities, collision detection, combat, scoring, respawn.
- Delta-compressed state broadcasts.
