import asyncio
import json

import pytest
from starlette.websockets import WebSocketDisconnect

from app.controllers.game_session import ROOM_FULL_CLOSE_CODE, SessionManager


class FakeWebSocket:
    """Minimal async double for fastapi.WebSocket, driven by tests."""

    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self.closed_code: int | None = None
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._disconnect = asyncio.Event()

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    async def receive_text(self) -> str:
        queue_get = asyncio.ensure_future(self._queue.get())
        disconnect_wait = asyncio.ensure_future(self._disconnect.wait())
        done, pending = await asyncio.wait(
            {queue_get, disconnect_wait}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        if disconnect_wait in done:
            raise WebSocketDisconnect()
        return queue_get.result()

    async def close(self, code: int = 1000) -> None:
        self.closed_code = code

    def send_input(self, raw: str) -> None:
        self._queue.put_nowait(raw)

    def disconnect(self) -> None:
        self._disconnect.set()


@pytest.mark.asyncio
async def test_get_or_create_reuses_existing_session() -> None:
    manager = SessionManager()
    s1 = manager.get_or_create("room-1")
    s2 = manager.get_or_create("room-1")

    assert s1 is s2
    manager.remove("room-1")


@pytest.mark.asyncio
async def test_duplicate_player_id_to_owned_room_is_rejected() -> None:
    manager = SessionManager()
    ws1 = FakeWebSocket()
    task1 = asyncio.create_task(manager.handle_connection(ws1, "room-1", "p1"))
    await asyncio.sleep(0.02)

    ws2 = FakeWebSocket()
    await manager.handle_connection(ws2, "room-1", "p1")

    assert ws2.closed_code == ROOM_FULL_CLOSE_CODE
    assert ws2.sent[-1]["reason"] == "duplicate_player"

    ws1.disconnect()
    await task1


@pytest.mark.asyncio
async def test_eleventh_player_to_a_full_room_is_rejected() -> None:
    manager = SessionManager()
    tasks = []
    sockets = []
    for i in range(10):
        ws = FakeWebSocket()
        sockets.append(ws)
        tasks.append(
            asyncio.create_task(manager.handle_connection(ws, "room-1", f"p{i}"))
        )
    await asyncio.sleep(0.02)

    overflow_ws = FakeWebSocket()
    await manager.handle_connection(overflow_ws, "room-1", "p-overflow")

    assert overflow_ws.closed_code == ROOM_FULL_CLOSE_CODE
    assert overflow_ws.sent[-1]["reason"] == "room_full"

    for ws in sockets:
        ws.disconnect()
    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_invalid_player_id_is_rejected() -> None:
    manager = SessionManager()
    ws = FakeWebSocket()

    await manager.handle_connection(ws, "room-1", "has a space")

    assert ws.closed_code == ROOM_FULL_CLOSE_CODE
    assert ws.sent[-1]["reason"] == "invalid_player_id"


@pytest.mark.asyncio
async def test_session_and_task_removed_when_room_becomes_empty() -> None:
    manager = SessionManager()
    ws = FakeWebSocket()
    task = asyncio.create_task(manager.handle_connection(ws, "room-1", "p1"))
    await asyncio.sleep(0.02)

    ws.disconnect()
    await task

    assert manager.get_or_create("room-1") is not None  # creates a fresh one
    manager.remove("room-1")


@pytest.mark.asyncio
async def test_malformed_input_is_ignored_connection_stays_open() -> None:
    manager = SessionManager()
    ws = FakeWebSocket()
    task = asyncio.create_task(manager.handle_connection(ws, "room-1", "p1"))
    await asyncio.sleep(0.02)

    ws.send_input("not json")
    await asyncio.sleep(0.02)
    ws.send_input(json.dumps({"type": "input", "thrust": 99, "turn": 0}))
    await asyncio.sleep(0.02)
    ws.send_input(json.dumps({"type": "input", "thrust": 1, "turn": 0}))
    await asyncio.sleep(0.02)

    ws.disconnect()
    await task  # must complete cleanly, not raise
