import pymunk
import pytest

from app.game_settings import game_settings
from app.session import (
    BELT_CENTER,
    INNER_FENCE_R,
    OUTER_FENCE_R,
    SPAWN_OFFSET,
    GameSession,
)

TICK_DT = 1 / 20


def _run_head_on_collision(
    asteroid_id: str, approach_speed: float, ticks: int = 5
) -> float:
    """Places the ship on contact with the named asteroid, moving straight at
    it, steps a few ticks, and returns the ship's resulting speed change."""
    session = GameSession("test-room")
    target = session.asteroids[asteroid_id]
    target.drift = False  # isolate the collision from the drift force

    approach_dir = pymunk.Vec2d(1, 0)
    contact_distance = (
        target.radius + game_settings.ship_radius - 1
    )  # slight overlap to force contact on tick 1
    session.ship.body.position = target.body.position - approach_dir * contact_distance
    session.ship.body.velocity = approach_dir * approach_speed
    initial_vx = session.ship.body.velocity.x

    for _ in range(ticks):
        session.step(TICK_DT)

    return abs(session.ship.body.velocity.x - initial_vx)


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

    assert session.ship.body.velocity.length <= game_settings.ship_max_speed + 1e-6


def test_asteroids_spawn_within_belt_annulus(session: GameSession) -> None:
    assert len(session.asteroids) == 45
    for asteroid in session.asteroids.values():
        distance = (asteroid.body.position - BELT_CENTER).length
        assert INNER_FENCE_R - 1e-6 <= distance <= OUTER_FENCE_R + 1e-6


def test_asteroids_do_not_overlap_each_other_or_the_ship(
    session: GameSession,
) -> None:
    bodies = [(a.body.position, a.radius) for a in session.asteroids.values()]
    bodies.append((session.ship.body.position, game_settings.ship_radius))

    for i, (pos_a, r_a) in enumerate(bodies):
        for pos_b, r_b in bodies[i + 1 :]:
            assert (pos_a - pos_b).length >= r_a + r_b - 1e-6


def test_asteroid_mass_scales_with_radius(session: GameSession) -> None:
    asteroids = sorted(session.asteroids.values(), key=lambda a: a.radius)
    small, large = asteroids[0], asteroids[-1]
    assert large.body.mass > small.body.mass
    assert large.body.mass == pytest.approx(
        small.body.mass * (large.radius**2 / small.radius**2)
    )


def test_heavier_asteroid_causes_larger_ship_velocity_change() -> None:
    """Elastic collision: a heavier asteroid reflects more of the ship's
    incoming velocity than a lighter one, given the same approach speed —
    "a large asteroid barely moves and deflects the ship hard, a small one
    is easily pushed aside and barely affects the ship's course" (design
    spec Goals)."""
    approach_speed = 80
    session = GameSession("test-room")
    asteroids = sorted(session.asteroids.values(), key=lambda a: a.radius)
    light_id, heavy_id = asteroids[0].id, asteroids[-1].id

    light_delta = _run_head_on_collision(light_id, approach_speed)
    heavy_delta = _run_head_on_collision(heavy_id, approach_speed)

    assert heavy_delta > light_delta


def test_drifting_asteroids_stay_within_belt_annulus() -> None:
    session = GameSession("test-room")

    for _ in range(2000):
        session.step(TICK_DT)

    for asteroid in session.asteroids.values():
        distance = (asteroid.body.position - BELT_CENTER).length
        assert INNER_FENCE_R - 1e-6 <= distance <= OUTER_FENCE_R + 1e-6


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


def test_ship_max_speed_change_is_reflected_live_per_tick(
    session: GameSession,
) -> None:
    """Live-tunable field: mutating game_settings.ship_max_speed should
    change the clamp applied on the very next tick of an already-constructed
    GameSession, proving the value is re-read per tick rather than baked in
    at construction time."""
    client = object()
    session.set_input(client, thrust=1, turn=0)
    original = game_settings.ship_max_speed
    try:
        game_settings.ship_max_speed = 10.0
        for _ in range(200):
            session.step(TICK_DT)
        assert session.ship.body.velocity.length <= game_settings.ship_max_speed + 1e-6
        assert session.ship.body.velocity.length < original
    finally:
        game_settings.ship_max_speed = original
