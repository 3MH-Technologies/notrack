"""Shared fixtures: offline httpx MockTransport factories."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

import httpx
import pytest

from notrack import NotrackClient, NotrackConfig


def sse_bytes(events: Sequence[dict[str, Any]]) -> bytes:
    """Serialise event dicts into an SSE ``data:`` payload."""
    return b"".join(f"data: {json.dumps(e)}\n\n".encode() for e in events)


def make_transport(
    events: Sequence[dict[str, Any]] | None = None,
    status: int = 200,
    *,
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
) -> httpx.MockTransport:
    """Build a MockTransport that replays *events* (or delegates to *handler*)."""

    def default(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            headers={"content-type": "text/event-stream"},
            content=sse_bytes(events or []),
        )

    return httpx.MockTransport(handler or default)


def make_client(
    events: Sequence[dict[str, Any]] | None = None,
    status: int = 200,
    *,
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
    config: NotrackConfig | None = None,
) -> NotrackClient:
    """A NotrackClient whose HTTP layer never leaves the process."""
    return NotrackClient(
        config=config or NotrackConfig(),
        transport=make_transport(events, status, handler=handler),
    )


@pytest.fixture
def replay() -> Callable[..., NotrackClient]:
    """Fixture wrapper around :func:`make_client`."""
    return make_client
