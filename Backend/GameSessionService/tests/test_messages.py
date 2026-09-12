import pytest
from pydantic import ValidationError

from app.models.messages import InputMessage


def test_valid_input_message_parses() -> None:
    msg = InputMessage.model_validate_json(
        '{"type": "input", "thrust": 1, "turn": -1, "fire": true}'
    )
    assert msg.thrust == 1
    assert msg.turn == -1
    assert msg.fire is True


def test_input_message_fire_defaults_false() -> None:
    msg = InputMessage.model_validate_json('{"type": "input", "thrust": 0, "turn": 0}')
    assert msg.fire is False


@pytest.mark.parametrize("thrust", [2, -2, 99])
def test_out_of_range_thrust_is_rejected(thrust: int) -> None:
    with pytest.raises(ValidationError):
        InputMessage.model_validate_json(
            f'{{"type": "input", "thrust": {thrust}, "turn": 0}}'
        )


def test_wrong_type_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        InputMessage.model_validate_json('{"type": "ping", "thrust": 0, "turn": 0}')


def test_malformed_json_is_rejected() -> None:
    with pytest.raises(ValidationError):
        InputMessage.model_validate_json("not json")


def test_state_message_serializes_ships_list() -> None:
    from app.models.messages import ShipState, StateMessage

    state = StateMessage(
        tick=1,
        ships=[
            ShipState(
                id="p1",
                x=0,
                y=0,
                rotation=0,
                vx=0,
                vy=0,
                hp=100,
                max_hp=100,
                alive=True,
            )
        ],
        asteroids=[],
        bullets=[],
        asteroids_spawned=[],
        asteroids_removed=[],
    )

    dumped = state.model_dump()
    assert dumped["ships"][0]["id"] == "p1"
    assert dumped["ships"][0]["hp"] == 100
    assert dumped["ships"][0]["alive"] is True
    assert "ship" not in dumped


def test_state_message_serializes_asteroids_bullets_and_diffs() -> None:
    from app.models.messages import (
        AsteroidInit,
        AsteroidState,
        BulletState,
        StateMessage,
    )

    state = StateMessage(
        tick=1,
        ships=[],
        asteroids=[
            AsteroidState(
                id="ast-1", x=0, y=0, rotation=0, vx=0, vy=0, hp=15, max_hp=30
            )
        ],
        bullets=[BulletState(id="blt-1", x=1, y=2, rotation=0.5)],
        asteroids_spawned=[AsteroidInit(id="ast-1-frag0", x=0, y=0, r=34.0)],
        asteroids_removed=["ast-1"],
    )

    dumped = state.model_dump()
    assert dumped["asteroids"][0]["hp"] == 15
    assert dumped["bullets"][0]["id"] == "blt-1"
    assert dumped["asteroids_spawned"][0]["id"] == "ast-1-frag0"
    assert dumped["asteroids_removed"] == ["ast-1"]
