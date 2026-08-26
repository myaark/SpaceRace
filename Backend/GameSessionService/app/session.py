import logging
import math

import pymunk
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.entities import Asteroid, Ship, generate_asteroid_layout
from app.game_settings import game_settings
from app.models.messages import AsteroidInit, InitMessage, ShipState, StateMessage


class GameSession:
    """Owns the authoritative physics state and connected sockets for one room."""

    def __init__(self, room_id: str, logger: logging.Logger | None = None) -> None:
        self.room_id = room_id
        self._logger = logger or logging.getLogger(f"{__name__}.{room_id}")
        self.space = pymunk.Space()
        self.space.gravity = (0, 0)
        self.space.damping = game_settings.space_damping

        self._belt_center = pymunk.Vec2d(*game_settings.belt_center)
        self._inner_fence_r = game_settings.inner_fence_r
        self._outer_fence_r = game_settings.outer_fence_r
        self._spawn = self._belt_center + pymunk.Vec2d(*game_settings.spawn_offset)

        self.ship = Ship("ship-1", (self._spawn.x, self._spawn.y))
        self.space.add(self.ship.body, self.ship.shape)

        layout = generate_asteroid_layout(
            (self._belt_center.x, self._belt_center.y),
            self._inner_fence_r,
            self._outer_fence_r,
            (self._spawn.x, self._spawn.y),
        )
        self.asteroids: dict[str, Asteroid] = {}
        for asteroid_id, x, y, r, drift, period in layout:
            asteroid = Asteroid(asteroid_id, (x, y), r, drift, period)
            self.space.add(asteroid.body, asteroid.shape)
            self.asteroids[asteroid_id] = asteroid

        self.connections: set[WebSocket] = set()
        self.latest_input: dict[WebSocket, dict] = {}
        self._active_client: WebSocket | None = None
        self.tick_count = 0
        self._elapsed_ms = 0.0

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
                (thrust * game_settings.ship_thrust_force, 0), (0, 0)
            )
        self.ship.body.angular_velocity = turn * game_settings.ship_turn_rate

    def _clamp_speed(self, body: pymunk.Body, max_speed: float) -> None:
        speed = body.velocity.length
        if speed > max_speed:
            body.velocity = body.velocity * (max_speed / speed)

    def _clamp_to_belt(self, body: pymunk.Body) -> None:
        offset = body.position - self._belt_center
        distance = offset.length

        if self._inner_fence_r <= distance <= self._outer_fence_r:
            return

        past_outer = distance > self._outer_fence_r
        clamped_distance = self._outer_fence_r if past_outer else self._inner_fence_r
        radial_dir = offset.normalized() if distance > 1e-6 else pymunk.Vec2d(1, 0)

        body.position = self._belt_center + radial_dir * clamped_distance
        radial_velocity = body.velocity.dot(radial_dir)
        # Only kill the component still pushing past this fence, so a body
        # that has reversed course back toward the belt isn't stuck there.
        still_escaping = radial_velocity > 0 if past_outer else radial_velocity < 0
        if still_escaping:
            body.velocity = body.velocity - radial_dir * radial_velocity

    def _apply_drift(self) -> None:
        """Small continuous sinusoidal force on drift=True asteroids — the
        server-authoritative replacement for the frontend's old tween wobble."""
        for index, asteroid in enumerate(self.asteroids.values()):
            if not asteroid.drift:
                continue
            phase = index * (math.pi / 4)
            angle = (2 * math.pi * self._elapsed_ms / asteroid.period) + phase
            force = (
                pymunk.Vec2d(math.cos(angle), math.sin(angle))
                * game_settings.asteroid_drift_force
            )
            asteroid.body.apply_force_at_local_point(force, (0, 0))

    def step(self, dt: float) -> None:
        """Advance physics by one tick: apply input, integrate, enforce the belt boundary."""
        self._elapsed_ms += dt * 1000
        self._apply_input()
        self._apply_drift()
        self.space.step(dt)

        self._clamp_speed(self.ship.body, game_settings.ship_max_speed)
        self._clamp_to_belt(self.ship.body)
        for asteroid in self.asteroids.values():
            self._clamp_speed(asteroid.body, game_settings.asteroid_max_speed)
            self._clamp_to_belt(asteroid.body)

        self.tick_count += 1

    def to_init_message(self) -> InitMessage:
        """One-time layout message: asteroid radius never changes, but since
        the layout is now server-generated (not a hand-copied frontend
        constant), the client needs it sent explicitly on connect."""
        return InitMessage(
            belt_center_x=self._belt_center.x,
            belt_center_y=self._belt_center.y,
            spawn_x=self._spawn.x,
            spawn_y=self._spawn.y,
            inner_r=self._inner_fence_r,
            outer_r=self._outer_fence_r,
            asteroids=[
                AsteroidInit(
                    id=a.id, x=a.body.position.x, y=a.body.position.y, r=a.radius
                )
                for a in self.asteroids.values()
            ],
        )

    def to_broadcast_message(self) -> StateMessage:
        return StateMessage(
            tick=self.tick_count,
            ship=ShipState(**self.ship.to_state()),
            asteroids=[ShipState(**a.to_state()) for a in self.asteroids.values()],
        )

    async def broadcast(self) -> None:
        if not self.connections:
            return
        message = self.to_broadcast_message().model_dump()
        dead: list[WebSocket] = []
        for websocket in self.connections:
            try:
                await websocket.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                self._logger.info(
                    "Dropping disconnected client from room %s", self.room_id
                )
                dead.append(websocket)
        for websocket in dead:
            self.unregister(websocket)
