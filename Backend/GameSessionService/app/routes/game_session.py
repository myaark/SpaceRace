from fastapi import APIRouter, WebSocket
from pydantic import BaseModel

from app.config import settings
from app.controllers.game_session import SessionManager

router = APIRouter()
session_manager = SessionManager()


class HealthResponse(BaseModel):
    status: str
    service: str
    room_id: str


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        room_id=settings.room_id,
    )


@router.websocket("/ws/{room_id}")
async def match_socket(websocket: WebSocket, room_id: str, player_id: str):
    await session_manager.handle_connection(websocket, room_id, player_id)
