from __future__ import annotations

import argparse
import asyncio
import re
import secrets
import socket
from typing import Any

from client.tcp_client import TcpClient
from infrastructure.protocol import decode_frame, encode_message


MESSAGE_LENGTH = 2_000
DEFAULT_MESSAGE_COUNT = 200
ROOM_PATTERN = re.compile(r"[a-z0-9_-]{1,32}\Z")


def _request(operation: str, **fields: Any) -> dict[str, Any]:
    return {
        "type": operation,
        "request_id": secrets.token_hex(8),
        **fields,
    }


def _require_success(response: dict[str, Any], action: str) -> None:
    if response.get("type") != "SUCCESS":
        detail = response.get("message", response.get("code", "respuesta inválida"))
        raise RuntimeError(f"No se pudo {action}: {detail}")


async def _raw_request(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    request: dict[str, Any],
) -> dict[str, Any]:
    writer.write(encode_message(request))
    await writer.drain()

    while True:
        frame = await asyncio.wait_for(reader.readuntil(b"\n"), timeout=5)
        response = decode_frame(frame)
        if response.get("request_id") == request["request_id"]:
            return response


async def _connect(client: TcpClient, username: str) -> None:
    _require_success(
        await client.request(_request("CONNECT", username=username)),
        f"conectar {username}",
    )


async def _join(client: TcpClient, room: str) -> None:
    _require_success(
        await client.request(_request("JOIN_ROOM", room=room)),
        f"unirse a #{room}",
    )


async def _wait_for_room(client: TcpClient, room: str) -> None:
    response = await client.request(_request("LIST_ROOMS"))
    _require_success(response, "consultar las salas")
    rooms = response.get("data", {}).get("rooms", [])
    if not any(item.get("room") == room for item in rooms):
        raise RuntimeError(
            f"No existe #{room}. Créala y únete desde la interfaz gráfica "
            "antes de ejecutar la demostración."
        )


async def _collect_messages(
    client: TcpClient,
    marker: str,
    count: int,
    timeout: float = 30,
) -> int:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    received = 0
    while received < count:
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        try:
            event = await asyncio.wait_for(client.events.get(), timeout=remaining)
        except TimeoutError:
            break
        if (
            event.get("type") == "CHAT_MESSAGE"
            and event.get("content", "").startswith(marker)
        ):
            received += 1
    return received


async def _wait_for_slow_disconnect(reader: asyncio.StreamReader) -> None:
    async def read_until_closed() -> None:
        while await reader.read(4_096):
            pass

    try:
        await asyncio.wait_for(read_until_closed(), timeout=5)
    except TimeoutError as error:
        raise RuntimeError(
            "El cliente lento no se desconectó. Verifica que el servidor esté "
            "ejecutándose con --queue-size 1 y --socket-send-buffer 1024."
        ) from error


async def run_demo(host: str, port: int, room: str, message_count: int) -> None:
    suffix = secrets.token_hex(3)
    marker = f"DEMO-{suffix}"
    sender = TcpClient()
    healthy = TcpClient()
    slow_writer: asyncio.StreamWriter | None = None

    try:
        await sender.connect(host, port)
        await _connect(sender, f"demo_tx_{suffix}")
        await _wait_for_room(sender, room)
        await _join(sender, room)

        await healthy.connect(host, port)
        await _connect(healthy, f"demo_ok_{suffix}")
        await _join(healthy, room)

        slow_reader, slow_writer = await asyncio.open_connection(
            host,
            port,
            limit=65_536,
        )
        slow_socket = slow_writer.get_extra_info("socket")
        if slow_socket is None:
            raise RuntimeError("No se pudo acceder al socket del cliente lento")
        slow_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1_024)

        response = await _raw_request(
            slow_reader,
            slow_writer,
            _request("CONNECT", username=f"demo_slow_{suffix}"),
        )
        _require_success(response, "conectar el cliente lento")
        response = await _raw_request(
            slow_reader,
            slow_writer,
            _request("JOIN_ROOM", room=room),
        )
        _require_success(response, f"unir el cliente lento a #{room}")

        print(
            f"Enviando {message_count} mensajes de 2 000 caracteres a #{room}. "
            "La interfaz gráfica debería mostrarlos en tiempo real."
        )
        for index in range(1, message_count + 1):
            label = f"{marker} {index:03}/{message_count:03} "
            content = label + ("x" * (MESSAGE_LENGTH - len(label)))
            response = await sender.request(
                _request("SEND_MESSAGE", room=room, content=content)
            )
            _require_success(response, f"enviar el mensaje {index}")

        received = await _collect_messages(healthy, marker, message_count)
        if received != message_count:
            raise RuntimeError(
                f"El cliente saludable recibió {received}/{message_count} mensajes."
            )
        await _wait_for_slow_disconnect(slow_reader)

        print(
            f"Éxito: el cliente saludable recibió {received}/{message_count} "
            "mensajes y el cliente lento fue desconectado por backpressure."
        )
        print(
            f"En la GUI, revisa la sala #{room}; los mensajes están marcados "
            f"con {marker}."
        )
    finally:
        try:
            if slow_writer is not None:
                slow_writer.close()
                await slow_writer.wait_closed()
        finally:
            try:
                await sender.close()
            finally:
                await healthy.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demuestra concurrencia y backpressure en una sala de ChatRoom"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--room", default="demo_concurrencia")
    parser.add_argument("--messages", type=int, default=DEFAULT_MESSAGE_COUNT)
    args = parser.parse_args()

    if not 1 <= args.port <= 65_535:
        parser.error("--port debe estar entre 1 y 65535")
    if not ROOM_PATTERN.fullmatch(args.room):
        parser.error("--room debe usar 1-32 letras minúsculas, dígitos, _ o -")
    if not 101 <= args.messages <= 1_000:
        parser.error("--messages debe estar entre 101 y 1000 para saturar la cola")
    return args


def main() -> None:
    args = parse_args()
    print(
        f"Antes de continuar, abre la GUI, inicia sesión y únete a "
        f"#{args.room}. El generador comenzará al pulsar Enter."
    )
    input()
    try:
        asyncio.run(run_demo(args.host, args.port, args.room, args.messages))
    except KeyboardInterrupt:
        print("\nDemostración cancelada.")
    except (ConnectionError, OSError, RuntimeError, TimeoutError) as error:
        raise SystemExit(f"Demostración fallida: {error}") from error


if __name__ == "__main__":
    main()
