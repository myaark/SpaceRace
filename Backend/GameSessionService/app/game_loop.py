import asyncio
import logging

from app.config import settings
from app.session import GameSession

logger = logging.getLogger(__name__)


async def run_game_loop(session: GameSession) -> None:
    """Fixed-tick server-authoritative loop for a single game session.

    Each tick: apply the latest buffered input, step physics, enforce the
    belt boundary, then broadcast the resulting state to connected clients.
    An exception during a single tick is logged and does not stop the loop —
    other rooms have their own independent task and are unaffected either way.
    """
    tick_interval = 1 / settings.tick_rate_hz
    while True:
        await asyncio.sleep(tick_interval)
        try:
            session.step(tick_interval)
            await session.broadcast()
        except Exception:
            logger.exception(
                "Unhandled error in game loop for room %s", session.room_id
            )
