import asyncio
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Callable, TypeVar


Result = TypeVar("Result")


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)

    async def initialize(self) -> None:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._initialize_sync)

    async def run(self, operation: Callable[..., Result], *args: Any) -> Result:
        return await asyncio.to_thread(operation, *args)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_sync(self) -> None:
        with closing(self.connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rooms (
                        name TEXT PRIMARY KEY,
                        created_by TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        room_name TEXT NOT NULL REFERENCES rooms(name),
                        username TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_messages_room_id ON messages(room_name, id)"
                )
