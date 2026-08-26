import asyncio
import logging

import pytest

from app.config import settings
from app.game_loop import run_game_loop


class _ExplodingOnceSession:
    def __init__(self) -> None:
        self.room_id = "test-room"
        self.step_calls = 0
        self.broadcast_calls = 0

    def step(self, dt: float) -> None:
        self.step_calls += 1
        if self.step_calls == 1:
            raise RuntimeError("boom")

    async def broadcast(self) -> None:
        self.broadcast_calls += 1


@pytest.mark.asyncio
async def test_loop_survives_one_bad_tick_and_logs_it(monkeypatch, caplog) -> None:
    monkeypatch.setattr(settings, "tick_rate_hz", 1000)
    session = _ExplodingOnceSession()
    task = asyncio.create_task(run_game_loop(session))

    with caplog.at_level(logging.ERROR):
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert session.step_calls >= 2
    assert session.broadcast_calls >= 1
    assert "Unhandled error in game loop" in caplog.text
