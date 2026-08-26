from dataclasses import dataclass


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
    asteroid_min_r: float = 26.0
    asteroid_max_r: float = 48.0
    asteroid_drift_chance: float = 0.5
    asteroid_drift_period_range: tuple[float, float] = (15000.0, 30000.0)  # ms
    asteroid_min_gap: float = 10.0  # px clearance between any two asteroids
    asteroid_ship_clearance: float = 150.0  # px clearance around ship spawn
    asteroid_placement_attempts: int = 500  # per asteroid, before giving up


game_settings = GameSettings()
