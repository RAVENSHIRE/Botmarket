"""Agent memory.

A bounded, in-process memory store holding recent observations and the agent's
own actions. Kept deliberately simple (a ring buffer) but with a clear
interface so it can later be backed by a vector store or database.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class MemoryEntry:
    """A single remembered item."""

    tick: int
    kind: str  # e.g. "observation", "action", "message"
    content: str


@dataclass
class Memory:
    """Short-term rolling memory for an agent.

    Attributes:
        capacity: Maximum number of entries retained.
    """

    capacity: int = 50
    _entries: deque[MemoryEntry] = field(default_factory=deque)

    def __post_init__(self) -> None:
        # Rebind the deque with the configured maxlen (ring-buffer semantics).
        self._entries = deque(self._entries, maxlen=self.capacity)

    def remember(self, tick: int, kind: str, content: str) -> None:
        """Store a new memory entry, evicting the oldest if at capacity."""
        self._entries.append(MemoryEntry(tick=tick, kind=kind, content=content))

    def recent(self, limit: int = 10) -> list[MemoryEntry]:
        """Return the most recent ``limit`` entries (newest last)."""
        return list(self._entries)[-limit:]

    def __len__(self) -> int:
        return len(self._entries)
