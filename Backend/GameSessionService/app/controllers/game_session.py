import asyncio
import logging

from fastapi import WebSocket
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.game_loop import run_game_loop
from app.models.messages import InputMessage
from app.session import GameSession

ROOM_FULL_CLOSE_CODE = 4409


class SessionManager:
    """Owns GameSession + game-loop-task lifecycle for every room."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._loop_tasks: dict[str, asyncio.Task] = {}
        self._logger = logger or logging.getLogger(__name__)

    def get_or_create(self, room_id: str) -> GameSession:
        session = self._sessions.get(room_id)
        if session is None:
            session = GameSession(room_id)
            self._sessions[room_id] = session
            self._loop_tasks[room_id] = asyncio.create_task(run_game_loop(session))
        return session

    def remove(self, room_id: str) -> None:
        task = self._loop_tasks.pop(room_id, None)
        if task is not None:
            task.cancel()
        self._sessions.pop(room_id, None)

    async def handle_connection(self, websocket: WebSocket, room_id: str) -> None:
        await websocket.accept()
        session = self.get_or_create(room_id)

        if session.connections:
            await websocket.send_json({"type": "error", "reason": "room_full"})
            await websocket.close(code=ROOM_FULL_CLOSE_CODE)
            return

        session.register(websocket)
        await websocket.send_json(session.to_init_message().model_dump())
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = InputMessage.model_validate_json(raw)
                except ValidationError:
                    self._logger.warning(
                        "Malformed input message on room %s: %r", room_id, raw
                    )
                    continue
                session.set_input(websocket, message.thrust, message.turn)
        except WebSocketDisconnect:
            pass
        finally:
            session.unregister(websocket)
            if not session.connections:
                self.remove(room_id)
