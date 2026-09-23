"""Unit tests for the streaming client (offline, via httpx MockTransport)."""

from __future__ import annotations

import json as _json
from typing import Any

import httpx
import pytest

from conftest import make_client, sse_bytes
from notrack import (
    ChatMeta,
    Delta,
    ErrorEvent,
    Notice,
    NotrackAPIError,
    NotrackConfig,
    NotrackError,
    NotrackRateLimitError,
    NotrackTransportError,
    Thinking,
    TurnEnd,
    count_tokens,
    get_client,
)
from notrack.client import _TRANSPORT_MAX_ATTEMPTS


async def test_stream_parses_events_in_order() -> None:
    client = make_client(
        [
            {"type": "chat_meta", "chat_id": "chat-1"},
            {"type": "thinking", "speaker": "C"},
            {"type": "delta", "chunk": "Hel"},
            {"type": "delta", "chunk": "lo"},
            {"type": "message", "content": "Hello"},
        ]
    )
    events = [ev async for ev in client.stream("hi")]

    assert [type(ev) for ev in events] == [ChatMeta, Thinking, Delta, Delta, TurnEnd]
    assert isinstance(events[0], ChatMeta) and events[0].chat_id == "chat-1"
    text = "".join(ev.text for ev in events if isinstance(ev, Delta))
    assert text == "Hello"  # "message" content skipped: deltas already emitted
    await client.aclose()


async def test_message_content_used_when_no_deltas() -> None:
    client = make_client(
        [
            {"type": "thinking", "speaker": "A"},
            {"type": "message", "content": "Full answer"},
        ]
    )
    text, chat_id = await client.complete("hi")
    assert text == "Full answer"
    assert chat_id is None
    await client.aclose()


async def test_complete_returns_text_and_chat_id() -> None:
    client = make_client(
        [
            {"type": "chat_meta", "chat_id": "chat-2"},
            {"type": "delta", "chunk": "Hel"},
            {"type": "delta", "chunk": "lo"},
            {"type": "message", "content": "Hello"},
        ]
    )
    text, chat_id = await client.complete("hi")
    assert text == "Hello"
    assert chat_id == "chat-2"
    await client.aclose()


async def test_consensus_event_ends_turn_like_message() -> None:
    client = make_client([{"type": "consensus", "content": "agreed"}])
    events = [ev async for ev in client.stream("hi")]
    assert isinstance(events[0], Delta) and events[0].text == "agreed"
    assert isinstance(events[1], TurnEnd)
    await client.aclose()


async def test_error_event_yields_in_stream_but_raises_in_complete() -> None:
    events_payload = [{"type": "error", "code": "denied", "content": "no access"}]

    stream_client = make_client(events_payload)
    events = [ev async for ev in stream_client.stream("hi")]
    assert len(events) == 1
    assert isinstance(events[0], ErrorEvent)
    assert events[0].code == "denied"
    assert events[0].message == "no access"
    await stream_client.aclose()

    complete_client = make_client(events_payload)
    with pytest.raises(NotrackError, match="no access"):
        await complete_client.complete("hi")
    await complete_client.aclose()


async def test_notice_events_surface_context_cut_and_busy() -> None:
    client = make_client(
        [
            {"type": "ctx_cut"},
            {"type": "busy", "why": "queue is full"},
        ]
    )
    events = [ev async for ev in client.stream("hi")]
    assert [type(ev) for ev in events] == [Notice, Notice]
    first, second = events
    assert isinstance(first, Notice) and first.kind == "ctx_cut"
    assert isinstance(second, Notice) and second.kind == "busy"
    assert second.message == "queue is full"
    await client.aclose()


async def test_unknown_and_malformed_events_are_skipped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = (
            b'data: {"type": "mystery"}\n\ndata: {not json\n\ndata: {"type": "delta", "chunk": "ok"}\n\n'
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=payload)

    client = make_client(handler=handler)
    events = [ev async for ev in client.stream("hi")]
    assert events == [Delta(text="ok")]
    await client.aclose()


async def test_http_error_raises_api_error_with_status() -> None:
    client = make_client([{}], status=503)
    with pytest.raises(NotrackAPIError) as exc_info:
        await client.complete("hi")
    assert exc_info.value.status_code == 503
    await client.aclose()


async def test_rate_limit_429_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "slow down"})
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=sse_bytes([{"type": "delta", "chunk": "ok"}]),
        )

    client = make_client(handler=handler, config=NotrackConfig(max_attempts=5))
    text, _ = await client.complete("hi")
    assert text == "ok"
    assert calls["n"] == 2
    await client.aclose()


async def test_rate_limit_exhausts_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    client = make_client(
        [{}],
        status=429,
        config=NotrackConfig(max_attempts=3),
    )
    with pytest.raises(NotrackRateLimitError):
        await client.complete("hi")
    await client.aclose()


async def test_in_stream_ratelimit_event_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        events = (
            [{"type": "error", "code": "ratelimit", "content": "busy"}]
            if calls["n"] == 1
            else [{"type": "delta", "chunk": "done"}]
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=sse_bytes(events))

    client = make_client(handler=handler)
    text, _ = await client.complete("hi")
    assert text == "done"
    assert calls["n"] == 2
    await client.aclose()


async def test_transport_errors_retry_then_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("asyncio.sleep", _no_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = make_client(handler=handler)
    with pytest.raises(NotrackTransportError):
        await client.complete("hi")
    await client.aclose()


async def test_transport_error_recovers_on_later_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < _TRANSPORT_MAX_ATTEMPTS:
            raise httpx.ConnectError("flaky", request=request)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=sse_bytes([{"type": "delta", "chunk": "recovered"}]),
        )

    client = make_client(handler=handler)
    text, _ = await client.complete("hi")
    assert text == "recovered"
    await client.aclose()


async def test_request_body_carries_normalized_model_and_persona() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(_json.loads(request.content))
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=sse_bytes([{"type": "delta", "chunk": "x"}]),
        )

    client = make_client(handler=handler)
    _ = [ev async for ev in client.stream("hi", model="zzz", persona="unknown", max_turns=3)]
    assert seen["model"] == "C"  # invalid → default
    assert seen["persona"] == "normal"
    assert seen["max_turns"] == 3
    assert seen["user_input"] == "hi"
    await client.aclose()


async def test_cookie_is_attached_to_requests() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["cookie"] = request.headers.get("cookie", "")
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=sse_bytes([]),
        )

    client = make_client(
        handler=handler,
        config=NotrackConfig(cookie="session=abc123; theme=dark"),
    )
    _ = [ev async for ev in client.stream("hi")]
    assert "session=abc123" in seen["cookie"]
    assert "theme=dark" in seen["cookie"]
    await client.aclose()


async def test_context_manager_closes_client() -> None:
    async with make_client([{"type": "delta", "chunk": "hi"}]) as client:
        events = [ev async for ev in client.stream("x")]
        assert events
        assert client._client is not None
    assert client._client is None  # closed on exit


def test_get_client_returns_shared_singleton() -> None:
    a = get_client()
    b = get_client()
    assert a is b


def test_count_tokens_estimates_and_never_zero() -> None:
    assert count_tokens("") == 1
    assert count_tokens("abcdefgh") == 2
    assert count_tokens("a") == 1


async def _no_sleep(delay: float) -> None:
    """Sleep replacement for retry tests (instant, no wall-clock cost)."""
    return None
