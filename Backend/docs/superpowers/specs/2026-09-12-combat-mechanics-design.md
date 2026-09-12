# Combat Mechanics — Backend Design

Status: approved for implementation planning
Scope: `Backend/GameSessionService` only (server-authoritative rules). Frontend
presentation (input capture, bullet rendering, health bar UI) is a separate,
later spec/session per root `CLAUDE.md`'s Frontend/Backend work isolation rule.

## 1. Overview

Adds player-vs-asteroid and player-vs-player combat to the game session:
ships fire bullets, bullets damage asteroids (which fragment into smaller
pieces) and other ships (which lose health and can die). This spec covers
damage/fragmentation/death rules only — the death → cooldown → respawn cycle
described in the product game plan (Section 8) is explicitly deferred to a
future spec; a dead ship here is simply flagged dead and stops interacting
with the game, with no revival path yet.

## 2. Module layout & tick flow

New module `app/combat.py`, alongside the existing `entities.py` /
`game_settings.py` split: houses the `Bullet` class and fragmentation/damage
helper functions. `session.py` gains bullet storage (`self.bullets: dict[str,
Bullet]`) and calls into `combat.py` each tick. `game_loop.py` is unchanged —
it only calls `session.step()`.

Updated per-tick order in `GameSession.step()`:

1. Apply ship input (existing — now also reads `fire`)
2. Spawn bullets for ships that fired this tick
3. Advance existing bullets, expire out-of-lifetime/out-of-belt ones
4. Detect bullet collisions (vs ships, vs asteroids); apply damage
5. Apply fragmentation/death from any HP that hit 0 this tick
6. Apply drift (existing)
7. `space.step(dt)` (existing pymunk integration — asteroid-ship ram damage
   is detected here via a pymunk collision handler, see §5)
8. Clamp speed / belt boundary (existing)

## 3. Bullets

- `Bullet` (plain dataclass, no pymunk body — bullets are simple, fast,
  short-lived, and must not bounce): `id`, `owner_id`, `x`, `y`, `vx`, `vy`,
  `spawned_at_ms`.
- Spawn: at the firing ship's nose (ship position + `ship_radius` offset
  along `body.angle`), velocity = ship velocity + fixed muzzle speed along
  the facing direction.
- No fire-rate limit or ammo: every tick where a ship's latest input has
  `fire: true`, one bullet spawns for it (effective rate is bounded by
  client input send rate / tick rate).
- Advance: `position += velocity * dt` each tick.
- Expiry: removed after `bullet_lifetime_ms` (new `game_settings` field) or
  once its distance from `belt_center` exceeds `outer_fence_r`, whichever
  comes first.
- Collision detection: **swept segment-vs-circle** — test the segment from
  the bullet's previous position to its new position against each ship's
  and asteroid's circle, rather than a point check at the new position only.
  This avoids tunneling through targets at high bullet speed / fixed tick
  rate. First hit wins; the bullet is removed on any hit (no piercing) and
  cannot damage its own `owner_id`.

## 4. Asteroid HP & fragmentation

- `Asteroid` gains `tier` (`"large" | "medium" | "small"`), `max_hp`, `hp`.
- New `game_settings.asteroid_tiers` table maps each tier to `radius` and
  `hp`, e.g.:

  ```python
  asteroid_tiers = {
      "large":  {"radius": 48.0, "hp": 30},
      "medium": {"radius": 34.0, "hp": 15},
      "small":  {"radius": 20.0, "hp": 5},
  }
  ```

  (Exact values tunable at implementation time; existing
  `asteroid_min_r`/`asteroid_max_r` range is replaced by sampling from these
  three tiers instead of a continuous range.)
- `generate_asteroid_layout` is updated to assign each generated asteroid
  the nearest tier for its sampled radius (or sample tier directly instead
  of a continuous radius — implementation detail for the plan) and set
  `hp = max_hp = asteroid_tiers[tier]["hp"]`.
