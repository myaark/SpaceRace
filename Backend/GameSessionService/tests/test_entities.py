from app.entities import Ship


def test_to_state_reflects_body_position_and_id() -> None:
    ship = Ship("ship-1", (10, -20))

    state = ship.to_state()

    assert state["id"] == "ship-1"
    assert state["x"] == 10
    assert state["y"] == -20
    assert state["rotation"] == 0
    assert state["vx"] == 0
    assert state["vy"] == 0
