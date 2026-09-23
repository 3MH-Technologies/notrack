"""Typed SSE events emitted by the dispatch endpoint.

The wire format is JSON-per-``data:`` line. Every event carries a ``type``
discriminator so it can be serialised back to wire format with
:func:`dataclasses.asdict` or :func:`to_dict` — handy when proxying the
stream to a browser.

Wire → SDK mapping:

============================  ==========================================
``chat_meta``                 :class:`ChatMeta`
``thinking``                  :class:`Thinking`
``delta``                     :class:`Delta`
``message`` / ``consensus``   :class:`Delta` (fallback) + :class:`TurnEnd`
``error``                     :class:`ErrorEvent`
``ctx_cut`` / ``busy``        :class:`Notice`
============================  ==========================================
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

__all__ = [
    "ChatMeta",
    "Delta",
    "ErrorEvent",
    "Notice",
    "StreamEvent",
    "Thinking",
    "TurnEnd",
    "to_dict",
]


@dataclass(frozen=True, slots=True)
class ChatMeta:
    """First event of a stream: assigns (or echoes) the server-side chat id."""

    chat_id: str | None
    type: Literal["chat_meta"] = "chat_meta"


@dataclass(frozen=True, slots=True)
class Thinking:
    """A model is preparing a turn. ``speaker`` is the model code (A/B/C/F)."""

    speaker: str | None
    type: Literal["thinking"] = "thinking"


@dataclass(frozen=True, slots=True)
class Delta:
    """Incremental text chunk — append it to the visible reply."""

    text: str
    type: Literal["delta"] = "delta"


@dataclass(frozen=True, slots=True)
class TurnEnd:
    """One speaker finished its turn (Synthesis mode emits several per reply)."""

    type: Literal["turn_end"] = "turn_end"


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    """Upstream reported an error. Raised by :meth:`NotrackClient.complete`,
    but yielded as an event by :meth:`NotrackClient.stream` so streaming
    callers can decide how to surface it."""

    message: str
    code: str | None = None
    type: Literal["error"] = "error"


@dataclass(frozen=True, slots=True)
class Notice:
    """Non-fatal information: ``ctx_cut`` (context trimmed) or ``busy``."""

    kind: str
    message: str
    type: Literal["notice"] = "notice"


#: Every event the stream can produce.
StreamEvent = ChatMeta | Thinking | Delta | TurnEnd | ErrorEvent | Notice


def to_dict(event: StreamEvent) -> dict[str, Any]:
    """Serialise an event back to its wire (JSON-ready) representation."""
    return asdict(event)
