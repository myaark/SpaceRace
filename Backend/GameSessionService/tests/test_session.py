import asyncio
import logging
import math

import pymunk
import pytest

from app.game_settings import game_settings
from app.models.messages import InitMessage, StateMessage
from app.session import GameSession

BELT_CENTER = pymunk.Vec2d(*game_settings.belt_center)
INNER_FENCE_R = game_settings.inner_fence_r
OUTER_FENCE_R = game_settings.outer_fence_r
SPAWN_POINT_0 = pymunk.Vec2d(*game_settings.spawn_points[0])

TICK_DT = 1 / 20


class _DummyWebSocket:
    """Stand-in for fastapi.WebSocket in tests that don't exercise broadcast."""


def _run_head_on_collision(
    asteroid_id: str, approach_speed: float, ticks: int = 5
) -> float:
    """Places a ship on contact with the named asteroid, moving straight at
    it, steps a few ticks, and returns the ship's resulting speed change."""
    session = GameSession("test-room")
    session.register("p1", _DummyWebSocket())
    ship = session.ships["p1"]
    target = session.asteroids[asteroid_id]
    target.drift = False  # isolate the collision from the drift force

    approach_dir = pymunk.Vec2d(1, 0)
    contact_distance = (
        target.radius + game_settings.ship_radius - 1
    )  # slight overlap to force contact on tick 1
    ship.body.position = target.body.position - approach_dir * contact_distance
    ship.body.velocity = approach_dir * approach_speed
    initial_vx = ship.body.velocity.x

    for _ in range(ticks):
        session.step(TICK_DT)

    return abs(ship.body.velocity.x - initial_vx)


@pytest.fixture
def session() -> GameSession:
    return GameSession("test-room")


@pytest.fixture
def ship(session: GameSession):
    session.register("p1", _DummyWebSocket())
    return session.ships["p1"]


def test_ship_spawns_within_belt(session: GameSession, ship) -> None:
    distance = (ship.body.position - BELT_CENTER).length
    assert INNER_FENCE_R <= distance <= OUTER_FENCE_R


def test_boundary_clamp_keeps_ship_pushed_outward_within_belt(
    session: GameSession, ship
) -> None:
    outward_dir = pymunk.Vec2d(0, -1)
    ship.body.position = BELT_CENTER + outward_dir * OUTER_FENCE_R
    ship.body.velocity = outward_dir * 5000  # far exceeds the fence radially

    session.step(TICK_DT)

    distance = (ship.body.position - BELT_CENTER).length
    assert INNER_FENCE_R <= distance <= OUTER_FENCE_R + 1e-6
    radial_component = ship.body.velocity.dot(outward_dir)
    assert radial_component <= 1e-6


def test_boundary_clamp_keeps_ship_pushed_inward_within_belt(
    session: GameSession, ship
) -> None:
    inward_dir = pymunk.Vec2d(0, -1)
    ship.body.position = BELT_CENTER + inward_dir * INNER_FENCE_R
    ship.body.velocity = -inward_dir * 5000  # heading toward the center

    session.step(TICK_DT)

    distance = (ship.body.position - BELT_CENTER).length
    assert INNER_FENCE_R - 1e-6 <= distance <= OUTER_FENCE_R


def test_boundary_clamp_does_not_kill_velocity_heading_back_into_belt(
    session: GameSession, ship
) -> None:
    outward_dir = pymunk.Vec2d(0, -1)
    ship.body.position = BELT_CENTER + outward_dir * (OUTER_FENCE_R + 50)
    ship.body.velocity = -outward_dir * 500  # already heading back inward

    session.step(TICK_DT)

    radial_component = ship.body.velocity.dot(outward_dir)
    assert radial_component < -50


def test_thrust_input_applies_velocity(session: GameSession, ship) -> None:
    assert ship.body.velocity.length == 0

    session.set_input("p1", thrust=1, turn=0)
    session.step(TICK_DT)

    assert ship.body.velocity.length > 0


def test_no_input_leaves_ship_at_rest(session: GameSession, ship) -> None:
    session.step(TICK_DT)

    assert ship.body.velocity.length == 0


def test_turn_input_sets_angular_velocity(session: GameSession, ship) -> None:
    session.set_input("p1", thrust=0, turn=1)
    session.step(TICK_DT)

    assert ship.body.angular_velocity > 0


