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
