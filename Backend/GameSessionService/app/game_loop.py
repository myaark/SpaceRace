import asyncio

from app.config import settings


async def run_game_loop() -> None:
    """Fixed-tick server-authoritative loop for a single match.

    TODO: collect inputs, step pymunk physics, resolve collisions,
    update scores/respawns, broadcast state to connected clients.
    """
    tick_interval = 1 / settings.tick_rate_hz
    while True:
        await asyncio.sleep(tick_interval)
