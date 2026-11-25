import sqlite3
from contextlib import closing
from datetime import datetime
import logging

from domain.errors import ChatError
from infrastructure.database import Database


logger = logging.getLogger(__name__)


class RoomRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def save(self, name: str, created_by: str, created_at: datetime) -> None:
        try:
            await self.database.run(
                self._save_sync,
                name,
                created_by,
                created_at.isoformat(),
            )
        except sqlite3.IntegrityError as error:
            raise ChatError("ROOM_EXISTS", "La sala ya existe") from error
        except sqlite3.Error as error:
            logger.exception("No se pudo guardar la sala %s", name)
            raise ChatError("INTERNAL_ERROR", "No se pudo guardar la sala") from error

    async def list_all(self) -> list[dict[str, str]]:
        return await self.database.run(self._list_all_sync)

    def _save_sync(self, name: str, created_by: str, created_at: str) -> None:
        with closing(self.database.connect()) as connection:
            with connection:
                connection.execute(
                    "INSERT INTO rooms (name, created_by, created_at) VALUES (?, ?, ?)",
                    (name, created_by, created_at),
                )

    def _list_all_sync(self) -> list[dict[str, str]]:
        with closing(self.database.connect()) as connection:
            rows = connection.execute(
                "SELECT name, created_by, created_at FROM rooms ORDER BY name"
            ).fetchall()
            return [dict(row) for row in rows]