def test_ship_spawns_at_frontend_design_point(session: GameSession, ship) -> None:
    expected = BELT_CENTER + SPAWN_POINT_0

    assert ship.body.position.x == pytest.approx(expected.x)
    assert ship.body.position.y == pytest.approx(expected.y)


def test_second_ship_spawns_at_a_different_point_than_the_first(
    session: GameSession,
) -> None:
    session.register("p1", _DummyWebSocket())
    session.register("p2", _DummyWebSocket())

    assert session.ships["p1"].body.position != session.ships["p2"].body.position


def test_spawn_index_is_reused_after_a_player_leaves(session: GameSession) -> None:
    session.register("p1", _DummyWebSocket())
    first_position = session.ships["p1"].body.position
    session.unregister("p1")

    session.register("p2", _DummyWebSocket())

    assert session.ships["p2"].body.position == first_position


def test_speed_is_clamped_to_max(session: GameSession, ship) -> None:
    session.set_input("p1", thrust=1, turn=0)

    for _ in range(200):
        session.step(TICK_DT)

    assert ship.body.velocity.length <= game_settings.ship_max_speed + 1e-6


def test_asteroids_spawn_within_belt_annulus(session: GameSession) -> None:
    assert len(session.asteroids) == 45
    for asteroid in session.asteroids.values():
        distance = (asteroid.body.position - BELT_CENTER).length
        assert INNER_FENCE_R - 1e-6 <= distance <= OUTER_FENCE_R + 1e-6


def test_asteroids_do_not_overlap_each_other_or_a_spawned_ship(
    session: GameSession, ship
) -> None:
    bodies = [(a.body.position, a.radius) for a in session.asteroids.values()]
    bodies.append((ship.body.position, game_settings.ship_radius))

    for i, (pos_a, r_a) in enumerate(bodies):
        for pos_b, r_b in bodies[i + 1 :]:
            assert (pos_a - pos_b).length >= r_a + r_b - 1e-6


def test_asteroids_clear_every_real_spawn_point(session: GameSession) -> None:
    """The layout is generated once at construction against the full
    game_settings.spawn_points list, so clearance must hold for all 10 real
    spawn points — not just the slots that happen to be occupied."""
    for i in range(game_settings.max_players):
        session.register(f"p{i}", _DummyWebSocket())

    spawn_positions = [
        BELT_CENTER + pymunk.Vec2d(*p) for p in game_settings.spawn_points
    ]
    assert len(spawn_positions) == 10
    assert len(session.ships) == len(spawn_positions)

    for asteroid in session.asteroids.values():
        for spawn in spawn_positions:
            distance = (asteroid.body.position - spawn).length
            assert (
                distance
                >= asteroid.radius + game_settings.asteroid_ship_clearance - 1e-6
            )


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
    session: GameSession, ship
) -> None:
    session.set_input("p1", thrust=1, turn=0)
    for _ in range(20):
        session.step(TICK_DT)
    peak_speed = ship.body.velocity.length
    assert peak_speed > 0

    session.set_input("p1", thrust=0, turn=0)
    for _ in range(6):
        session.step(TICK_DT)

    assert ship.body.velocity.length <= peak_speed * 0.1


def test_ship_max_speed_change_is_reflected_live_per_tick(
    session: GameSession, ship
) -> None:
    """Live-tunable field: mutating game_settings.ship_max_speed should
    change the clamp applied on the very next tick of an already-constructed
    GameSession, proving the value is re-read per tick rather than baked in
    at construction time."""
    session.set_input("p1", thrust=1, turn=0)
    original = game_settings.ship_max_speed
    try:
        game_settings.ship_max_speed = 10.0
        for _ in range(200):
            session.step(TICK_DT)
        assert ship.body.velocity.length <= game_settings.ship_max_speed + 1e-6
        assert ship.body.velocity.length < original
    finally:
        game_settings.ship_max_speed = original


