import pytest

from app.game_settings import GameSettings, game_settings


def test_defaults_match_original_constants() -> None:
    defaults = GameSettings()

    assert defaults.ship_mass == 1.0
    assert defaults.ship_radius == 20.0
    assert defaults.ship_thrust_force == 400.0
    assert defaults.ship_turn_rate == 3.0
    assert defaults.ship_max_speed == 90.0
    assert defaults.space_damping == 0.0003

    assert defaults.collision_elasticity == 0.8
    assert defaults.collision_friction == 0.3

    assert defaults.asteroid_density == 1.0 / 20.0**2
    assert defaults.asteroid_max_speed == 300.0
    assert defaults.asteroid_drift_force == 5.0

    assert defaults.asteroid_count == 45
    assert defaults.asteroid_layout_seed == 42
    assert defaults.asteroid_drift_chance == 0.5
    assert defaults.asteroid_drift_period_range == (15000.0, 30000.0)
    assert defaults.asteroid_min_gap == 10.0
    assert defaults.asteroid_ship_clearance == 150.0
    assert defaults.asteroid_placement_attempts == 500


def test_settings_singleton_is_mutable() -> None:
    original = game_settings.ship_thrust_force
    try:
        game_settings.ship_thrust_force = 999.0
        assert game_settings.ship_thrust_force == 999.0
    finally:
        game_settings.ship_thrust_force = original


def test_defaults_include_belt_geometry() -> None:
    defaults = GameSettings()

    assert defaults.belt_center == (-200.0, 1500.0)
    assert defaults.spawn_offset == (924.0, -1182.0)
    assert defaults.inner_fence_r == 1420.0
    assert defaults.outer_fence_r == 1760.0


def test_defaults_include_room_capacity() -> None:
    defaults = GameSettings()

    assert defaults.max_players == 10


def test_spawn_points_point_zero_matches_spawn_offset_bit_exact() -> None:
    defaults = GameSettings()

    assert defaults.spawn_points[0] == defaults.spawn_offset


def test_spawn_points_point_zero_matches_spawn_offset() -> None:
    defaults = GameSettings()

    assert defaults.spawn_points[0] == pytest.approx(defaults.spawn_offset)


def test_spawn_points_are_evenly_distributed_and_unique() -> None:
    defaults = GameSettings()

    assert len(defaults.spawn_points) == defaults.max_players
    assert len({tuple(round(v, 6) for v in p) for p in defaults.spawn_points}) == len(
        defaults.spawn_points
    )


def test_defaults_include_combat_tunables() -> None:
    defaults = GameSettings()

    assert defaults.bullet_speed == 500.0
    assert defaults.bullet_lifetime_ms == 2000.0
    assert defaults.bullet_damage_to_asteroid == 10
    assert defaults.bullet_damage_to_ship == 10
    assert defaults.ship_max_hp == 100

    assert defaults.asteroid_tiers == {
        "large": {"radius": 48.0, "hp": 30},
        "medium": {"radius": 34.0, "hp": 15},
        "small": {"radius": 20.0, "hp": 5},
    }
    assert defaults.asteroid_fragment_impulse == 80.0

    assert defaults.ram_damage_by_tier == {"large": 20, "medium": 12, "small": 5}
    assert defaults.ram_cooldown_ms == 500.0
