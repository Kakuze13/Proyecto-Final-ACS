import pytest

from infrastructure.protocol import (
    FrameDecoder,
    MAX_FRAME_BYTES,
    ProtocolError,
    decode_frame,
    encode_message,
    validate_request,
)


def test_frame_decoder_reassembles_fragmented_input() -> None:
    decoder = FrameDecoder()
    frame = encode_message({"type": "LIST_ROOMS", "request_id": "r1"})

    assert decoder.feed(frame[:5]) == []
    assert decoder.feed(frame[5:]) == [{"type": "LIST_ROOMS", "request_id": "r1"}]


def test_frame_decoder_processes_multiple_messages_from_one_chunk() -> None:
    decoder = FrameDecoder()
    first = {"type": "LIST_ROOMS", "request_id": "r1"}
    second = {"type": "LIST_USERS", "request_id": "r2"}

    assert decoder.feed(encode_message(first) + encode_message(second)) == [first, second]


def test_malformed_json_is_rejected() -> None:
    with pytest.raises(ProtocolError):
        decode_frame(b'{"type":\n')


@pytest.mark.parametrize(
    "frame",
    [
        b'{"type":"CONNECT","type":"LIST_ROOMS","request_id":"r1"}\n',
        b'{"type":"LIST_ROOMS","request_id":"r1","value":NaN}\n',
        b'{"type":"LIST_ROOMS","request_id":"r1"}\r\n',
    ],
)
def test_nonstandard_json_frames_are_rejected(frame: bytes) -> None:
    with pytest.raises(ProtocolError):
        decode_frame(frame)


@pytest.mark.parametrize(
    "message",
    [
        {"type": "CONNECT", "request_id": "r1"},
        {"type": "CONNECT", "request_id": "", "username": "ana"},
        {"type": "CONNECT", "request_id": "r1", "username": "ana", "extra": True},
        {"type": "HISTORY", "request_id": "r1", "room": "general", "limit": 101},
    ],
)
def test_invalid_request_shape_is_rejected(message: dict[str, object]) -> None:
    with pytest.raises(ProtocolError):
        validate_request(message)


def test_oversized_frame_is_rejected() -> None:
    decoder = FrameDecoder(max_frame_bytes=8)
    with pytest.raises(ProtocolError) as error:
        decoder.feed(b'{"1234567')
    assert error.value.code == "MESSAGE_TOO_LARGE"


def test_protocol_accepts_exact_limit_and_rejects_one_byte_over() -> None:
    message = {"content": "x" * (MAX_FRAME_BYTES - 15)}
    frame = encode_message(message)
    assert len(frame) == MAX_FRAME_BYTES
    assert decode_frame(frame) == message

    with pytest.raises(ProtocolError) as error:
        encode_message({"content": "x" * (MAX_FRAME_BYTES - 14)})
    assert error.value.code == "MESSAGE_TOO_LARGE"
