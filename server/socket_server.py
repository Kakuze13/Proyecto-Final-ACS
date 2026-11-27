import asyncio
import logging
import socket
from pathlib import Path

from infrastructure.database import Database
from repositories.message_repository import MessageRepository
from repositories.room_repository import RoomRepository
from server.client_session import ClientSession
from server.connection_manager import ConnectionManager
from services.chat_service import ChatService
from services.event_manager import EventManager
from services.room_service import RoomService


logger = logging.getLogger(__name__)


class SocketServer:
    def __init__(
        self,
        host: str,
        port: int,
        database_path: str | Path = "chatroom.db",
        max_connections: int = 100,
        queue_size: int = 100,
        enqueue_timeout: float = 0.1,
        read_timeout: float = 300,
        socket_send_buffer: int | None = None,
    ) -> None:
        if max_connections < 1:
            raise ValueError("max_connections debe ser positivo")
        if queue_size < 1:
            raise ValueError("queue_size debe ser positivo")
        if enqueue_timeout <= 0:
            raise ValueError("enqueue_timeout debe ser positivo")
        if read_timeout <= 0:
            raise ValueError("read_timeout debe ser positivo")
        if socket_send_buffer is not None and socket_send_buffer < 1:
            raise ValueError("socket_send_buffer debe ser positivo")
        self.host = host
        self.port = port
        self._database = Database(database_path)
        self._room_repository = RoomRepository(self._database)
        self._message_repository = MessageRepository(self._database)
        self.max_connections = max_connections
        self.queue_size = queue_size
        self.enqueue_timeout = enqueue_timeout
        self.read_timeout = read_timeout
        self.socket_send_buffer = socket_send_buffer
        self._server: asyncio.Server | None = None
        self._writers: set[asyncio.StreamWriter] = set()
        self._client_tasks: set[asyncio.Task[None]] = set()
        self._connections = ConnectionManager()
        self._rooms = RoomService(self._room_repository)
        self._events = EventManager(self._connections, self._rooms)
        self._chat = ChatService(
            self._connections,
            self._rooms,
            self._events,
            self._message_repository,
        )

    @property
    def sockets(self) -> list[socket.socket]:
        return list(self._server.sockets) if self._server is not None else []

    async def start(self) -> None:
        if self._server is not None:
            raise RuntimeError("El servidor ya está iniciado")
        await self._database.initialize()
        await self._rooms.load()
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
            backlog=self.max_connections,
            limit=65_536,
            reuse_address=True,
        )
        logger.info("Servidor TCP escuchando en %s:%s", self.host, self.port)

    async def serve_forever(self) -> None:
        if self._server is None:
            raise RuntimeError("El servidor no está iniciado")
        async with self._server:
            await self._server.serve_forever()

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        writers = tuple(self._writers)
        for writer in writers:
            writer.close()
        if writers:
            await asyncio.gather(
                *(writer.wait_closed() for writer in writers),
                return_exceptions=True,
            )

        tasks = tuple(self._client_tasks)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._client_tasks.add(task)

        peer = writer.get_extra_info("peername")
        if len(self._writers) >= self.max_connections:
            logger.warning("Conexiones máximas alcanzadas; rechazando %s", peer)
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError) as error:
                logger.info("Error cerrando conexión rechazada %s: %s", peer, error)
            if task is not None:
                self._client_tasks.discard(task)
            return

        self._writers.add(writer)
        logger.info("Cliente TCP conectado: %s", peer)
        try:
            if self.socket_send_buffer is not None:
                client_socket = writer.get_extra_info("socket")
                if client_socket is None:
                    raise RuntimeError("No se pudo acceder al socket TCP del cliente")
                client_socket.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_SNDBUF,
                    self.socket_send_buffer,
                )
            session = ClientSession(
                reader,
                writer,
                self._connections,
                self._rooms,
                self._chat,
                self._events,
                self.queue_size,
                self.enqueue_timeout,
                self.read_timeout,
            )
            await session.serve()
        except (ConnectionError, asyncio.IncompleteReadError):
            logger.info("Conexión TCP interrumpida: %s", peer)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError) as error:
                logger.info("Error cerrando stream de %s: %s", peer, error)
            finally:
                self._writers.discard(writer)
                if task is not None:
                    self._client_tasks.discard(task)
                logger.info("Cliente TCP desconectado: %s", peer)
