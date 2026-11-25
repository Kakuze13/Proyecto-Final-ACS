from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

from domain.errors import ChatError
from domain.message import Message
from services.event_manager import EventManager
from server.connection_manager import ConnectionManager
from repositories.message_repository import MessageRepository
from services.room_service import RoomService

if TYPE_CHECKING:
    from server.client_session import ClientSession


logger = logging.getLogger(__name__)
MAX_MESSAGE_LENGTH = 2_000


class ChatService:
    def __init__(
        self,
        connections: ConnectionManager,
        rooms: RoomService,
        events: EventManager,
        messages: MessageRepository,
    ) -> None:
        self.connections = connections
        self.rooms = rooms
        self.events = events
        self.messages = messages

    async def send_message(
        self,
        session: ClientSession,
        room_name: str,
        content: str,
    ) -> Message:
        user = await self.connections.user_for(session)
        if user is None:
            raise ChatError("NOT_CONNECTED", "La sesión no está identificada")
        if (
            not content
            or len(content) > MAX_MESSAGE_LENGTH
            or "\x00" in content
            or any(0xD800 <= ord(character) <= 0xDFFF for character in content)
        ):
            raise ChatError("INVALID_CONTENT", "El mensaje debe tener 1-2000 caracteres válidos")

        members = await self.rooms.list_members(room_name)
        if user.username not in members:
            raise ChatError("NOT_IN_ROOM", "Debe pertenecer a la sala para enviar mensajes")

        message = Message.create(room_name, user.username, content)
        try:
            await self.messages.save(message)
        except sqlite3.Error as error:
            logger.exception("No se pudo persistir el mensaje")
            raise ChatError("INTERNAL_ERROR", "No se pudo guardar el mensaje") from error
        await self.events.publish_room(room_name, message.to_event())
        return message

    async def history(
        self,
        session: ClientSession,
        room_name: str,
        limit: int,
    ) -> list[Message]:
        user = await self.connections.user_for(session)
        if user is None:
            raise ChatError("NOT_CONNECTED", "La sesión no está identificada")
        members = await self.rooms.list_members(room_name)
        if user.username not in members:
            raise ChatError("NOT_IN_ROOM", "Debe pertenecer a la sala para consultar el historial")
        try:
            return await self.messages.history(room_name, limit)
        except sqlite3.Error as error:
            logger.exception("No se pudo consultar el historial")
            raise ChatError("INTERNAL_ERROR", "No se pudo consultar el historial") from error
