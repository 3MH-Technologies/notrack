"""Async streaming client for the NoTrack dispatch API.

Every chat reply goes through ``POST /api/dispatch`` and comes back as an
SSE stream — that's what keeps UIs feeling instant.

Design notes:

* One :class:`NotrackClient` per process is enough; it owns a lazily built
  :class:`httpx.AsyncClient` (connection pooling + a persistent cookie jar).
* Auth is cookie-based: set ``NOTRACK_COOKIE`` (format ``"k1=v1; k2=v2"``)
  and the client attaches it to every request. Cookies are never logged.
* Retries are automatic and bounded: linear backoff on HTTP 429 / in-stream
  ``ratelimit`` errors, plus transport-level retries for transient network
  failures.
* The client accepts an optional ``transport`` so tests (and air-gapped
  deployments) can swap the HTTP layer without monkeypatching.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

import httpx

from .config import NotrackConfig
from .events import ChatMeta, Delta, ErrorEvent, Notice, StreamEvent, Thinking, TurnEnd
from .exceptions import (
    NotrackAPIError,
    NotrackError,
    NotrackRateLimitError,
    NotrackTransportError,
)
from .models import normalize_model, normalize_persona

__all__ = [
    "NotrackClient",
    "count_tokens",
    "get_client",
]

log = logging.getLogger(__name__)

#: HTTP status codes with meaning in the dispatch protocol.
_HTTP_OK = 200
_HTTP_TOO_MANY_REQUESTS = 429

#: Hard cap on transport-level (network) retries per dispatch.
_TRANSPORT_MAX_ATTEMPTS = 3


class _InStreamRateLimit(Exception):
    """Internal signal: upstream reported a rate limit mid-stream."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotrackClient:
    """Process-wide async client for ``/api/dispatch``.

    Args:
        config: Settings; defaults to :meth:`NotrackConfig.from_env`.
        transport: Optional httpx transport (tests / custom networking).
    """

    def __init__(
        self,
        config: NotrackConfig | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config if config is not None else NotrackConfig.from_env()
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    @property
    def config(self) -> NotrackConfig:
        """The active configuration."""
        return self._config

    async def _http(self) -> httpx.AsyncClient:
        """Build (once) and return the shared httpx client."""
        async with self._lock:
            if self._client is None:
                cfg = self._config
                client = httpx.AsyncClient(
                    base_url=cfg.base_url,
                    timeout=httpx.Timeout(cfg.timeout, connect=cfg.connect_timeout),
                    headers={"User-Agent": cfg.user_agent, "Accept-Encoding": "identity"},
                    follow_redirects=True,
                    transport=self._transport,
                )
                for raw_pair in cfg.cookie.split(";"):
                    pair = raw_pair.strip()
                    if "=" in pair:
                        key, value = pair.split("=", 1)
                        client.cookies.set(key.strip(), value.strip())
                self._client = client
            return self._client

    async def aclose(self) -> None:
        """Close the underlying HTTP client (idempotent)."""
        async with self._lock:
            if self._client is not None:
                await self._client.aclose()
                self._client = None

    async def __aenter__(self) -> NotrackClient:
        await self._http()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    def _build_body(
        self,
        user_input: str,
        *,
        chat_id: str | None,
        model: str | None,
        persona: str | None,
        max_turns: int | None,
        attachments: list[str] | None,
        regenerate: bool,
        edit: bool,
        edit_mid: str | None,
        via: str,
    ) -> dict[str, Any]:
        """Assemble the dispatch payload, normalising model/persona codes."""
        cfg = self._config
        return {
            "user_input": user_input,
            "mode": "usual",
            "model": normalize_model(model) if model is not None else cfg.default_model,
            "persona": normalize_persona(persona) if persona is not None else cfg.default_persona,
            "max_turns": max_turns if max_turns is not None else cfg.max_turns,
            "chat_id": chat_id,
            "attachments": attachments or [],
            "regenerate": regenerate,
            "edit": edit,
            "edit_mid": edit_mid,
            "via": via,
        }

    @staticmethod
    async def _data_events(resp: httpx.Response) -> AsyncIterator[dict[str, Any]]:
        """Yield parsed JSON payloads from SSE ``data:`` lines.

        Malformed lines are logged at DEBUG and skipped — one bad line
        never kills a stream.
        """
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                log.debug("notrack: skipping malformed SSE line")

    async def _parse_sse(self, resp: httpx.Response) -> AsyncIterator[StreamEvent]:
        """Translate upstream payloads into typed events.

        Raises:
            _InStreamRateLimit: when upstream signals ``ratelimit`` — the
                public :meth:`stream` loop converts that into a bounded retry.
        """
        turn_had_delta = False
        async for ev in self._data_events(resp):
            match ev.get("type"):
                case "chat_meta":
                    yield ChatMeta(chat_id=ev.get("chat_id"))
                case "thinking":
                    turn_had_delta = False
                    yield Thinking(speaker=ev.get("speaker"))
                case "delta":
                    chunk = ev.get("chunk", "")
                    if chunk:
                        turn_had_delta = True
                        yield Delta(text=chunk)
                case "message" | "consensus":
                    # Fallback: full content when no deltas preceded it.
                    content = ev.get("content", "")
                    if content and not turn_had_delta:
                        yield Delta(text=content)
                    turn_had_delta = False
                    yield TurnEnd()
                case "error":
                    if ev.get("code") == "ratelimit":
                        raise _InStreamRateLimit(ev.get("content") or "rate limited")
                    yield ErrorEvent(message=ev.get("content", ""), code=ev.get("code"))
                case "ctx_cut":
                    yield Notice(kind="ctx_cut", message="")
                case "busy":
                    yield Notice(kind="busy", message=ev.get("why", ""))
                case _:
                    log.debug("notrack: unknown event type %r", ev.get("type"))

    async def _raise_for_status(self, resp: httpx.Response) -> None:
        """Raise :class:`NotrackAPIError` for non-200 responses."""
        if resp.status_code == _HTTP_OK:
            return
        raw_body = (await resp.aread()).decode("utf-8", "replace")
        try:
            data = json.loads(raw_body)
            msg = data.get("error") or data.get("message") or raw_body
        except json.JSONDecodeError:
            msg = raw_body
        raise NotrackAPIError(f"HTTP {resp.status_code}: {msg}", status_code=resp.status_code)

    async def stream(
        self,
        user_input: str,
        *,
        chat_id: str | None = None,
        model: str | None = None,
        persona: str | None = None,
        max_turns: int | None = None,
        attachments: list[str] | None = None,
        regenerate: bool = False,
        edit: bool = False,
        edit_mid: str | None = None,
        via: str = "typed",
    ) -> AsyncIterator[StreamEvent]:
        """Yield typed SSE events from ``/api/dispatch``.

        Unknown model/persona values silently fall back to the configured
        defaults. Rate limits and transient network errors are retried
        internally with bounded backoff; permanent failures raise
        :class:`NotrackError` subclasses.

        Args:
            user_input: The user's message.
            chat_id: Continue an existing server-side chat (``None`` = new).
            model: Model code (``A``/``B``/``C``/``F``); defaults to config.
            persona: Persona name; defaults to config.
            max_turns: Agent turns for this dispatch; defaults to config.
            attachments: Attachment references forwarded upstream.
            regenerate: Re-answer the last user message instead of appending.
            edit: Replace an earlier user message (with ``edit_mid``).
            edit_mid: Id of the message being edited.
            via: Provenance tag forwarded upstream (``typed``/``api``/...).

        Yields:
            Typed events — see :mod:`notrack.events`.
        """
        cfg = self._config
        body = self._build_body(
            user_input,
            chat_id=chat_id,
            model=model,
            persona=persona,
            max_turns=max_turns,
            attachments=attachments,
            regenerate=regenerate,
            edit=edit,
            edit_mid=edit_mid,
            via=via,
        )

        attempt = 0
        while True:
            attempt += 1
            client = await self._http()
            try:
                async with client.stream("POST", "/api/dispatch", json=body) as resp:
                    if resp.status_code == _HTTP_TOO_MANY_REQUESTS:
                        if attempt >= cfg.max_attempts:
                            raise NotrackRateLimitError(
                                "rate limit exceeded; try again in a minute",
                                code="ratelimit",
                            )
                        wait = attempt * cfg.rate_limit_backoff
                        log.warning("notrack 429; retrying in %ss (attempt %s)", wait, attempt)
                        await asyncio.sleep(wait)
                        continue
                    await self._raise_for_status(resp)
                    async for event in self._parse_sse(resp):
                        yield event
            except _InStreamRateLimit as exc:
                if attempt >= cfg.max_attempts:
                    raise NotrackRateLimitError(exc.message, code="ratelimit") from exc
                wait = attempt * cfg.rate_limit_backoff
                log.warning("notrack ratelimit event; retrying in %ss", wait)
                await asyncio.sleep(wait)
                continue
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                if attempt >= _TRANSPORT_MAX_ATTEMPTS:
                    raise NotrackTransportError(f"connection error: {exc}") from exc
                log.warning("notrack transport error (%s); retrying", exc)
                await asyncio.sleep(attempt * cfg.transport_backoff)
                continue
            return

    async def complete(
        self,
        user_input: str,
        **kwargs: Any,
    ) -> tuple[str, str | None]:
        """Non-streaming helper: collect the full reply.

        Returns:
            ``(text, chat_id)`` — the concatenated reply and the server-side
            chat id to pass on the next turn (``None`` if unchanged).

        Raises:
            NotrackError: On upstream error events or exhausted retries.
        """
        parts: list[str] = []
        chat_id: str | None = None
        async for ev in self.stream(user_input, **kwargs):
            match ev:
                case Delta(text=text):
                    parts.append(text)
                case TurnEnd():
                    parts.append("\n\n")
                case ChatMeta(chat_id=meta_id):
                    chat_id = meta_id or chat_id
                case ErrorEvent(code=code, message=message):
                    raise NotrackError(message or "unknown error", code=code)
                case _:
                    continue
        return "".join(parts).strip(), chat_id


@lru_cache(maxsize=1)
def get_client() -> NotrackClient:
    """Return the process-wide shared client (keeps the cookie jar warm).

    The client is created on first use from ``NOTRACK_*`` environment
    variables. Call ``await client.aclose()`` on shutdown if you need to
    release sockets deterministically.
    """
    return NotrackClient()


def count_tokens(text: str) -> int:
    """Cheap token estimate (~4 chars per token). Never returns less than 1."""
    return max(1, len(text) // 4)
