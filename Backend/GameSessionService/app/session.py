import logging
import math

import pymunk
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app import combat
from app.combat import Bullet
from app.entities import (
    ASTEROID_COLLISION_TYPE,
    SHIP_COLLISION_TYPE,
    Asteroid,
    Ship,
    generate_asteroid_layout,
)
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
        self._spawn_points = [
            self._belt_center + pymunk.Vec2d(*offset)
            for offset in game_settings.spawn_points
        ]

        layout = generate_asteroid_layout(
            (self._belt_center.x, self._belt_center.y),
            self._inner_fence_r,
            self._outer_fence_r,
            [(p.x, p.y) for p in self._spawn_points],
        )
        self.asteroids: dict[str, Asteroid] = {}
        for asteroid_id, x, y, r, tier, drift, period in layout:
            asteroid = Asteroid(asteroid_id, (x, y), r, tier, drift, period)
            self.space.add(asteroid.body, asteroid.shape)
            self.asteroids[asteroid_id] = asteroid

        self.ships: dict[str, Ship] = {}
        self.connections: dict[str, WebSocket] = {}
        self.latest_input: dict[str, dict] = {}
        self._spawn_index_by_player: dict[str, int] = {}
        self.tick_count = 0
        self._elapsed_ms = 0.0
        self.bullets: dict[str, Bullet] = {}
        self._bullet_seq = 0

    def _next_free_spawn_index(self) -> int:
        occupied = set(self._spawn_index_by_player.values())
        for index in range(len(self._spawn_points)):
            if index not in occupied:
                return index
        raise RuntimeError(f"room {self.room_id} has no free spawn point")

    def is_full(self) -> bool:
        return len(self.ships) >= game_settings.max_players

    def has_player(self, player_id: str) -> bool:
        return player_id in self.ships

    def register(self, player_id: str, websocket: WebSocket) -> None:
        index = self._next_free_spawn_index()
        position = self._spawn_points[index]
        ship = Ship(player_id, (position.x, position.y))
        self.space.add(ship.body, ship.shape)
        self.ships[player_id] = ship
        self._spawn_index_by_player[player_id] = index
        self.connections[player_id] = websocket

    def unregister(self, player_id: str) -> None:
        ship = self.ships.pop(player_id, None)
        if ship is not None:
            self.space.remove(ship.body, ship.shape)
        self.latest_input.pop(player_id, None)
        self.connections.pop(player_id, None)
        self._spawn_index_by_player.pop(player_id, None)

    def set_input(self, player_id: str, thrust: int, turn: int, fire: bool = False) -> None:
        self.latest_input[player_id] = {"thrust": thrust, "turn": turn, "fire": fire}

    def _apply_input(self) -> None:
        for player_id, ship in self.ships.items():
            if not ship.alive:
                continue
            input_state = self.latest_input.get(
                player_id, {"thrust": 0, "turn": 0, "fire": False}
            )
            thrust = input_state["thrust"]
            turn = input_state["turn"]

            if thrust:
                ship.body.apply_force_at_local_point(
                    (thrust * game_settings.ship_thrust_force, 0), (0, 0)
                )
            ship.body.angular_velocity = turn * game_settings.ship_turn_rate

    def _spawn_bullets(self) -> None:
        for player_id, ship in self.ships.items():
            if not ship.alive:
                continue
            input_state = self.latest_input.get(player_id)
            if input_state is None or not input_state["fire"]:
                continue
            self._bullet_seq += 1
            bullet_id = f"blt-{player_id}-{self._bullet_seq}"
            bullet = combat.spawn_bullet(bullet_id, player_id, ship, self._elapsed_ms)
            self.bullets[bullet_id] = bullet

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
        self._spawn_bullets()
        self._apply_drift()
        self.space.step(dt)

        for ship in self.ships.values():
            self._clamp_speed(ship.body, game_settings.ship_max_speed)
            self._clamp_to_belt(ship.body)
        for asteroid in self.asteroids.values():
            self._clamp_speed(asteroid.body, game_settings.asteroid_max_speed)
            self._clamp_to_belt(asteroid.body)

        self.tick_count += 1

    def to_init_message(self) -> InitMessage:
        """One-time layout message: asteroid radius never changes, but since
        the layout is now server-generated (not a hand-copied frontend
        constant), the client needs it sent explicitly on connect. spawn_x/y
        always describes spawn point 0 — the point the frontend hardcodes
        for its own ship's pre-broadcast placement."""
        spawn = self._spawn_points[0]
        return InitMessage(
            belt_center_x=self._belt_center.x,
            belt_center_y=self._belt_center.y,
            spawn_x=spawn.x,
            spawn_y=spawn.y,
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
            ships=[ShipState(**ship.to_state()) for ship in self.ships.values()],
            asteroids=[ShipState(**a.to_state()) for a in self.asteroids.values()],
        )

    async def broadcast(self) -> None:
        if not self.connections:
            return
        message = self.to_broadcast_message().model_dump()
        dead: list[str] = []
        # Snapshot: send_json yields, and register/unregister run on other
        # tasks — mutating self.connections mid-iteration would raise.
        for player_id, websocket in list(self.connections.items()):
            try:
                await websocket.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                self._logger.info(
                    "Dropping disconnected client %s from room %s",
                    player_id,
                    self.room_id,
                )
                dead.append(player_id)
        for player_id in dead:
            self.unregister(player_id)
