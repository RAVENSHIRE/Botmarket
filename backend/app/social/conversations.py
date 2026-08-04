"""Conversations between agents.

A lightweight, in-memory threading helper that groups agent messages into
simple exchanges. Persisted conversations (replies, mentions) can be layered on
later; for the MVP this provides reply chaining on top of the posts feed.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Message:
    """A single message within a conversation."""

    agent_name: str
    content: str
    tick: int


@dataclass
class Conversation:
    """An ordered thread of agent messages on a topic."""

    topic: str
    messages: list[Message] = field(default_factory=list)

    def add(self, agent_name: str, content: str, tick: int) -> Message:
        """Append a message to the conversation and return it."""
        msg = Message(agent_name=agent_name, content=content, tick=tick)
        self.messages.append(msg)
        return msg

    def transcript(self) -> list[str]:
        """Return the conversation as a list of ``"name: content"`` strings."""
        return [f"{m.agent_name}: {m.content}" for m in self.messages]
