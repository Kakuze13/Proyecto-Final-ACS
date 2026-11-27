from client.command_handler import _command_to_request


def test_delete_room_command_creates_delete_request() -> None:
    request = _command_to_request(["/delete", "general"])

    assert request is not None
    assert request["type"] == "DELETE_ROOM"
    assert request["room"] == "general"


def test_delete_room_command_requires_a_room_name() -> None:
    assert _command_to_request(["/delete"]) is None
