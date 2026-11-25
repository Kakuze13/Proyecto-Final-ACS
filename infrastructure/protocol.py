import json
from typing import Any


MAX_FRAME_BYTES = 65_536

REQUEST_FIELDS: dict[str, set[str]] = {
    "CONNECT": {"username"},
    "DISCONNECT": set(),
    "CREATE_ROOM": {"room"},
    "LIST_ROOMS": set(),
    "JOIN_ROOM": {"room"},
    "LEAVE_ROOM": {"room"},
    "LIST_USERS": set(),
    "SEND_MESSAGE": {"room", "content"},
    "HISTORY": {"room"},
}
OPTIONAL_FIELDS: dict[str, set[str]] = {
    "LIST_USERS": {"room"},
    "HISTORY": {"limit"},
}


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError(f"Campo JSON duplicado: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ProtocolError(f"Constante JSON no válida: {value}")


class ProtocolError(ValueError):
    def __init__(self, message: str, code: str = "INVALID_REQUEST") -> None:
        super().__init__(message)
        self.code = code


def encode_message(message: dict[str, Any]) -> bytes:
    if not isinstance(message, dict):
        raise ProtocolError("Cada mensaje debe ser un objeto JSON")
    try:
        frame = (
            json.dumps(message, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise ProtocolError("El mensaje no se puede serializar") from error
    if len(frame) > MAX_FRAME_BYTES:
        raise ProtocolError("El mensaje supera el tamaño máximo", "MESSAGE_TOO_LARGE")
    return frame


def decode_frame(frame: bytes) -> dict[str, Any]:
    if len(frame) > MAX_FRAME_BYTES:
        raise ProtocolError("El mensaje supera el tamaño máximo", "MESSAGE_TOO_LARGE")
    if not frame.endswith(b"\n") or frame.endswith(b"\r\n") or frame.count(b"\n") != 1:
        raise ProtocolError("El frame debe terminar en un único LF")
    try:
        message = json.loads(
            frame[:-1].decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("El frame no contiene JSON UTF-8 válido") from error
    if not isinstance(message, dict):
        raise ProtocolError("Cada mensaje debe ser un objeto JSON")
    return message


def validate_request(message: dict[str, Any]) -> None:
    message_type = message.get("type")
    if not isinstance(message_type, str) or message_type not in REQUEST_FIELDS:
        raise ProtocolError("Tipo de solicitud desconocido", "UNSUPPORTED_TYPE")

    request_id = message.get("request_id")
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 64:
        raise ProtocolError("request_id debe tener entre 1 y 64 caracteres")

    allowed = {"type", "request_id"} | REQUEST_FIELDS[message_type] | OPTIONAL_FIELDS.get(
        message_type, set()
    )
    unexpected = message.keys() - allowed
    if unexpected:
        raise ProtocolError(f"Campo(s) no permitido(s): {', '.join(sorted(unexpected))}")

    required = {"type", "request_id"} | REQUEST_FIELDS[message_type]
    missing = required - message.keys()
    if missing:
        raise ProtocolError(f"Falta(n) campo(s): {', '.join(sorted(missing))}")

    for field in REQUEST_FIELDS[message_type] | OPTIONAL_FIELDS.get(message_type, set()):
        if field in message and not isinstance(message[field], str):
            if field == "limit" and type(message[field]) is int and 1 <= message[field] <= 100:
                continue
            raise ProtocolError(f"{field} debe tener un tipo válido")
    if "limit" in message and not 1 <= message["limit"] <= 100:
        raise ProtocolError("limit debe estar entre 1 y 100")


class FrameDecoder:
    def __init__(self, max_frame_bytes: int = MAX_FRAME_BYTES) -> None:
        if max_frame_bytes < 2:
            raise ValueError("max_frame_bytes debe ser al menos 2")
        self.max_frame_bytes = max_frame_bytes
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        self._buffer.extend(data)
        messages: list[dict[str, Any]] = []
        while True:
            delimiter = self._buffer.find(b"\n")
            if delimiter < 0:
                if len(self._buffer) >= self.max_frame_bytes:
                    raise ProtocolError("El mensaje supera el tamaño máximo", "MESSAGE_TOO_LARGE")
                return messages
            frame_length = delimiter + 1
            if frame_length > self.max_frame_bytes:
                raise ProtocolError("El mensaje supera el tamaño máximo", "MESSAGE_TOO_LARGE")
            frame = bytes(self._buffer[:frame_length])
            del self._buffer[:frame_length]
            messages.append(decode_frame(frame))