def test_broadcast_uses_injected_logger_on_dropped_client(caplog) -> None:
    class _FailingWebSocket:
        async def send_json(self, data: dict) -> None:
            raise RuntimeError("send failed")

    custom_logger = logging.getLogger("test-custom-logger")
    session = GameSession("test-room", logger=custom_logger)
    session.register("p1", _FailingWebSocket())

    with caplog.at_level(logging.INFO, logger="test-custom-logger"):
        asyncio.run(session.broadcast())

    assert len(caplog.records) == 1
    assert caplog.records[0].name == "test-custom-logger"
    assert "test-room" in caplog.records[0].getMessage()
    assert "p1" not in session.ships  # dropped client is unregistered


def test_to_init_message_includes_belt_geometry_and_asteroids(
    session: GameSession,
) -> None:
    init = session.to_init_message()

    assert isinstance(init, InitMessage)
    assert init.belt_center_x == pytest.approx(BELT_CENTER.x)
    assert init.belt_center_y == pytest.approx(BELT_CENTER.y)
    assert init.spawn_x == pytest.approx((BELT_CENTER + SPAWN_POINT_0).x)
    assert init.spawn_y == pytest.approx((BELT_CENTER + SPAWN_POINT_0).y)
    assert init.inner_r == INNER_FENCE_R
    assert init.outer_r == OUTER_FENCE_R
    assert len(init.asteroids) == len(session.asteroids)


def test_to_broadcast_message_returns_typed_state_for_every_ship(
    session: GameSession,
) -> None:
    session.register("p1", _DummyWebSocket())
    session.register("p2", _DummyWebSocket())

    state = session.to_broadcast_message()

    assert isinstance(state, StateMessage)
    assert state.tick == session.tick_count
    assert {s.id for s in state.ships} == {"p1", "p2"}
    assert len(state.asteroids) == len(session.asteroids)


def test_is_full_true_at_max_players(session: GameSession) -> None:
    for i in range(game_settings.max_players):
        session.register(f"p{i}", _DummyWebSocket())

    assert session.is_full()


def test_has_player_reflects_registration(session: GameSession) -> None:
    assert not session.has_player("p1")
    session.register("p1", _DummyWebSocket())
    assert session.has_player("p1")
    session.unregister("p1")
    assert not session.has_player("p1")


def test_unregister_removes_ship_body_from_physics_space(
    session: GameSession,
) -> None:
    session.register("p1", _DummyWebSocket())
    ship = session.ships["p1"]

    session.unregister("p1")

    assert ship.body not in session.space.bodies
    assert ship.shape not in session.space.shapes


def test_each_ship_applies_its_own_independent_input(session: GameSession) -> None:
    session.register("p1", _DummyWebSocket())
    session.register("p2", _DummyWebSocket())

    session.set_input("p1", thrust=1, turn=0)
    session.set_input("p2", thrust=0, turn=0)
    session.step(TICK_DT)

    assert session.ships["p1"].body.velocity.length > 0
    assert session.ships["p2"].body.velocity.length == 0


def test_fire_input_spawns_a_bullet(session: GameSession, ship) -> None:
    session.set_input("p1", thrust=0, turn=0, fire=True)

    session.step(TICK_DT)

    assert len(session.bullets) == 1


def test_no_fire_input_spawns_no_bullet(session: GameSession, ship) -> None:
    session.set_input("p1", thrust=0, turn=0)

    session.step(TICK_DT)

    assert len(session.bullets) == 0


def test_held_fire_input_spawns_one_bullet_per_tick(session: GameSession, ship) -> None:
    session.set_input("p1", thrust=0, turn=0, fire=True)

    session.step(TICK_DT)
    session.step(TICK_DT)
    session.step(TICK_DT)

    assert len(session.bullets) == 3


def test_dead_ship_does_not_spawn_bullets(session: GameSession, ship) -> None:
    ship.alive = False
    session.set_input("p1", thrust=0, turn=0, fire=True)

    session.step(TICK_DT)

    assert len(session.bullets) == 0


def test_bullet_spawns_at_ships_position_facing_direction(
    session: GameSession, ship
) -> None:
    ship.body.angle = 0.0
    origin = ship.body.position

    session.set_input("p1", thrust=0, turn=0, fire=True)
    session.step(TICK_DT)

    bullet = next(iter(session.bullets.values()))
    assert bullet.owner_id == "p1"
    # A bullet advances in the same tick it spawns (spawn -> advance/expire
    # is the tick order), so its position after step() already includes one
    # tick's worth of travel along the facing direction.
    assert bullet.x == pytest.approx(
        origin.x + game_settings.ship_radius + game_settings.bullet_speed * TICK_DT
    )
    assert bullet.y == pytest.approx(origin.y)


