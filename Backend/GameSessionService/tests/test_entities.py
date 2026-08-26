import math

import pytest

from app.entities import Asteroid, Ship, generate_asteroid_layout
from app.game_settings import game_settings

CENTER = (-200.0, 1500.0)
INNER_R = 1420.0
OUTER_R = 1760.0
SHIP_SPAWN = (724.0, 318.0)


def test_to_state_reflects_body_position_and_id() -> None:
    ship = Ship("ship-1", (10, -20))

    state = ship.to_state()

    assert state["id"] == "ship-1"
    assert state["x"] == 10
    assert state["y"] == -20
    assert state["rotation"] == 0
    assert state["vx"] == 0
    assert state["vy"] == 0


def test_asteroid_to_state_reflects_body_position_and_id() -> None:
    asteroid = Asteroid("ast-1", (10, -20), 30)

    state = asteroid.to_state()

    assert state["id"] == "ast-1"
    assert state["x"] == 10
    assert state["y"] == -20
    assert state["rotation"] == 0
    assert state["vx"] == 0
    assert state["vy"] == 0


def test_asteroid_mass_scales_with_radius_squared() -> None:
    small = Asteroid("ast-small", (0, 0), 10)
    large = Asteroid("ast-large", (0, 0), 40)

    assert small.body.mass == game_settings.asteroid_density * 10**2
    assert large.body.mass == game_settings.asteroid_density * 40**2
    assert large.body.mass == pytest.approx(small.body.mass * 16)


def test_generate_asteroid_layout_is_deterministic_for_a_seed() -> None:
    layout_a = generate_asteroid_layout(CENTER, INNER_R, OUTER_R, SHIP_SPAWN, seed=42)
    layout_b = generate_asteroid_layout(CENTER, INNER_R, OUTER_R, SHIP_SPAWN, seed=42)

    assert layout_a == layout_b


def test_generate_asteroid_layout_returns_requested_count() -> None:
    layout = generate_asteroid_layout(CENTER, INNER_R, OUTER_R, SHIP_SPAWN, count=45)

    assert len(layout) == 45
    assert len({asteroid_id for asteroid_id, *_ in layout}) == 45


def test_generate_asteroid_layout_stays_within_annulus() -> None:
    layout = generate_asteroid_layout(CENTER, INNER_R, OUTER_R, SHIP_SPAWN)
    cx, cy = CENTER

    for _, x, y, r, _, _ in layout:
        distance = math.hypot(x - cx, y - cy)
        assert INNER_R + r - 1e-6 <= distance <= OUTER_R - r + 1e-6


def test_generate_asteroid_layout_avoids_overlap_and_ship_clearance() -> None:
    layout = generate_asteroid_layout(CENTER, INNER_R, OUTER_R, SHIP_SPAWN)
    sx, sy = SHIP_SPAWN

    for i, (_, x, y, r, _, _) in enumerate(layout):
        assert math.hypot(x - sx, y - sy) >= r + 150.0 - 1e-6
        for _, ox, oy, oradius, _, _ in layout[i + 1 :]:
            assert math.hypot(x - ox, y - oy) >= r + oradius + 10.0 - 1e-6


def test_ship_radius_change_is_reflected_in_newly_constructed_ships() -> None:
    """Construction-time field: mutating game_settings.ship_radius should
    change the shape of a Ship built *after* the edit, proving the settings
    migration actually drives object construction and not just that the
    dataclass field itself happens to be assignable."""
    original = game_settings.ship_radius
    try:
        game_settings.ship_radius = 55.0
        ship = Ship("ship-radius-test", (0, 0))
        assert ship.shape.radius == 55.0
    finally:
        game_settings.ship_radius = original
