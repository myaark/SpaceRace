import pytest
from pydantic import ValidationError

from app.models.messages import InputMessage


def test_valid_input_message_parses() -> None:
    msg = InputMessage.model_validate_json('{"type": "input", "thrust": 1, "turn": -1}')
    assert msg.thrust == 1
    assert msg.turn == -1


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
        ships=[ShipState(id="p1", x=0, y=0, rotation=0, vx=0, vy=0)],
        asteroids=[],
    )

    dumped = state.model_dump()
    assert dumped["ships"][0]["id"] == "p1"
    assert "ship" not in dumped
