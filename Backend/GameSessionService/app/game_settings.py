import math
from dataclasses import dataclass, field

SPAWN_POINT_COUNT = 10


def _generate_spawn_points(
    base_offset: tuple[float, float],
) -> list[tuple[float, float]]:
    """Rotates base_offset around the origin in SPAWN_POINT_COUNT equal
    angular steps, so point 0 is identical to base_offset (preserving the
    existing frontend spawn-compat point) and the rest sit on the same
    radius, evenly spaced around it."""
    ox, oy = base_offset
    radius = math.hypot(ox, oy)
    base_angle = math.atan2(oy, ox)
    points = [base_offset]  # Point 0 is exact base_offset, not computed via trig
    points.extend(
        (
            radius * math.cos(base_angle + 2 * math.pi * i / SPAWN_POINT_COUNT),
            radius * math.sin(base_angle + 2 * math.pi * i / SPAWN_POINT_COUNT),
        )
        for i in range(1, SPAWN_POINT_COUNT)
    )
    return points


@dataclass
class GameSettings:
    """Mutable, runtime-tunable gameplay/physics values.

    Read fresh at point of use (per tick or per object construction) via
    the module-level `game_settings` singleton below — there is no change
    hook, so edits to a field only affect objects constructed after the
    edit, and take effect immediately for values re-read every tick.
    """

    # Ship body/physics
    ship_mass: float = 1.0
    ship_radius: float = 20.0
    ship_thrust_force: float = 400.0
    ship_turn_rate: float = 3.0  # radians/sec
    ship_max_speed: float = 90.0  # px/sec — deliberately low handling cap
    space_damping: float = 0.0003  # Fraction of velocity retained per second — unpowered ship stops in ~0.3s.

    # Room capacity — matches the product plan's 2-10 players per match.
    # There is deliberately no minimum enforced here: gating "room readiness"
    # at 2+ players is a matchmaking-layer concern, not this service's.
    max_players: int = 10

    # "Mostly elastic" collisions with a touch of friction — pymunk shapes
    # default to 0/0, which would make any contact perfectly inelastic
    # (bodies stick instead of bouncing).
    collision_elasticity: float = 0.8
    collision_friction: float = 0.3

    # Asteroid body/physics. Density matches ship_mass / ship_radius**2 so
    # mass scales purely with size (area) at the current ship defaults —
    # kept as a literal (not derived) so changing ship_mass/ship_radius
    # doesn't silently retune every asteroid's mass.
    asteroid_density: float = 1.0 / 20.0**2
    asteroid_max_speed: float = 300.0  # generous cap vs. ship_max_speed
    asteroid_drift_force: float = 5.0  # sinusoidal wobble force, drift=True

    # Asteroid belt layout generation (applied at session/layout creation
    # only — not live, since layout is generated once per session).
    asteroid_count: int = 45
    asteroid_layout_seed: int = 42
    # Fixed size/HP tiers — replaces the old continuous asteroid_min_r/
    # asteroid_max_r range. generate_asteroid_layout samples a tier per
    # asteroid instead of a continuous radius.
    asteroid_tiers: dict[str, dict[str, float]] = field(
        default_factory=lambda: {
            "large": {"radius": 48.0, "hp": 30},
            "medium": {"radius": 34.0, "hp": 15},
            "small": {"radius": 20.0, "hp": 5},
        }
    )
    asteroid_drift_chance: float = 0.5
    asteroid_drift_period_range: tuple[float, float] = (15000.0, 30000.0)  # ms
    asteroid_min_gap: float = 10.0  # px clearance between any two asteroids
    asteroid_ship_clearance: float = 150.0  # px clearance around each ship spawn point
    asteroid_placement_attempts: int = 500  # per asteroid, before giving up

    # Bullets
    bullet_speed: float = 500.0  # muzzle speed added along facing direction, px/sec
    bullet_lifetime_ms: float = 2000.0
    bullet_damage_to_asteroid: int = 10
    bullet_damage_to_ship: int = 10

    # Ship health
    ship_max_hp: int = 100

    # Fragmentation
    asteroid_fragment_impulse: float = 80.0  # outward push on fragment children, px/sec

    # Ship-asteroid ram damage (pymunk collision handler, see session.py)
    ram_damage_by_tier: dict[str, int] = field(
        default_factory=lambda: {"large": 20, "medium": 12, "small": 5}
    )
    ram_cooldown_ms: float = 500.0  # per (ship, asteroid) pair, prevents re-damage every tick of sustained contact

    # Belt boundary geometry. Must match Frontend/src/scenes/BeltScene.js's
    # BELT_CENTER / OUTER_FENCE_R / INNER_FENCE_R — there is no shared-schema
    # mechanism enforcing this, so keep the two in sync by hand.
    belt_center: tuple[float, float] = (-200.0, 1500.0)

    # Offset from belt_center to Frontend/src/scenes/BeltScene.js's SHIP
    # constant (724, 318). The first-connecting ship must spawn exactly
    # here — it's the only point the frontend draws before the first server
    # state arrives, so any mismatch makes that ship appear to teleport on
    # the first broadcast. spawn_points[0] (derived below) always equals
    # this value.
    spawn_offset: tuple[float, float] = (924.0, -1182.0)
    inner_fence_r: float = 1420.0
    outer_fence_r: float = 1760.0

    # Derived at construction time from spawn_offset (not live-tunable —
    # same "construction-time" category as the asteroid layout constants
    # above). Point 0 always equals spawn_offset exactly; the rest are
    # spawn_offset rotated around belt_center in even angular steps, one
    # per max_players slot.
    spawn_points: list[tuple[float, float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.spawn_points:
            self.spawn_points = _generate_spawn_points(self.spawn_offset)


game_settings = GameSettings()
