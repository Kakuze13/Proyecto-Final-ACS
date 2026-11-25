import asyncio
import logging
from typing import TYPE_CHECKING, Any

from server.connection_manager import ConnectionManager
from services.room_service import RoomService

if TYPE_CHECKING:
    from server.client_session import ClientSession


logger = logging.getLogger(__name__)


class EventManager:
    def __init__(self, connections: ConnectionManager, rooms: RoomService) -> None:
        self.connections = connections
        self.rooms = rooms

    async def publish_global(self, event: dict[str, Any]) -> None:
        sessions = await self.connections.sessions()
        await self._deliver(sessions, event)

    async def publish_room(self, room: str, event: dict[str, Any]) -> None:
        members = await self.rooms.list_members(room)
        sessions = await self.connections.sessions_for(members)
        await self._deliver(sessions, event)

    async def _deliver(
        self,
        sessions: list["ClientSession"],
        event: dict[str, Any],
    ) -> None:
        results = await asyncio.gather(
            *(session.send_event(event) for session in sessions),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.warning("No se pudo distribuir %s: %s", event.get("type"), result)
