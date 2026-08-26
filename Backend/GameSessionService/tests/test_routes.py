from app.routes.game_session import router, session_manager


def test_router_registers_health_and_websocket_routes() -> None:
    paths = {route.path for route in router.routes}
    assert "/health" in paths
    assert "/ws/{room_id}" in paths


def test_session_manager_is_a_shared_singleton() -> None:
    from app.controllers.game_session import SessionManager

    assert isinstance(session_manager, SessionManager)
