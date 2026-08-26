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
    assert defaults.asteroid_min_r == 26.0
    assert defaults.asteroid_max_r == 48.0
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
