from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Message:
    room: str
    username: str
    content: str
    timestamp: datetime

    @classmethod
    def create(cls, room: str, username: str, content: str) -> "Message":
        return cls(room, username, content, datetime.now(timezone.utc))

    def to_event(self) -> dict[str, str]:
        return {
            "type": "CHAT_MESSAGE",
            **self.to_dict(),
        }

    def to_dict(self) -> dict[str, str]:
        return {
            "room": self.room,
            "username": self.username,
            "content": self.content,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
        }
