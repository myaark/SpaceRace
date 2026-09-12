import math
from dataclasses import dataclass

import pymunk

from app.entities import Ship
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


def spawn_bullet(bullet_id: str, owner_id: str, ship: Ship, elapsed_ms: float) -> Bullet:
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
