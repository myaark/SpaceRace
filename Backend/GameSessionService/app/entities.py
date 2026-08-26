import math
import random

import pymunk

from app.settings import settings


def generate_asteroid_layout(
    center: tuple[float, float],
    inner_r: float,
    outer_r: float,
    ship_spawn: tuple[float, float],
    count: int | None = None,
    seed: int | None = None,
) -> list[tuple[str, float, float, float, bool, float | None]]:
    """Scatters `count` asteroids across the belt annulus around `center`.

    Deterministic for a given seed. Uses rejection sampling to keep
    asteroids clear of each other and of the ship's spawn point — each
    candidate is retried (up to settings.asteroid_placement_attempts times)
    until it clears both, falling back to the last candidate if that cap is
    hit (the annulus is large relative to asteroid size, so this is rare).
    Returns (id, x, y, r, drift, period) tuples, matching the old
    ASTEROID_DEFS shape.
    """
    count = settings.asteroid_count if count is None else count
    seed = settings.asteroid_layout_seed if seed is None else seed
    rng = random.Random(seed)
    cx, cy = center
    sx, sy = ship_spawn
    placed: list[tuple[float, float, float]] = []  # (x, y, r)
    layout: list[tuple[str, float, float, float, bool, float | None]] = []

    for i in range(count):
        radius = rng.uniform(settings.asteroid_min_r, settings.asteroid_max_r)
        x = y = 0.0
        for _ in range(settings.asteroid_placement_attempts):
            angle = rng.uniform(0, 2 * math.pi)
            distance = rng.uniform(inner_r + radius, outer_r - radius)
            x = cx + math.cos(angle) * distance
            y = cy + math.sin(angle) * distance

            clear_of_ship = (
                math.hypot(x - sx, y - sy) >= radius + settings.asteroid_ship_clearance
            )
            clear_of_others = all(
                math.hypot(x - px, y - py) >= radius + pr + settings.asteroid_min_gap
                for px, py, pr in placed
            )
            if clear_of_ship and clear_of_others:
                break

        placed.append((x, y, radius))
        drift = rng.random() < settings.asteroid_drift_chance
        period = rng.uniform(*settings.asteroid_drift_period_range) if drift else None
        layout.append((f"ast-{i + 1}", x, y, radius, drift, period))

    return layout


class Ship:
    """A player-controlled ship: a pymunk Body + Circle wrapped with game state."""

    def __init__(self, ship_id: str, position: tuple[float, float]) -> None:
        self.id = ship_id
        moment = pymunk.moment_for_circle(settings.ship_mass, 0, settings.ship_radius)
        self.body = pymunk.Body(settings.ship_mass, moment)
        self.body.position = position
        self.shape = pymunk.Circle(self.body, settings.ship_radius)
        self.shape.elasticity = settings.collision_elasticity
        self.shape.friction = settings.collision_friction

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
        mass = settings.asteroid_density * radius**2
        moment = pymunk.moment_for_circle(mass, 0, radius)
        self.body = pymunk.Body(mass, moment)
        self.body.position = position
        self.shape = pymunk.Circle(self.body, radius)
        self.shape.elasticity = settings.collision_elasticity
        self.shape.friction = settings.collision_friction

    def to_state(self) -> dict:
        return {
            "id": self.id,
            "x": self.body.position.x,
            "y": self.body.position.y,
            "rotation": self.body.angle,
            "vx": self.body.velocity.x,
            "vy": self.body.velocity.y,
        }
