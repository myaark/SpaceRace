import pymunk
import pytest

from app.session import BELT_CENTER, INNER_FENCE_R, OUTER_FENCE_R, GameSession

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
