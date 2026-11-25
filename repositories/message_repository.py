import sqlite3
from contextlib import closing
from datetime import datetime

from domain.message import Message
from infrastructure.database import Database


class MessageRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def save(self, message: Message) -> None:
        await self.database.run(
            self._save_sync,
            message.room,
            message.username,
            message.content,
            message.timestamp.isoformat(),
        )

    async def history(self, room: str, limit: int) -> list[Message]:
        rows = await self.database.run(self._history_sync, room, limit)
        return [
            Message(
                room=row["room_name"],
                username=row["username"],
                content=row["content"],
                timestamp=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def _save_sync(self, room: str, username: str, content: str, created_at: str) -> None:
        with closing(self.database.connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO messages (room_name, username, content, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (room, username, content, created_at),
                )

    def _history_sync(self, room: str, limit: int) -> list[sqlite3.Row]:
        with closing(self.database.connect()) as connection:
            rows = connection.execute(
                """
                SELECT room_name, username, content, created_at
                FROM messages
                WHERE room_name = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (room, limit),
            ).fetchall()
            return list(reversed(rows))
