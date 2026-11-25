import asyncio
import re
from typing import TYPE_CHECKING

from domain.errors import ChatError
from domain.user import User

if TYPE_CHECKING:
    from server.client_session import ClientSession


USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_]{3,20}\Z")


class ConnectionManager:
    def __init__(self) -> None:
        self._users_by_key: dict[str, User] = {}
        self._sessions_by_key: dict[str, "ClientSession"] = {}
        self._keys_by_session: dict["ClientSession", str] = {}
        self._lock = asyncio.Lock()

    async def register(self, session: "ClientSession", username: str) -> User:
        if not USERNAME_PATTERN.fullmatch(username):
            raise ChatError("INVALID_USERNAME", "El nombre debe tener 3-20 caracteres alfanuméricos o _")

        key = username.casefold()
        async with self._lock:
            if session in self._keys_by_session:
                raise ChatError("ALREADY_CONNECTED", "La sesión ya tiene un usuario")
            if key in self._users_by_key:
                raise ChatError("USERNAME_TAKEN", "El nombre de usuario ya está conectado")
            user = User.create(username)
            self._users_by_key[key] = user
            self._sessions_by_key[key] = session
            self._keys_by_session[session] = key
            return user

    async def unregister(self, session: "ClientSession") -> User | None:
        async with self._lock:
            key = self._keys_by_session.pop(session, None)
            if key is None:
                return None
            self._sessions_by_key.pop(key, None)
            return self._users_by_key.pop(key, None)

    async def user_for(self, session: "ClientSession") -> User | None:
        async with self._lock:
            key = self._keys_by_session.get(session)
            return self._users_by_key.get(key) if key is not None else None

    async def list_users(self) -> list[str]:
        async with self._lock:
            return sorted(user.username for user in self._users_by_key.values())

    async def sessions_for(self, usernames: list[str]) -> list["ClientSession"]:
        async with self._lock:
            sessions: list["ClientSession"] = []
            for username in usernames:
                session = self._sessions_by_key.get(username.casefold())
                if session is not None:
                    sessions.append(session)
            return sessions

    async def sessions(self) -> list["ClientSession"]:
        async with self._lock:
            return list(self._sessions_by_key.values())
