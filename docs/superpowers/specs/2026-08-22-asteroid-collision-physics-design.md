# Asteroid Collision Physics — Design

Status: approved for planning
Date: 2026-08-22

## Context

The movement slice (`2026-08-21-game-session-movement-slice-design.md`)
made the ship a real pymunk body, server-authoritative, with no other
physics objects in the world. Asteroids currently exist only as
decorative frontend art (`Frontend/src/scenes/BeltScene.js`'s
`ASTEROIDS` array): static circles, some wobbling via client-side
`tweens.add`. They have no presence in the backend's `pymunk.Space` and
never interact with the ship.

This spec adds real collision physics: the ship can hit asteroids (and
asteroids can hit each other), and both bodies' velocities change based
on their relative mass/size — a large asteroid barely moves and
deflects the ship hard, a small one is easily pushed aside and barely
affects the ship's course. Asteroid position/motion becomes fully
server-authoritative, replacing the client-side tweens.

## Goals

- Asteroids become real dynamic pymunk bodies in the same `Space` as the
  ship, with mass proportional to size, so collisions resolve via
  pymunk's own momentum-conserving solver (no hand-rolled deflection
  math).
- Idle asteroid motion (the current decorative "drift") becomes a
  server-applied physics force, not a client tween — all asteroid
  positioning lives on the backend.
- Frontend renders asteroids purely from server state broadcasts, the
  same pattern `RemoteShip` already uses for the ship.
- Asteroids stay within the belt ring boundary, same as the ship.

## Non-goals

- Ship damage/HP or any game-over-on-impact logic — this is physics
  only.
- Asteroid-asteroid collisions are not specially handled or excluded —
  they fall out of putting all asteroids in the same `Space` for free,
  but no bespoke logic targets them.
- Salvage marker / hostile marker — unaffected, remain decorative.
- Multiple players, matchmaking, combat, scoring — unrelated to this
  slice, unchanged from prior scope.

## Object representation

Extends the movement slice's pattern: server owns authoritative state,
client mirrors it via `.applyState()`.

- Backend: `Asteroid` class (new, in `entities.py`) wraps a pymunk
  `Body` + `Circle`, structurally identical to `Ship` — `id`, position,
  velocity, angle, exposing `.to_state()`.
- Frontend: `RemoteAsteroid` class (new, in `entities/`) — a Phaser
  container holding just the existing asteroid circle graphic, updated
  only via `.applyState({x, y})`. No local motion logic.

### Protocol changes

**Server → Client**, broadcast every tick — adds an `asteroids` array
alongside the existing `ship`:

```json
{
  "type": "state",
  "tick": 0,
  "ship": { "id": "string", "x": 0, "y": 0, "rotation": 0, "vx": 0, "vy": 0 },
  "asteroids": [
    { "id": "string", "x": 0, "y": 0, "rotation": 0, "vx": 0, "vy": 0 }
  ]
}
```

Radius is not sent — it never changes, so it stays a client-side
constant (matching how `SHIP_SIZE` is a frontend constant today), keyed
by the same `id` the backend uses.

### Shared asteroid layout

