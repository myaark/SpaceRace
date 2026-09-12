from typing import Literal

from pydantic import BaseModel, field_validator

VALID_INPUT_VALUES = (-1, 0, 1)


class InputMessage(BaseModel):
    """Incoming websocket message: a player's current thrust/turn/fire input."""

    type: Literal["input"]
    thrust: int
    turn: int
    fire: bool = False

    @field_validator("thrust", "turn")
    @classmethod
    def _validate_range(cls, value: int) -> int:
        if value not in VALID_INPUT_VALUES:
            raise ValueError(f"must be one of {VALID_INPUT_VALUES}")
        return value


class ShipState(BaseModel):
    id: str
    x: float
    y: float
    rotation: float
    vx: float
    vy: float
    hp: int
    max_hp: int
    alive: bool


class AsteroidState(BaseModel):
    id: str
    x: float
    y: float
    rotation: float
    vx: float
    vy: float
    hp: int
    max_hp: int


class BulletState(BaseModel):
    id: str
    x: float
    y: float
    rotation: float


class AsteroidInit(BaseModel):
    id: str
    x: float
    y: float
    r: float


class InitMessage(BaseModel):
    """One-time layout message sent right after a client connects."""

    type: Literal["init"] = "init"
    belt_center_x: float
    belt_center_y: float
    spawn_x: float
    spawn_y: float
    inner_r: float
    outer_r: float
    asteroids: list[AsteroidInit]


class StateMessage(BaseModel):
    """Per-tick broadcast of authoritative physics state."""

    type: Literal["state"] = "state"
    tick: int
    ships: list[ShipState]
    asteroids: list[AsteroidState]
    bullets: list[BulletState]
    asteroids_spawned: list[AsteroidInit]
    asteroids_removed: list[str]
