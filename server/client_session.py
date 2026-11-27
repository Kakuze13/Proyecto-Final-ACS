import asyncio
import logging
from typing import Any

from domain.errors import ChatError
from infrastructure.protocol import ProtocolError, decode_frame, encode_message, validate_request
from server.connection_manager import ConnectionManager
from services.chat_service import ChatService
from services.event_manager import EventManager
from services.room_service import RoomService


logger = logging.getLogger(__name__)


class ClientSession:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        connections: ConnectionManager,
        rooms: RoomService,
        chat: ChatService,
        events: EventManager,
        queue_size: int = 100,
        enqueue_timeout: float = 0.1,
        read_timeout: float = 300,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.connections = connections
        self.rooms = rooms
        self.chat = chat
        self.events = events
        self.enqueue_timeout = enqueue_timeout
        self.read_timeout = read_timeout
        self._outgoing: asyncio.Queue[bytes] = asyncio.Queue(maxsize=queue_size)
        self._writer_task: asyncio.Task[None] | None = None

    async def serve(self) -> None:
        self._writer_task = asyncio.create_task(self._write_loop())
        try:
            while True:
                frame = await asyncio.wait_for(
                    self.reader.readuntil(b"\n"),
                    timeout=self.read_timeout,
                )
                message = decode_frame(frame)
                try:
                    validate_request(message)
                except ProtocolError as error:
                    request_id = message.get("request_id")
                    if not isinstance(request_id, str):
                        request_id = None
                    await self._send_error(request_id, error.code, str(error))
                    continue
                if not await self._handle_request(message):
                    await self._flush_outgoing()
                    break
        except asyncio.IncompleteReadError:
            pass
        except (asyncio.LimitOverrunError, ProtocolError) as error:
            logger.info("Trama inválida desde %s: %s", self.writer.get_extra_info("peername"), error)
            try:
                code = error.code if isinstance(error, ProtocolError) else "MESSAGE_TOO_LARGE"
                await self._send_error(None, code, str(error))
                await self._flush_outgoing()
            except (ChatError, ConnectionError) as send_error:
                logger.info("No se pudo responder al frame inválido: %s", send_error)
        except asyncio.TimeoutError:
            logger.info("Timeout de lectura para %s", self.writer.get_extra_info("peername"))
        except ChatError as error:
            logger.warning("Cerrando sesión por saturación: %s", error)
        except ConnectionError:
            logger.info("Conexión cerrada durante I/O")
        finally:
            user = await self.connections.unregister(self)
            if user is not None:
                await self.rooms.remove_user(user.username)
                await self.events.publish_global(
                    {"type": "USER_DISCONNECTED", "username": user.username}
                )
                logger.info("Sesión retirada: %s", user.username)
            if self._writer_task is not None:
                self._writer_task.cancel()
                await asyncio.gather(self._writer_task, return_exceptions=True)

    async def _flush_outgoing(self) -> None:
        try:
            await asyncio.wait_for(self._outgoing.join(), timeout=self.enqueue_timeout)
        except asyncio.TimeoutError:
            self.writer.close()

    async def _handle_request(self, message: dict[str, Any]) -> bool:
        request_id = message["request_id"]
        current_user = await self.connections.user_for(self)

        try:
            if current_user is None:
                if message["type"] != "CONNECT":
                    raise ChatError("NOT_CONNECTED", "Primero debe identificarse con CONNECT")
                user = await self.connections.register(self, message["username"])
                await self._send_success(request_id, "CONNECT", {"username": user.username})
                await self.events.publish_global(
                    {"type": "USER_CONNECTED", "username": user.username}
                )
                return True

            if message["type"] == "CONNECT":
                raise ChatError("ALREADY_CONNECTED", "La sesión ya está identificada")
            if message["type"] == "DISCONNECT":
                await self._send_success(request_id, "DISCONNECT")
                return False
            if message["type"] == "CREATE_ROOM":
                room = await self.rooms.create(message["room"], current_user.username)
                await self.events.publish_global(
                    {
                        "type": "ROOM_CREATED",
                        "room": room.name,
                        "created_by": current_user.username,
                    }
                )
                await self._send_success(request_id, "CREATE_ROOM", {"room": room.name})
                return True
            if message["type"] == "DELETE_ROOM":
                room_name = message["room"]
                await self.rooms.delete(room_name, current_user.username)
                await self.events.publish_global(
                    {
                        "type": "ROOM_DELETED",
                        "room": room_name,
                        "deleted_by": current_user.username,
                    }
                )
                await self._send_success(
                    request_id,
                    "DELETE_ROOM",
                    {"room": room_name},
                )
                return True
            if message["type"] == "LIST_ROOMS":
                rooms = await self.rooms.list_rooms()
                await self._send_success(request_id, "LIST_ROOMS", {"rooms": rooms})
                return True
            if message["type"] == "JOIN_ROOM":
                await self.rooms.join(message["room"], current_user.username)
                await self.events.publish_room(
                    message["room"],
                    {
                        "type": "USER_JOINED",
                        "room": message["room"],
                        "username": current_user.username,
                    },
                )
                await self._send_success(request_id, "JOIN_ROOM", {"room": message["room"]})
                return True
            if message["type"] == "LEAVE_ROOM":
                await self.rooms.leave(message["room"], current_user.username)
                await self.events.publish_room(
                    message["room"],
                    {
                        "type": "USER_LEFT",
                        "room": message["room"],
                        "username": current_user.username,
                    },
                )
                await self._send_success(request_id, "LEAVE_ROOM", {"room": message["room"]})
                return True
            if message["type"] == "SEND_MESSAGE":
                chat_message = await self.chat.send_message(
                    self, message["room"], message["content"]
                )
                await self._send_success(
                    request_id,
                    "SEND_MESSAGE",
                    {"room": chat_message.room},
                )
                return True
            if message["type"] == "HISTORY":
                history = await self.chat.history(
                    self,
                    message["room"],
                    message.get("limit", 50),
                )
                response: dict[str, Any] = {
                    "type": "HISTORY_RESULT",
                    "request_id": request_id,
                    "room": message["room"],
                    "messages": [item.to_dict() for item in history],
                    "truncated": False,
                }
                while True:
                    try:
                        frame = encode_message(response)
                    except ProtocolError as error:
                        if error.code != "MESSAGE_TOO_LARGE" or not response["messages"]:
                            raise
                        response["messages"].pop(0)
                        response["truncated"] = True
                    else:
                        await self._enqueue_frame(frame)
                        break
                return True
            if message["type"] == "LIST_USERS" and "room" not in message:
                await self._send_success(
                    request_id,
                    "LIST_USERS",
                    {"users": await self.connections.list_users()},
                )
                return True
            if message["type"] == "LIST_USERS":
                members = await self.rooms.list_members(message["room"])
                await self._send_success(request_id, "LIST_USERS", {"users": members})
                return True
            raise ChatError("UNSUPPORTED_TYPE", "La operación aún no está disponible")
        except ChatError as error:
            await self._send_error(request_id, error.code, str(error))
            return True

    async def _send_success(
        self,
        request_id: str,
        operation: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        response: dict[str, Any] = {
            "type": "SUCCESS",
            "request_id": request_id,
            "operation": operation,
        }
        if data is not None:
            response["data"] = data
        await self.send_event(response)

    async def _send_error(self, request_id: str | None, code: str, message: str) -> None:
        await self.send_event(
            {"type": "ERROR", "request_id": request_id, "code": code, "message": message}
        )

    async def send_event(self, event: dict[str, Any]) -> None:
        if self.writer.is_closing():
            raise ConnectionError("La conexión ya está cerrada")
        await self._enqueue_frame(encode_message(event))

    async def _enqueue_frame(self, frame: bytes) -> None:
        if self.writer.is_closing():
            raise ConnectionError("La conexión ya está cerrada")
        try:
            await asyncio.wait_for(self._outgoing.put(frame), timeout=self.enqueue_timeout)
        except asyncio.TimeoutError as error:
            logger.warning(
                "Cola de salida saturada para %s",
                self.writer.get_extra_info("peername"),
            )
            self.writer.close()
            raise ChatError("SERVER_BUSY", "Cliente lento desconectado por saturación") from error

    async def _write_loop(self) -> None:
        try:
            while True:
                frame = await self._outgoing.get()
                try:
                    self.writer.write(frame)
                    await self.writer.drain()
                finally:
                    self._outgoing.task_done()
        except asyncio.CancelledError:
            raise
        except (ConnectionError, OSError) as error:
            logger.info("Error escribiendo al cliente: %s", error)
            self.writer.close()