def test_dead_ship_ignores_thrust_and_turn_input(session: GameSession, ship) -> None:
    ship.alive = False
    session.set_input("p1", thrust=1, turn=1)

    session.step(TICK_DT)

    assert ship.body.velocity.length == 0
    assert ship.body.angular_velocity == 0


def test_bullet_advances_each_tick(session: GameSession, ship) -> None:
    session.set_input("p1", thrust=0, turn=0, fire=True)
    session.step(TICK_DT)
    bullet = next(iter(session.bullets.values()))
    first_x = bullet.x

    session.step(TICK_DT)

    assert session.bullets[bullet.id].x != first_x


def test_bullet_expires_after_lifetime(session: GameSession, ship) -> None:
    session.set_input("p1", thrust=0, turn=0, fire=True)
    session.step(TICK_DT)
    bullet_id = next(iter(session.bullets))

    ticks_to_expire = int(game_settings.bullet_lifetime_ms / (TICK_DT * 1000)) + 2
    for _ in range(ticks_to_expire):
        session.step(TICK_DT)

    assert bullet_id not in session.bullets


def test_bullet_hits_enemy_ship_and_deals_damage(session: GameSession) -> None:
    session.register("p1", _DummyWebSocket())
    session.register("p2", _DummyWebSocket())
    shooter, target = session.ships["p1"], session.ships["p2"]
    shooter.body.angle = 0.0
    target.body.position = shooter.body.position + pymunk.Vec2d(
        game_settings.ship_radius + 5, 0
    )
    starting_hp = target.hp

    session.set_input("p1", thrust=0, turn=0, fire=True)
    session.step(TICK_DT)

    assert target.hp == starting_hp - game_settings.bullet_damage_to_ship
    assert len(session.bullets) == 0  # consumed on hit, no piercing


def test_bullet_cannot_damage_its_own_owner(session: GameSession, ship) -> None:
    starting_hp = ship.hp

    session.set_input("p1", thrust=0, turn=0, fire=True)
    for _ in range(5):
        session.step(TICK_DT)

    assert ship.hp == starting_hp


def test_bullet_hits_asteroid_and_deals_damage(session: GameSession, ship) -> None:
    asteroid = next(iter(session.asteroids.values()))
    ship.body.position = asteroid.body.position - pymunk.Vec2d(
        asteroid.radius + game_settings.ship_radius + 5, 0
    )
    ship.body.angle = 0.0
    starting_hp = asteroid.hp

    session.set_input("p1", thrust=0, turn=0, fire=True)
    session.step(TICK_DT)

    assert asteroid.hp == starting_hp - game_settings.bullet_damage_to_asteroid
    assert len(session.bullets) == 0


def test_bullet_miss_leaves_hp_and_bullet_unchanged(session: GameSession, ship) -> None:
    ship.body.angle = math.pi  # facing away from every asteroid/ship

    session.set_input("p1", thrust=0, turn=0, fire=True)
    session.step(TICK_DT)

    assert len(session.bullets) == 1


def test_ship_dies_when_hp_reaches_zero_from_bullets(session: GameSession) -> None:
    session.register("p1", _DummyWebSocket())
    session.register("p2", _DummyWebSocket())
    shooter, target = session.ships["p1"], session.ships["p2"]
    shooter.body.angle = 0.0
    target.body.position = shooter.body.position + pymunk.Vec2d(
        game_settings.ship_radius + 5, 0
    )
    target.hp = game_settings.bullet_damage_to_ship  # exactly lethal

    session.set_input("p1", thrust=0, turn=0, fire=True)
    session.step(TICK_DT)

    assert target.hp <= 0
    assert target.alive is False


def test_bullet_does_not_damage_an_already_dead_ship(session: GameSession) -> None:
    session.register("p1", _DummyWebSocket())
    session.register("p2", _DummyWebSocket())
    shooter, target = session.ships["p1"], session.ships["p2"]
    shooter.body.angle = 0.0
    target.body.position = shooter.body.position + pymunk.Vec2d(
        game_settings.ship_radius + 5, 0
    )
    target.alive = False
    target.hp = -999

    session.set_input("p1", thrust=0, turn=0, fire=True)
    session.step(TICK_DT)

    assert target.hp == -999  # untouched, no-op on already-dead