- Each bullet hit subtracts a fixed `bullet_damage_to_asteroid` (new
  `game_settings` field) from `hp`. When `hp <= 0`:
  - `large` or `medium` → destroy this asteroid; spawn 2 children one tier
    smaller at the parent's position, pymunk body/shape constructed via the
    same code path `generate_asteroid_layout`/`Asteroid.__init__` already
    use. Children get a small outward impulse in randomized opposite
    directions (so they don't immediately overlap) and independently
    re-rolled `drift`/`period`.
  - `small` → destroyed outright, no children.

## 5. Ship health & damage sources

- `Ship` gains `max_hp`, `hp` (new `game_settings.ship_max_hp` default).
- Bullet hits a ship (not its own `owner_id`) → subtract
  `bullet_damage_to_ship` (separate tunable from asteroid damage) from `hp`.
- Ship–asteroid ram damage: detected via a pymunk
  `space.add_collision_handler(ship_collision_type, asteroid_collision_type)`
  begin/pre-solve callback (reusing pymunk's existing contact detection
  rather than a separate manual distance check). Damage scales with the
  asteroid's `tier`. A per-(ship, asteroid)-pair cooldown guard prevents a
  single sustained graze from re-applying damage every tick while the
  bodies stay in contact.
- At `hp <= 0` → ship's `alive` flag becomes `False` (see §6). No respawn.

## 6. Death handling (respawn deferred)

- Ship gains `alive: bool = True`.
- Once `alive` is `False`:
  - `_apply_input` skips it — no thrust/turn is applied, so a dead ship
    drifts to a stop (subject to existing `space_damping`) rather than
    continuing to fly under player control.
  - Further bullet or asteroid-collision damage against it is a no-op
    (already-dead check short-circuits before HP subtraction).
  - It is **not** removed from `self.ships` / the pymunk space —
    unregistering is reserved for actual disconnects — so a future respawn
    spec can revive it in place without re-deriving connection state.
- No cooldown timer, no respawn point selection, no re-entry into combat —
  explicitly out of scope for this spec.

## 7. Broadcast schema changes (`app/models/messages.py`)

- `ShipState` gains `hp: int`, `max_hp: int`, `alive: bool`.
- New `BulletState` (`id: str`, `x: float`, `y: float`, `rotation: float`)
  for client rendering; `StateMessage` gains `bullets: list[BulletState]`.
- Asteroid state (`AsteroidInit` and/or the broadcast asteroid entries)
  gains `hp: int`, `max_hp: int`.
- Since fragmentation creates/destroys asteroids mid-match (the initial
  layout from `to_init_message` is no longer the complete lifetime set),
  `StateMessage` gains:
  - `asteroids_spawned: list[AsteroidInit]` — any asteroid created this
    tick (fragmentation children), same shape as the existing `init`
    asteroid entries.
  - `asteroids_removed: list[str]` — ids of asteroids destroyed this tick.

  This avoids re-broadcasting full asteroid existence/liveness every tick.
- Client → server input message gains `fire: bool`, alongside the existing
  `thrust`/`turn` fields.

## 8. Testing

Following the existing per-service convention (one test per implementation
step, not just an end-to-end test):

- New `tests/test_combat.py`:
  - Bullet spawn position/velocity from a firing ship
  - Bullet advancement and expiry (lifetime and belt-exit cases)
  - Swept segment-vs-circle collision math (hit, miss, tunneling-prevented
    case)
  - Asteroid tier fragmentation: correct child count/tier/radius/hp on
    large→medium and medium→small splits; small asteroids destroyed with no
    children
  - Ship HP depletion from bullet hits; `alive` flips to `False` at 0 hp;
    no negative-HP or double-death edge cases
  - Asteroid-ship ram damage scaling by tier, and the repeat-hit cooldown
    guard (single sustained contact only damages once per cooldown window)
  - Bullet cannot damage its own `owner_id`
- Updates to existing `tests/test_session.py` / `tests/test_entities.py` for
  the new fields and their integration into `GameSession.step()`.

## Out of scope

- Death → cooldown → respawn cycle (future spec)
- Frontend presentation: mouse-fire input capture, bullet rendering, health
  bar UI, hit/break visual feedback (future spec, separate session per
  Frontend/Backend work isolation rule)
- Fire-rate limiting / ammo (explicitly no limit for this iteration)
- Scoring integration with `LeaderboardService` for asteroid/ship kills
  (game plan already describes scoring in general terms; wiring combat
  events to score submission is not addressed here)
