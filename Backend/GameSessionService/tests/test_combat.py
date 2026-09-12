import math

import pytest

from app.combat import Bullet, advance_bullet, bullet_to_state, is_bullet_expired, spawn_bullet
from app.entities import Ship
from app.game_settings import game_settings


def test_spawn_bullet_starts_at_ship_nose_along_facing_direction() -> None:
    ship = Ship("p1", (0, 0))
    ship.body.angle = 0.0  # facing +x

    bullet = spawn_bullet("blt-1", "p1", ship, elapsed_ms=1000.0)

    assert bullet.id == "blt-1"
    assert bullet.owner_id == "p1"
    assert bullet.x == pytest.approx(game_settings.ship_radius)
    assert bullet.y == pytest.approx(0.0)
    assert bullet.spawned_at_ms == 1000.0


def test_spawn_bullet_velocity_adds_ship_velocity_and_muzzle_speed() -> None:
    ship = Ship("p1", (0, 0))
    ship.body.angle = 0.0
    ship.body.velocity = (10.0, 0.0)

    bullet = spawn_bullet("blt-1", "p1", ship, elapsed_ms=0.0)

    assert bullet.vx == pytest.approx(10.0 + game_settings.bullet_speed)
    assert bullet.vy == pytest.approx(0.0)


def test_spawn_bullet_faces_ship_rotation() -> None:
    ship = Ship("p1", (0, 0))
    ship.body.angle = math.pi / 2  # facing +y

    bullet = spawn_bullet("blt-1", "p1", ship, elapsed_ms=0.0)

    assert bullet.x == pytest.approx(0.0, abs=1e-9)
    assert bullet.y == pytest.approx(game_settings.ship_radius)
    assert bullet.vy == pytest.approx(game_settings.bullet_speed)


def test_advance_bullet_moves_by_velocity_times_dt_and_tracks_previous_position() -> (
    None
):
    bullet = Bullet(
        id="blt-1", owner_id="p1", x=0.0, y=0.0, vx=100.0, vy=50.0,
        prev_x=0.0, prev_y=0.0, spawned_at_ms=0.0,
    )

    advance_bullet(bullet, dt=0.1)

    assert bullet.prev_x == pytest.approx(0.0)
    assert bullet.prev_y == pytest.approx(0.0)
    assert bullet.x == pytest.approx(10.0)
    assert bullet.y == pytest.approx(5.0)


def test_bullet_expires_after_lifetime() -> None:
    bullet = Bullet(
        id="blt-1", owner_id="p1", x=0.0, y=0.0, vx=0.0, vy=0.0,
        prev_x=0.0, prev_y=0.0, spawned_at_ms=1000.0,
    )

    not_yet = is_bullet_expired(
        bullet,
        elapsed_ms=1000.0 + game_settings.bullet_lifetime_ms - 1,
        belt_center=(0.0, 0.0),
        outer_fence_r=10000.0,
    )
    expired = is_bullet_expired(
        bullet,
        elapsed_ms=1000.0 + game_settings.bullet_lifetime_ms,
        belt_center=(0.0, 0.0),
        outer_fence_r=10000.0,
    )

    assert not_yet is False
    assert expired is True


def test_bullet_expires_outside_outer_fence() -> None:
    bullet = Bullet(
        id="blt-1", owner_id="p1", x=500.0, y=0.0, vx=0.0, vy=0.0,
        prev_x=500.0, prev_y=0.0, spawned_at_ms=0.0,
    )

    assert is_bullet_expired(
        bullet, elapsed_ms=1.0, belt_center=(0.0, 0.0), outer_fence_r=400.0
    ) is True
    assert is_bullet_expired(
        bullet, elapsed_ms=1.0, belt_center=(0.0, 0.0), outer_fence_r=600.0
    ) is False


def test_bullet_to_state_includes_rotation_from_velocity() -> None:
    bullet = Bullet(
        id="blt-1", owner_id="p1", x=3.0, y=4.0, vx=1.0, vy=1.0,
        prev_x=0.0, prev_y=0.0, spawned_at_ms=0.0,
    )

    state = bullet_to_state(bullet)

    assert state == {
        "id": "blt-1",
        "x": 3.0,
        "y": 4.0,
        "rotation": pytest.approx(math.pi / 4),
    }
