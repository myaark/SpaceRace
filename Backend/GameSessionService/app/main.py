import asyncio
import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.config import settings
from app.game_loop import run_game_loop
from app.session import GameSession

logger = logging.getLogger(__name__)

app = FastAPI(title="Game Session Service")

sessions: dict[str, GameSession] = {}
loop_tasks: dict[str, asyncio.Task] = {}

VALID_INPUT_VALUES = (-1, 0, 1)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "room_id": settings.room_id,
    }


def _get_or_create_session(room_id: str) -> GameSession:
    session = sessions.get(room_id)
    if session is None:
        session = GameSession(room_id)
        sessions[room_id] = session
        loop_tasks[room_id] = asyncio.create_task(run_game_loop(session))
    return session


@app.websocket("/ws/{room_id}")
async def match_socket(websocket: WebSocket, room_id: str):
    await websocket.accept()
    session = _get_or_create_session(room_id)
    session.register(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Malformed input message on room %s: %r", room_id, raw)
                continue

            if not isinstance(message, dict) or message.get("type") != "input":
                logger.warning("Unexpected message on room %s: %r", room_id, message)
                continue

            thrust = message.get("thrust")
            turn = message.get("turn")
            if thrust not in VALID_INPUT_VALUES or turn not in VALID_INPUT_VALUES:
                logger.warning(
                    "Malformed input values on room %s: %r", room_id, message
                )
                continue

            session.set_input(websocket, thrust, turn)
    except WebSocketDisconnect:
        pass
    finally:
        session.unregister(websocket)
