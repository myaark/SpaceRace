import math

import pytest

from app.entities import Asteroid, Ship, generate_asteroid_layout
from app.game_settings import game_settings

CENTER = (-200.0, 1500.0)
INNER_R = 1420.0
OUTER_R = 1760.0
SHIP_SPAWNS = [(724.0, 318.0), (900.0, 500.0)]


def test_to_state_reflects_body_position_and_id() -> None:
    ship = Ship("ship-1", (10, -20))

    state = ship.to_state()

    assert state["id"] == "ship-1"
    assert state["x"] == 10
    assert state["y"] == -20
    assert state["rotation"] == 0
    assert state["vx"] == 0
    assert state["vy"] == 0


def test_ship_spawns_with_full_hp_and_alive() -> None:
    ship = Ship("ship-1", (0, 0))

    assert ship.max_hp == game_settings.ship_max_hp
    assert ship.hp == game_settings.ship_max_hp
    assert ship.alive is True


def test_ship_to_state_includes_hp_and_alive() -> None:
    ship = Ship("ship-1", (0, 0))
    ship.hp = 40
    ship.alive = False

    state = ship.to_state()

    assert state["hp"] == 40
    assert state["max_hp"] == game_settings.ship_max_hp
    assert state["alive"] is False


def test_asteroid_to_state_reflects_body_position_and_id() -> None:
    asteroid = Asteroid("ast-1", (10, -20), 30, "small")

    state = asteroid.to_state()

    assert state["id"] == "ast-1"
    assert state["x"] == 10
    assert state["y"] == -20
    assert state["rotation"] == 0
    assert state["vx"] == 0
    assert state["vy"] == 0


def test_asteroid_hp_and_max_hp_come_from_its_tier() -> None:
    asteroid = Asteroid("ast-1", (0, 0), 48.0, "large")

    assert asteroid.tier == "large"
    assert asteroid.max_hp == game_settings.asteroid_tiers["large"]["hp"]
    assert asteroid.hp == asteroid.max_hp


def test_asteroid_to_state_includes_hp_and_max_hp() -> None:
    asteroid = Asteroid("ast-1", (0, 0), 20.0, "small")
    asteroid.hp = 2

    state = asteroid.to_state()

    assert state["hp"] == 2
    assert state["max_hp"] == game_settings.asteroid_tiers["small"]["hp"]


def test_asteroid_mass_scales_with_radius_squared() -> None:
    small = Asteroid("ast-small", (0, 0), 10, "small")
    large = Asteroid("ast-large", (0, 0), 40, "large")

    assert small.body.mass == game_settings.asteroid_density * 10**2
    assert large.body.mass == game_settings.asteroid_density * 40**2
    assert large.body.mass == pytest.approx(small.body.mass * 16)


def test_generate_asteroid_layout_is_deterministic_for_a_seed() -> None:
    layout_a = generate_asteroid_layout(CENTER, INNER_R, OUTER_R, SHIP_SPAWNS, seed=42)
    layout_b = generate_asteroid_layout(CENTER, INNER_R, OUTER_R, SHIP_SPAWNS, seed=42)

    assert layout_a == layout_b


def test_generate_asteroid_layout_returns_requested_count() -> None:
    layout = generate_asteroid_layout(CENTER, INNER_R, OUTER_R, SHIP_SPAWNS, count=45)

    assert len(layout) == 45
    assert len({asteroid_id for asteroid_id, *_ in layout}) == 45


def test_generate_asteroid_layout_assigns_a_valid_tier_and_matching_radius() -> None:
    layout = generate_asteroid_layout(CENTER, INNER_R, OUTER_R, SHIP_SPAWNS)

    for _, _, _, r, tier, _, _ in layout:
        assert tier in game_settings.asteroid_tiers
        assert r == game_settings.asteroid_tiers[tier]["radius"]


def test_generate_asteroid_layout_stays_within_annulus() -> None:
    layout = generate_asteroid_layout(CENTER, INNER_R, OUTER_R, SHIP_SPAWNS)
    cx, cy = CENTER

    for _, x, y, r, _, _, _ in layout:
        distance = math.hypot(x - cx, y - cy)
        assert INNER_R + r - 1e-6 <= distance <= OUTER_R - r + 1e-6


def test_generate_asteroid_layout_avoids_overlap_and_every_ship_spawn_clearance() -> (
    None
):
    layout = generate_asteroid_layout(CENTER, INNER_R, OUTER_R, SHIP_SPAWNS)

    for i, (_, x, y, r, _, _, _) in enumerate(layout):
        for sx, sy in SHIP_SPAWNS:
            assert math.hypot(x - sx, y - sy) >= r + 150.0 - 1e-6
        for _, ox, oy, oradius, _, _, _ in layout[i + 1 :]:
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