def test_asteroid_fragments_into_two_children_when_hp_reaches_zero(
    session: GameSession,
) -> None:
    large = next(a for a in session.asteroids.values() if a.tier == "large")
    large.hp = 1
    large_id = large.id
    count_before = len(session.asteroids)

    # Force a bullet hit on it: place a ship facing it, one hp of damage.
    session.register("p1", _DummyWebSocket())
    ship = session.ships["p1"]
    ship.body.position = large.body.position - pymunk.Vec2d(
        large.radius + game_settings.ship_radius + 5, 0
    )
    ship.body.angle = 0.0
    session.set_input("p1", thrust=0, turn=0, fire=True)

    session.step(TICK_DT)

    assert large_id not in session.asteroids
    assert len(session.asteroids) == count_before + 1  # -1 parent, +2 children
    children = [
        a for a in session.asteroids.values() if a.id.startswith(f"{large_id}-frag")
    ]
    assert len(children) == 2
    assert all(c.tier == "medium" for c in children)
    assert large.body not in session.space.bodies


def test_small_asteroid_destroyed_outright_with_no_children(
    session: GameSession,
) -> None:
    small = next(a for a in session.asteroids.values() if a.tier == "small")
    small.hp = 1
    small_id = small.id
    count_before = len(session.asteroids)

    session.register("p1", _DummyWebSocket())
    ship = session.ships["p1"]
    ship.body.position = small.body.position - pymunk.Vec2d(
        small.radius + game_settings.ship_radius + 5, 0
    )
    ship.body.angle = 0.0
    session.set_input("p1", thrust=0, turn=0, fire=True)

    session.step(TICK_DT)

    assert small_id not in session.asteroids
    assert len(session.asteroids) == count_before - 1


def test_ram_damage_applies_on_ship_asteroid_contact(session: GameSession) -> None:
    asteroid = next(a for a in session.asteroids.values() if a.tier == "large")
    asteroid.drift = False
    session.register("p1", _DummyWebSocket())
    ship = session.ships["p1"]
    approach_dir = pymunk.Vec2d(1, 0)
    contact_distance = asteroid.radius + game_settings.ship_radius - 1
    ship.body.position = asteroid.body.position - approach_dir * contact_distance
    starting_hp = ship.hp

    session.step(TICK_DT)

    assert ship.hp == starting_hp - game_settings.ram_damage_by_tier["large"]


def test_ram_damage_cooldown_prevents_re_damage_every_tick(
    session: GameSession,
) -> None:
    asteroid = next(a for a in session.asteroids.values() if a.tier == "large")
    asteroid.drift = False
    session.register("p1", _DummyWebSocket())
    ship = session.ships["p1"]
    approach_dir = pymunk.Vec2d(1, 0)
    contact_distance = asteroid.radius + game_settings.ship_radius - 1
    ship.body.position = asteroid.body.position - approach_dir * contact_distance
    ship.body.velocity = (0, 0)

    ticks_within_cooldown = max(
        1, int(game_settings.ram_cooldown_ms / (TICK_DT * 1000)) - 1
    )
    for _ in range(ticks_within_cooldown):
        session.step(TICK_DT)
        ship.body.position = asteroid.body.position - approach_dir * contact_distance

    damage_taken = ship.max_hp - ship.hp
    assert damage_taken == game_settings.ram_damage_by_tier["large"]


def test_to_broadcast_message_includes_bullets_and_asteroid_diffs(
    session: GameSession,
) -> None:
    session.register("p1", _DummyWebSocket())
    session.set_input("p1", thrust=0, turn=0, fire=True)
    session.step(TICK_DT)

    state = session.to_broadcast_message()

    assert len(state.bullets) == len(session.bullets)
    assert isinstance(state.asteroids_spawned, list)
    assert isinstance(state.asteroids_removed, list)
    for ship_state in state.ships:
        assert hasattr(ship_state, "hp")
        assert hasattr(ship_state, "alive")
    for asteroid_state in state.asteroids:
        assert hasattr(asteroid_state, "hp")