Frontend scene coordinates and backend pymunk world coordinates are
already the same coordinate space (confirmed via the ship's
`SPAWN_OFFSET`, which sums to the frontend's hardcoded `SHIP` position).
So the backend's initial asteroid layout is the *same* `(id, x, y, r)`
tuples as the frontend's `ASTEROIDS` array — no coordinate conversion
needed, just kept in sync by hand (same convention as `BELT_CENTER` /
fence radii today). Both sides gain explicit `id` fields (`"ast-1"` …
`"ast-10"`) to match entities across the broadcast, same role `"ship-1"`
plays for the ship.

## Backend architecture

Changes under `Backend/GameSessionService/app/`:

- **`entities.py`**:
  - `Asteroid` class: pymunk `Body`+`Circle`, `mass = ASTEROID_DENSITY *
    radius ** 2` where `ASTEROID_DENSITY = SHIP_MASS / SHIP_RADIUS ** 2`
    (same density as the ship, so mass scales purely with size —
    smallest asteroids ≈ ship-weight, largest are several times
    heavier). `.to_state()` mirrors `Ship.to_state()`.
  - `ASTEROID_DEFS`: the 10 `(id, x, y, r, drift, period)` tuples,
    values copied from the frontend's current `ASTEROIDS` array
    (`period` is only meaningful when `drift` is true).
  - Add `elasticity` (~0.8, "mostly elastic" per design discussion) and
    modest `friction` to both `Ship`'s and `Asteroid`'s shapes — today
    neither sets these, so any contact would be perfectly inelastic
    (pymunk shape defaults). This is what makes collisions bounce
    instead of stick.
  - `ASTEROID_MAX_SPEED`: a generous cap (independent from
    `SHIP_MAX_SPEED`) to prevent runaway velocity from repeated/stacked
    collisions.

- **`session.py`**:
  - `GameSession.__init__` builds all 10 `Asteroid`s from
    `ASTEROID_DEFS` and adds each body+shape to `self.space`.
  - `_clamp_to_belt` and `_clamp_speed` are generalized to take a body
    (and, for the belt clamp, that body's own max/min radius — same
    logic, just no longer hardcoded to `self.ship.body`), then called
    once for the ship and once per asteroid each tick.
  - New `_apply_drift()`: for asteroids with `drift = True`, applies a
    small continuous sinusoidal force each tick (phase/period per
    asteroid, reusing the existing `period` values from the frontend's
    tween config) — this replaces the client tween with an
    authoritative, server-computed wobble. Non-drift asteroids receive
    no force and stay still until struck.
  - `step()` gains `_apply_drift()` before `space.step()`, and the
    per-body clamp calls after it, alongside the existing ship-only
    logic.
  - `to_broadcast_message()` adds `"asteroids": [a.to_state() for a in
    self.asteroids.values()]`.
  - No collision callbacks/handlers needed — pymunk's default solver
    already resolves the elastic collision using each body's mass,
    given both are dynamic bodies with elasticity set.

## Frontend architecture

Changes under `Frontend/src/`:

- **`entities/RemoteAsteroid.js`** (new): Phaser container wrapping the
  existing fill/stroke circle graphic (currently inlined in
  `drawAsteroids()`), with `.applyState({x, y})` setting position only
  (asteroids are circles — rotation has no visible effect, so it's not
  applied, unlike the ship).
- **`scenes/BeltScene.js`**:
  - `ASTEROIDS` keeps `id`/`x`/`y`/`r` (radius + initial placeholder
    position before the first server broadcast arrives, same role the
    `SHIP` constant plays today) but drops `drift`/`period` — those now
    only matter server-side.
  - `create()` builds a `Map<id, RemoteAsteroid>` from `ASTEROIDS`
    instead of calling the old `drawAsteroids()` tween logic.
  - The `gameSocket.onState()` callback, alongside
    `remoteShip.applyState(msg.ship)`, iterates `msg.asteroids` and
    calls `.applyState()` on the matching map entry by `id`.

## Flow

1. Session init: server builds the ship and all 10 asteroids as dynamic
   pymunk bodies in one `Space`.
2. Each tick: apply ship input → apply drift force to drifting asteroids
   → `space.step()` (resolves all collisions via mass/elasticity,
   including ship↔asteroid and incidental asteroid↔asteroid) → clamp
   every body to the belt ring → clamp speeds → broadcast full state
   (`ship` + `asteroids`).
3. Client applies `state` directly to `RemoteShip` and each
   `RemoteAsteroid` — no interpolation or prediction, consistent with
   the movement slice.

## Error handling

No new error paths beyond the movement slice's existing ones (malformed
input ignored, disconnect drops the client reference). Physics
stability is handled by `ASTEROID_MAX_SPEED` capping runaway velocity
rather than by error handling per se.

## Testing

- **Backend**: pytest tests against `GameSession`/`Asteroid` directly —
  mass scales with `radius ** 2` as expected; a ship-asteroid collision
  transfers momentum proportionally to mass (heavier asteroid produces
  a smaller ship velocity change than a lighter one, given the same
  approach velocity); asteroids stay within the belt annulus under an
  applied drift force over many ticks.
- **Frontend**: manual verification — run the dev server, confirm
  asteroids render at their initial positions, drift server-side, and
  visibly bounce off the ship (and each other) on contact, per this
  repo's existing UI-testing convention (no automated frontend test
  harness yet).

## Sequencing

Per `CLAUDE.md`'s work-isolation rule, this would normally split into a
backend session and a frontend session — the user has explicitly
approved doing both in this session for this task. Implementation still
proceeds backend-first (asteroids must exist and broadcast before the
frontend has anything to consume), then frontend, so each side stays
independently verifiable:

1. **Backend**: `entities.py` (`Asteroid`, `ASTEROID_DEFS`,
   elasticity/friction, `ASTEROID_MAX_SPEED`), `session.py` (asteroid
   bodies in the space, generalized clamps, `_apply_drift`, broadcast
   schema), pytest coverage.
2. **Frontend**: `RemoteAsteroid.js`, `BeltScene.js` wiring, manual
   browser verification against the now-working backend.

## Deferred (future slices)

- Ship damage/HP from collisions.
- Bespoke asteroid-asteroid collision behavior (fragmentation, merging,
  etc.) beyond incidental physics contact.
- Delta-compressed state broadcasts (still full state every tick, per
  the game-plan doc).
