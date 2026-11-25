import asyncio
import re
from datetime import datetime

from domain.errors import ChatError
from domain.room import Room
from repositories.room_repository import RoomRepository


ROOM_PATTERN = re.compile(r"[a-z0-9_-]{1,32}\Z")


class RoomService:
    def __init__(self, repository: RoomRepository | None = None) -> None:
        self._rooms: dict[str, Room] = {}
        self._lock = asyncio.Lock()
        self.repository = repository

    async def load(self) -> None:
        if self.repository is None:
            return
        records = await self.repository.list_all()
        rooms = {
            record["name"]: Room(
                name=record["name"],
                created_by=record["created_by"],
                created_at=datetime.fromisoformat(record["created_at"]),
            )
            for record in records
        }
        async with self._lock:
            self._rooms = rooms

    async def create(self, name: str, username: str) -> Room:
        if not ROOM_PATTERN.fullmatch(name):
            raise ChatError("INVALID_ROOM", "La sala debe usar 1-32 letras minúsculas, dígitos, _ o -")
        async with self._lock:
            if name in self._rooms:
                raise ChatError("ROOM_EXISTS", "La sala ya existe")
            room = Room(name=name, created_by=username, members={username})
        if self.repository is not None:
            await self.repository.save(name, username, room.created_at)
        async with self._lock:
            self._rooms[name] = room
        return room

    async def list_rooms(self) -> list[dict[str, int | str]]:
        async with self._lock:
            return [
                {"room": room.name, "members_count": len(room.members)}
                for room in sorted(self._rooms.values(), key=lambda item: item.name)
            ]

    async def join(self, name: str, username: str) -> None:
        async with self._lock:
            room = self._rooms.get(name)
            if room is None:
                raise ChatError("ROOM_NOT_FOUND", "La sala no existe")
            if username in room.members:
                raise ChatError("ALREADY_IN_ROOM", "El usuario ya pertenece a la sala")
            room.members.add(username)

    async def leave(self, name: str, username: str) -> None:
        async with self._lock:
            room = self._rooms.get(name)
            if room is None:
                raise ChatError("ROOM_NOT_FOUND", "La sala no existe")
            if username not in room.members:
                raise ChatError("NOT_IN_ROOM", "El usuario no pertenece a la sala")
            room.members.remove(username)

    async def list_members(self, name: str) -> list[str]:
        async with self._lock:
            room = self._rooms.get(name)
            if room is None:
                raise ChatError("ROOM_NOT_FOUND", "La sala no existe")
            return sorted(room.members, key=str.casefold)

    async def remove_user(self, username: str) -> None:
        async with self._lock:
            for room in self._rooms.values():
                room.members.discard(username)
