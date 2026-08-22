import logging

import pymunk
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.entities import SHIP_MAX_SPEED, SHIP_THRUST_FORCE, SHIP_TURN_RATE, Ship

logger = logging.getLogger(__name__)

# Belt boundary geometry. Must match Frontend/src/scenes/BeltScene.js's
# BELT_CENTER / OUTER_FENCE_R / INNER_FENCE_R — there is no shared-schema
# mechanism enforcing this, so keep the two in sync by hand.
BELT_CENTER = pymunk.Vec2d(-200, 1500)
OUTER_FENCE_R = 1760.0
INNER_FENCE_R = 1420.0

# Offset from BELT_CENTER to Frontend/src/scenes/BeltScene.js's SHIP constant
# (724, 318). The ship must spawn exactly here — it's the only point the
# frontend draws before the first server state arrives, so any mismatch
# makes the ship appear to teleport/disappear on the first broadcast.
SPAWN_OFFSET = pymunk.Vec2d(924, -1182)

# Fraction of velocity retained per second — unpowered ship stops in ~0.3s.
SPACE_DAMPING = 0.0003


class GameSession:
    """Owns the authoritative physics state and connected sockets for one room."""

    def __init__(self, room_id: str) -> None:
        self.room_id = room_id
        self.space = pymunk.Space()
        self.space.gravity = (0, 0)
        self.space.damping = SPACE_DAMPING

        spawn = BELT_CENTER + SPAWN_OFFSET
        self.ship = Ship("ship-1", (spawn.x, spawn.y))
        self.space.add(self.ship.body, self.ship.shape)

        self.connections: set[WebSocket] = set()
        self.latest_input: dict[WebSocket, dict] = {}
        self._active_client: WebSocket | None = None
        self.tick_count = 0

    def register(self, websocket: WebSocket) -> None:
        self.connections.add(websocket)

    def unregister(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)
        self.latest_input.pop(websocket, None)
        if self._active_client is websocket:
            self._active_client = None

    def set_input(self, websocket: WebSocket, thrust: int, turn: int) -> None:
        self.latest_input[websocket] = {"thrust": thrust, "turn": turn}
        self._active_client = websocket

    def _apply_input(self) -> None:
        input_state = self.latest_input.get(
            self._active_client, {"thrust": 0, "turn": 0}
        )
        thrust = input_state["thrust"]
        turn = input_state["turn"]

        if thrust:
            self.ship.body.apply_force_at_local_point(
                (thrust * SHIP_THRUST_FORCE, 0), (0, 0)
            )
        self.ship.body.angular_velocity = turn * SHIP_TURN_RATE

    def _clamp_speed(self) -> None:
        body = self.ship.body
        speed = body.velocity.length
        if speed > SHIP_MAX_SPEED:
            body.velocity = body.velocity * (SHIP_MAX_SPEED / speed)

    def _clamp_to_belt(self) -> None:
        body = self.ship.body
        offset = body.position - BELT_CENTER
        distance = offset.length

        if INNER_FENCE_R <= distance <= OUTER_FENCE_R:
            return

        past_outer = distance > OUTER_FENCE_R
        clamped_distance = OUTER_FENCE_R if past_outer else INNER_FENCE_R
        radial_dir = offset.normalized() if distance > 1e-6 else pymunk.Vec2d(1, 0)

        body.position = BELT_CENTER + radial_dir * clamped_distance
        radial_velocity = body.velocity.dot(radial_dir)
        # Only kill the component still pushing past this fence, so a ship
        # that has reversed course back toward the belt isn't stuck there.
        still_escaping = radial_velocity > 0 if past_outer else radial_velocity < 0
        if still_escaping:
            body.velocity = body.velocity - radial_dir * radial_velocity

    def step(self, dt: float) -> None:
        """Advance physics by one tick: apply input, integrate, enforce the belt boundary."""
        self._apply_input()
        self.space.step(dt)
        self._clamp_speed()
        self._clamp_to_belt()
        self.tick_count += 1

    def to_broadcast_message(self) -> dict:
        return {"type": "state", "tick": self.tick_count, "ship": self.ship.to_state()}

    async def broadcast(self) -> None:
        if not self.connections:
            return
        message = self.to_broadcast_message()
        dead: list[WebSocket] = []
        for websocket in self.connections:
            try:
                await websocket.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                logger.info("Dropping disconnected client from room %s", self.room_id)
                dead.append(websocket)
        for websocket in dead:
            self.unregister(websocket)
