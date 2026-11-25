from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class User:
    username: str
    connected_at: datetime

    @classmethod
    def create(cls, username: str) -> "User":
        return cls(username=username, connected_at=datetime.now(timezone.utc))
