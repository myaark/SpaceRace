import pymunk
import pytest

from app.session import (
    BELT_CENTER,
    INNER_FENCE_R,
    OUTER_FENCE_R,
    SHIP_MAX_SPEED,
    SPAWN_OFFSET,
    GameSession,
)

TICK_DT = 1 / 20


@pytest.fixture
def session() -> GameSession:
    return GameSession("test-room")


def test_ship_spawns_within_belt(session: GameSession) -> None:
    distance = (session.ship.body.position - BELT_CENTER).length
    assert INNER_FENCE_R <= distance <= OUTER_FENCE_R


def test_boundary_clamp_keeps_ship_pushed_outward_within_belt(
    session: GameSession,
) -> None:
    outward_dir = pymunk.Vec2d(0, -1)
    session.ship.body.position = BELT_CENTER + outward_dir * OUTER_FENCE_R
    session.ship.body.velocity = outward_dir * 5000  # far exceeds the fence radially

    session.step(TICK_DT)

    distance = (session.ship.body.position - BELT_CENTER).length
    assert INNER_FENCE_R <= distance <= OUTER_FENCE_R + 1e-6
    # radial component of velocity should have been zeroed out
    radial_component = session.ship.body.velocity.dot(outward_dir)
    assert radial_component <= 1e-6


def test_boundary_clamp_keeps_ship_pushed_inward_within_belt(
    session: GameSession,
) -> None:
    inward_dir = pymunk.Vec2d(0, -1)
    session.ship.body.position = BELT_CENTER + inward_dir * INNER_FENCE_R
    session.ship.body.velocity = -inward_dir * 5000  # heading toward the center

    session.step(TICK_DT)

    distance = (session.ship.body.position - BELT_CENTER).length
    assert INNER_FENCE_R - 1e-6 <= distance <= OUTER_FENCE_R


def test_boundary_clamp_does_not_kill_velocity_heading_back_into_belt(
    session: GameSession,
) -> None:
    outward_dir = pymunk.Vec2d(0, -1)
    session.ship.body.position = BELT_CENTER + outward_dir * (OUTER_FENCE_R + 50)
    session.ship.body.velocity = -outward_dir * 500  # already heading back inward

    session.step(TICK_DT)

    # the inward radial component must survive the clamp (only ambient
    # damping should shrink it) instead of being zeroed by the fence
    radial_component = session.ship.body.velocity.dot(outward_dir)
    assert radial_component < -50


def test_thrust_input_applies_velocity(session: GameSession) -> None:
    client = object()
    assert session.ship.body.velocity.length == 0

    session.set_input(client, thrust=1, turn=0)
    session.step(TICK_DT)

    assert session.ship.body.velocity.length > 0


def test_no_input_leaves_ship_at_rest(session: GameSession) -> None:
    session.step(TICK_DT)

    assert session.ship.body.velocity.length == 0


def test_turn_input_sets_angular_velocity(session: GameSession) -> None:
    client = object()

    session.set_input(client, thrust=0, turn=1)
    session.step(TICK_DT)

    assert session.ship.body.angular_velocity > 0


def test_ship_spawns_at_frontend_design_point(session: GameSession) -> None:
    expected = BELT_CENTER + SPAWN_OFFSET

    assert session.ship.body.position.x == pytest.approx(expected.x)
    assert session.ship.body.position.y == pytest.approx(expected.y)


def test_speed_is_clamped_to_max(session: GameSession) -> None:
    client = object()
    session.set_input(client, thrust=1, turn=0)

    for _ in range(200):
        session.step(TICK_DT)

    assert session.ship.body.velocity.length <= SHIP_MAX_SPEED + 1e-6


def test_ship_decays_to_rest_quickly_after_thrust_released(
    session: GameSession,
) -> None:
    client = object()
    session.set_input(client, thrust=1, turn=0)
    for _ in range(20):
        session.step(TICK_DT)
    peak_speed = session.ship.body.velocity.length
    assert peak_speed > 0

    session.set_input(client, thrust=0, turn=0)
    for _ in range(6):
        session.step(TICK_DT)

    assert session.ship.body.velocity.length <= peak_speed * 0.1
