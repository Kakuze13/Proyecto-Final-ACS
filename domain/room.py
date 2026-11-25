from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Room:
    name: str
    created_by: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    members: set[str] = field(default_factory=set)
