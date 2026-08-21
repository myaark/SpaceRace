import asyncio

from app.config import settings
from app.session import GameSession


async def run_game_loop(session: GameSession) -> None:
    """Fixed-tick server-authoritative loop for a single game session.

    Each tick: apply the latest buffered input, step physics, enforce the
    belt boundary, then broadcast the resulting state to connected clients.
    """
    tick_interval = 1 / settings.tick_rate_hz
    while True:
        await asyncio.sleep(tick_interval)
        session.step(tick_interval)
        await session.broadcast()
