import math
import random
from dataclasses import dataclass

import pymunk

from app.entities import Asteroid, Ship
from app.game_settings import game_settings


@dataclass
class Bullet:
    """A fired shot: no pymunk body — bullets are simple, fast, short-lived,
    and must not bounce (spec §3)."""

    id: str
    owner_id: str
    x: float
    y: float
    vx: float
    vy: float
    prev_x: float
    prev_y: float
    spawned_at_ms: float


def spawn_bullet(
    bullet_id: str, owner_id: str, ship: Ship, elapsed_ms: float
) -> Bullet:
    angle = ship.body.angle
    direction = pymunk.Vec2d(math.cos(angle), math.sin(angle))
    nose = ship.body.position + direction * game_settings.ship_radius
    velocity = ship.body.velocity + direction * game_settings.bullet_speed
    return Bullet(
        id=bullet_id,
        owner_id=owner_id,
        x=nose.x,
        y=nose.y,
        vx=velocity.x,
        vy=velocity.y,
        prev_x=nose.x,
        prev_y=nose.y,
        spawned_at_ms=elapsed_ms,
    )


def advance_bullet(bullet: Bullet, dt: float) -> None:
    bullet.prev_x, bullet.prev_y = bullet.x, bullet.y
    bullet.x += bullet.vx * dt
    bullet.y += bullet.vy * dt


def is_bullet_expired(
    bullet: Bullet,
    elapsed_ms: float,
    belt_center: tuple[float, float],
    outer_fence_r: float,
) -> bool:
    age = elapsed_ms - bullet.spawned_at_ms
    if age >= game_settings.bullet_lifetime_ms:
        return True
    distance = math.hypot(bullet.x - belt_center[0], bullet.y - belt_center[1])
    return distance > outer_fence_r


def bullet_to_state(bullet: Bullet) -> dict:
    return {
        "id": bullet.id,
        "x": bullet.x,
        "y": bullet.y,
        "rotation": math.atan2(bullet.vy, bullet.vx),
    }


def segment_hits_circle(
    start: tuple[float, float],
    end: tuple[float, float],
    center: tuple[float, float],
    radius: float,
) -> bool:
    """True if the segment start->end passes within `radius` of `center` at
    any point along it — used for swept bullet-vs-target collision so a fast
    bullet can't tunnel through a target between ticks (spec §3)."""
    sx, sy = start
    ex, ey = end
    cx, cy = center
    dx, dy = ex - sx, ey - sy
    fx, fy = sx - cx, sy - cy

    a = dx * dx + dy * dy
    if a == 0:
        return math.hypot(fx, fy) <= radius

    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius
    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return False

    sqrt_disc = math.sqrt(discriminant)
    t1 = (-b - sqrt_disc) / (2 * a)
    t2 = (-b + sqrt_disc) / (2 * a)
    return (0 <= t1 <= 1) or (0 <= t2 <= 1) or (t1 < 0 and t2 > 1)


_CHILD_TIER = {"large": "medium", "medium": "small"}


def fragment_asteroid(parent: Asteroid, rng: random.Random) -> list[Asteroid]:
    """Splits a destroyed large/medium asteroid into 2 children one tier
    smaller, given a small outward impulse in opposite directions so they
    don't immediately overlap (spec §4). Returns [] for a small-tier parent
    (destroyed outright, no children)."""
    child_tier = _CHILD_TIER.get(parent.tier)
    if child_tier is None:
        return []

    child_radius = game_settings.asteroid_tiers[child_tier]["radius"]
    base_angle = rng.uniform(0, 2 * math.pi)
    children = []
    for i in range(2):
        angle = base_angle + i * math.pi
        direction = pymunk.Vec2d(math.cos(angle), math.sin(angle))
        drift = rng.random() < game_settings.asteroid_drift_chance
        period = (
            rng.uniform(*game_settings.asteroid_drift_period_range) if drift else None
        )
        child = Asteroid(
            f"{parent.id}-frag{i}",
            (parent.body.position.x, parent.body.position.y),
            child_radius,
            child_tier,
            drift,
            period,
        )
        child.body.velocity = direction * game_settings.asteroid_fragment_impulse
        children.append(child)
    return children
