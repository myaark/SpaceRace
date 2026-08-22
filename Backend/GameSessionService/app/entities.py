import pymunk

SHIP_MASS = 1.0
SHIP_RADIUS = 20.0
SHIP_THRUST_FORCE = 400.0
SHIP_TURN_RATE = 3.0  # radians/sec
SHIP_MAX_SPEED = 90.0  # px/sec — deliberately low handling cap


class Ship:
    """A player-controlled ship: a pymunk Body + Circle wrapped with game state."""

    def __init__(self, ship_id: str, position: tuple[float, float]) -> None:
        self.id = ship_id
        moment = pymunk.moment_for_circle(SHIP_MASS, 0, SHIP_RADIUS)
        self.body = pymunk.Body(SHIP_MASS, moment)
        self.body.position = position
        self.shape = pymunk.Circle(self.body, SHIP_RADIUS)

    def to_state(self) -> dict:
        return {
            "id": self.id,
            "x": self.body.position.x,
            "y": self.body.position.y,
            "rotation": self.body.angle,
            "vx": self.body.velocity.x,
            "vy": self.body.velocity.y,
        }
