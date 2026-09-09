import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.routes.game_session import router, session_manager


def test_router_registers_health_and_websocket_routes() -> None:
    paths = {route.path for route in router.routes}
    assert "/health" in paths
    assert "/ws/{room_id}" in paths


def test_session_manager_is_a_shared_singleton() -> None:
    from app.controllers.game_session import SessionManager

    assert isinstance(session_manager, SessionManager)


def test_websocket_route_requires_player_id_query_param() -> None:
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws/room-1"):
        pass
