import asyncio
from typing import Any

from infrastructure.protocol import (
    ProtocolError,
    decode_frame,
    encode_message,
    validate_request,
)


class TcpClient:
    def __init__(self) -> None:
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._reader_task: asyncio.Task[None] | None = None

    async def connect(self, host: str, port: int) -> None:
        self.reader, self.writer = await asyncio.open_connection(host, port, limit=65_536)
        self._reader_task = asyncio.create_task(self._read_loop())

    async def request(self, message: dict[str, Any]) -> dict[str, Any]:
        if self.writer is None or self.writer.is_closing():
            raise ConnectionError("El cliente no está conectado")
        validate_request(message)
        request_id = message["request_id"]
        if request_id in self._pending:
            raise ValueError("request_id ya está en uso")

        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            self.writer.write(encode_message(message))
            await self.writer.drain()
            return await asyncio.wait_for(future, timeout=30)
        finally:
            self._pending.pop(request_id, None)
            if not future.done():
                future.cancel()

    async def close(self) -> None:
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()
        if self._reader_task is not None:
            self._reader_task.cancel()
            await asyncio.gather(self._reader_task, return_exceptions=True)

    async def _read_loop(self) -> None:
        if self.reader is None:
            return
        try:
            while True:
                message = decode_frame(await self.reader.readuntil(b"\n"))
                request_id = message.get("request_id")
                if isinstance(request_id, str):
                    future = self._pending.get(request_id)
                    if future is not None and not future.done():
                        future.set_result(message)
                else:
                    await self.events.put(message)
        except asyncio.CancelledError:
            raise
        except (asyncio.IncompleteReadError, ConnectionError, ProtocolError):
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(ConnectionError("El servidor cerró la conexión"))
        finally:
            if self.writer is not None and not self.writer.is_closing():
                self.writer.close()
