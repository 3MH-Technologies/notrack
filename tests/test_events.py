"""Unit tests for the SSE event model and serialisation (offline)."""

from __future__ import annotations

import dataclasses

import pytest

from notrack import (
    ChatMeta,
    Delta,
    ErrorEvent,
    Notice,
    StreamEvent,
    Thinking,
    TurnEnd,
    to_dict,
)


def test_discriminators_match_wire_format() -> None:
    assert to_dict(ChatMeta(chat_id="c1")) == {"type": "chat_meta", "chat_id": "c1"}
    assert to_dict(Thinking(speaker="A")) == {"type": "thinking", "speaker": "A"}
    assert to_dict(Delta(text="hi")) == {"type": "delta", "text": "hi"}
    assert to_dict(TurnEnd()) == {"type": "turn_end"}
    assert to_dict(ErrorEvent(message="no", code="denied")) == {
        "type": "error",
        "code": "denied",
        "message": "no",
    }
    assert to_dict(Notice(kind="busy", message="try later")) == {
        "type": "notice",
        "kind": "busy",
        "message": "try later",
    }


def test_error_event_defaults_to_none_code() -> None:
    ev = ErrorEvent(message="boom")
    assert ev.code is None
    assert to_dict(ev) == {"type": "error", "code": None, "message": "boom"}


def test_events_are_immutable() -> None:
    ev = Delta(text="a")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.text = "b"  # type: ignore[misc]


def test_stream_event_union_accepts_all_kinds() -> None:
    events: list[StreamEvent] = [
        ChatMeta(chat_id=None),
        Thinking(speaker=None),
        Delta(text=""),
        TurnEnd(),
        ErrorEvent(message="x"),
        Notice(kind="ctx_cut", message=""),
    ]
    assert len(events) == 6
