import pytest

from app.entities import ASTEROID_DENSITY, Asteroid, Ship


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

    assert small.body.mass == ASTEROID_DENSITY * 10**2
    assert large.body.mass == ASTEROID_DENSITY * 40**2
    assert large.body.mass == pytest.approx(small.body.mass * 16)
