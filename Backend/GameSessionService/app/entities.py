import math
import random

import pymunk

SHIP_MASS = 1.0
SHIP_RADIUS = 20.0
SHIP_THRUST_FORCE = 400.0
SHIP_TURN_RATE = 3.0  # radians/sec
SHIP_MAX_SPEED = 90.0  # px/sec — deliberately low handling cap

# "Mostly elastic" collisions with a touch of friction — pymunk shapes
# default to 0/0, which would make any contact perfectly inelastic (bodies
# stick instead of bouncing).
COLLISION_ELASTICITY = 0.8
COLLISION_FRICTION = 0.3

# Same density for every asteroid, so mass scales purely with size (area).
ASTEROID_DENSITY = SHIP_MASS / SHIP_RADIUS**2
ASTEROID_MAX_SPEED = (
    300.0  # generous cap vs. SHIP_MAX_SPEED, guards against runaway collision velocity
)
ASTEROID_DRIFT_FORCE = 5.0  # small sinusoidal wobble force for drift=True asteroids

# The server is the sole source of truth for the asteroid layout (positions
# are no longer hand-copied to the frontend — see generate_asteroid_layout).
# A fixed seed keeps the layout stable across restarts for dev/testing.
ASTEROID_COUNT = 45
ASTEROID_LAYOUT_SEED = 42
ASTEROID_MIN_R = 26.0
ASTEROID_MAX_R = 48.0
ASTEROID_DRIFT_CHANCE = 0.5
ASTEROID_DRIFT_PERIOD_RANGE = (15000.0, 30000.0)  # ms
ASTEROID_MIN_GAP = 10.0  # px clearance required between any two asteroids
ASTEROID_SHIP_CLEARANCE = 150.0  # px clearance required around ship spawn
ASTEROID_PLACEMENT_ATTEMPTS = 500  # per asteroid, before giving up and placing anyway


def generate_asteroid_layout(
    center: tuple[float, float],
    inner_r: float,
    outer_r: float,
    ship_spawn: tuple[float, float],
    count: int = ASTEROID_COUNT,
    seed: int = ASTEROID_LAYOUT_SEED,
) -> list[tuple[str, float, float, float, bool, float | None]]:
    """Scatters `count` asteroids across the belt annulus around `center`.

    Deterministic for a given seed. Uses rejection sampling to keep
    asteroids clear of each other and of the ship's spawn point — each
    candidate is retried (up to ASTEROID_PLACEMENT_ATTEMPTS times) until it
    clears both, falling back to the last candidate if that cap is hit
    (the annulus is large relative to asteroid size, so this is rare).
    Returns (id, x, y, r, drift, period) tuples, matching the old
    ASTEROID_DEFS shape.
    """
    rng = random.Random(seed)
    cx, cy = center
    sx, sy = ship_spawn
    placed: list[tuple[float, float, float]] = []  # (x, y, r)
    layout: list[tuple[str, float, float, float, bool, float | None]] = []

    for i in range(count):
        radius = rng.uniform(ASTEROID_MIN_R, ASTEROID_MAX_R)
        x = y = 0.0
        for _ in range(ASTEROID_PLACEMENT_ATTEMPTS):
            angle = rng.uniform(0, 2 * math.pi)
            distance = rng.uniform(inner_r + radius, outer_r - radius)
            x = cx + math.cos(angle) * distance
            y = cy + math.sin(angle) * distance

            clear_of_ship = (
                math.hypot(x - sx, y - sy) >= radius + ASTEROID_SHIP_CLEARANCE
            )
            clear_of_others = all(
                math.hypot(x - px, y - py) >= radius + pr + ASTEROID_MIN_GAP
                for px, py, pr in placed
            )
            if clear_of_ship and clear_of_others:
                break

        placed.append((x, y, radius))
        drift = rng.random() < ASTEROID_DRIFT_CHANCE
        period = rng.uniform(*ASTEROID_DRIFT_PERIOD_RANGE) if drift else None
        layout.append((f"ast-{i + 1}", x, y, radius, drift, period))

    return layout


class Ship:
    """A player-controlled ship: a pymunk Body + Circle wrapped with game state."""

    def __init__(self, ship_id: str, position: tuple[float, float]) -> None:
        self.id = ship_id
        moment = pymunk.moment_for_circle(SHIP_MASS, 0, SHIP_RADIUS)
        self.body = pymunk.Body(SHIP_MASS, moment)
        self.body.position = position
        self.shape = pymunk.Circle(self.body, SHIP_RADIUS)
        self.shape.elasticity = COLLISION_ELASTICITY
        self.shape.friction = COLLISION_FRICTION

    def to_state(self) -> dict:
        return {
            "id": self.id,
            "x": self.body.position.x,
            "y": self.body.position.y,
            "rotation": self.body.angle,
            "vx": self.body.velocity.x,
            "vy": self.body.velocity.y,
        }


class Asteroid:
    """A dynamic pymunk Body + Circle, structurally identical to Ship."""

    def __init__(
        self,
        asteroid_id: str,
        position: tuple[float, float],
        radius: float,
        drift: bool = False,
        period: float | None = None,
    ) -> None:
        self.id = asteroid_id
        self.radius = radius
        self.drift = drift
        self.period = period
        mass = ASTEROID_DENSITY * radius**2
        moment = pymunk.moment_for_circle(mass, 0, radius)
        self.body = pymunk.Body(mass, moment)
        self.body.position = position
        self.shape = pymunk.Circle(self.body, radius)
        self.shape.elasticity = COLLISION_ELASTICITY
        self.shape.friction = COLLISION_FRICTION

    def to_state(self) -> dict:
        return {
            "id": self.id,
            "x": self.body.position.x,
            "y": self.body.position.y,
            "rotation": self.body.angle,
            "vx": self.body.velocity.x,
            "vy": self.body.velocity.y,
        }
