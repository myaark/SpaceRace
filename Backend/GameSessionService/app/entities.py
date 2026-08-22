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

# (id, x, y, r, drift, period) — values copied from
# Frontend/src/scenes/BeltScene.js's ASTEROIDS array; kept in sync by hand
# (same convention as BELT_CENTER / fence radii).
ASTEROID_DEFS = [
    ("ast-1", 574, 262, 30, True, 17000),
    ("ast-2", 835, 500, 26, False, None),
    ("ast-3", 981, 277, 44, True, 23000),
    ("ast-4", 490, 202, 36, False, None),
    ("ast-5", 906, 182, 34, True, 29000),
    ("ast-6", 798, 223, 28, False, None),
    ("ast-7", 804, 385, 48, True, 19000),
    ("ast-8", 1063, 363, 40, False, None),
    ("ast-9", 966, 589, 32, True, 21000),
    ("ast-10", 1123, 673, 26, False, None),
]


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
