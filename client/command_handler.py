import asyncio
import uuid
from typing import Any

from client.tcp_client import TcpClient


HELP_TEXT = """Comandos:
  /rooms                         listar salas
  /create <sala>                 crear sala (el creador entra automáticamente)
  /delete <sala>                 eliminar sala creada por ti
  /join <sala>                   entrar en una sala
  /leave <sala>                  salir de una sala
  /users [sala]                  listar usuarios o integrantes de una sala
  /say <sala> <mensaje>          enviar un mensaje
  /history <sala> [límite]       consultar historial
  /help                          mostrar esta ayuda
  /quit                          desconectarse"""


def new_request(message_type: str, **fields: Any) -> dict[str, Any]:
    return {
        "type": message_type,
        "request_id": uuid.uuid4().hex,
        **fields,
    }


async def display_events(client: TcpClient) -> None:
    while True:
        event = await client.events.get()
        if event.get("type") == "CHAT_MESSAGE":
            print(f"\n[{event['room']}] {event['username']}: {event['content']}")
        else:
            print(f"\n[Evento] {event}")


async def run_console(host: str, port: int) -> None:
    username = (await asyncio.to_thread(input, "Nombre de usuario: ")).strip()
    client = TcpClient()
    display_task: asyncio.Task[None] | None = None
    try:
        await client.connect(host, port)
        response = await client.request(new_request("CONNECT", username=username))
        if response["type"] == "ERROR":
            print(f"Error: {response['message']}")
            return

        print(f"Conectado como {username}. Escribe /help para ver los comandos.")
        display_task = asyncio.create_task(display_events(client))
        while True:
            line = await asyncio.to_thread(input, "chatroom> ")
            parts = line.strip().split(maxsplit=2)
            if not parts:
                continue
            command = parts[0].lower()

            if command == "/help":
                print(HELP_TEXT)
                continue
            if command == "/quit":
                await client.request(new_request("DISCONNECT"))
                break

            request = _command_to_request(parts)
            if request is None:
                print("Comando inválido. Escribe /help para ver las opciones.")
                continue
            result = await client.request(request)
            if result["type"] == "ERROR":
                print(f"Error: {result['message']}")
            elif result["type"] == "HISTORY_RESULT":
                if result.get("truncated"):
                    print("Historial limitado por el tamaño máximo del protocolo.")
                for message in result["messages"]:
                    print(
                        f"[{message['timestamp']}] {message['username']}: "
                        f"{message['content']}"
                    )
            elif "data" in result:
                print(result["data"])
    except (OSError, asyncio.TimeoutError) as error:
        print(f"Conexión finalizada: {error}")
    finally:
        if display_task is not None:
            display_task.cancel()
            await asyncio.gather(display_task, return_exceptions=True)
        await client.close()


def _command_to_request(parts: list[str]) -> dict[str, Any] | None:
    command = parts[0].lower()
    if command == "/rooms" and len(parts) == 1:
        return new_request("LIST_ROOMS")
    if command == "/create" and len(parts) == 2:
        return new_request("CREATE_ROOM", room=parts[1])
    if command == "/delete" and len(parts) == 2:
        return new_request("DELETE_ROOM", room=parts[1])
    if command == "/join" and len(parts) == 2:
        return new_request("JOIN_ROOM", room=parts[1])
    if command == "/leave" and len(parts) == 2:
        return new_request("LEAVE_ROOM", room=parts[1])
    if command == "/users" and len(parts) <= 2:
        fields = {"room": parts[1]} if len(parts) == 2 else {}
        return new_request("LIST_USERS", **fields)
    if command == "/say" and len(parts) == 3:
        room, content = parts[1], parts[2]
        return new_request("SEND_MESSAGE", room=room, content=content)
    if command == "/history" and 2 <= len(parts) <= 3:
        fields: dict[str, Any] = {"room": parts[1]}
        if len(parts) == 3:
            try:
                fields["limit"] = int(parts[2])
            except ValueError:
                return None
        return new_request("HISTORY", **fields)
    return None
