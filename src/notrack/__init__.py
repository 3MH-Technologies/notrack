"""NoTrack — official Python SDK for the NoTrack dispatch API.

Streaming SSE chat, typed events, bounded retries, cookie auth. Pure
``httpx``; no API keys, no vendor branding surprises.

Quickstart::

    import asyncio
    from notrack import NotrackClient, Delta

    async def main() -> None:
        async with NotrackClient() as client:
            async for ev in client.stream("hello"):
                if isinstance(ev, Delta):
                    print(ev.text, end="", flush=True)

    asyncio.run(main())

Credits: © 3MH Technologies — https://3mh.pages.dev/ — https://t.me/j49_c
"""

from __future__ import annotations

from ._version import __version__
from .client import NotrackClient, count_tokens, get_client
from .config import DEFAULT_BASE_URL, NotrackConfig
from .events import (
    ChatMeta,
    Delta,
    ErrorEvent,
    Notice,
    StreamEvent,
    Thinking,
    TurnEnd,
    to_dict,
)
from .exceptions import (
    NotrackAPIError,
    NotrackConfigError,
    NotrackError,
    NotrackRateLimitError,
    NotrackTransportError,
)
from .models import (
    DEFAULT_MODEL,
    DEFAULT_PERSONA,
    MODEL_DESCRIPTIONS,
    MODELS,
    PERSONAS,
    normalize_model,
    normalize_persona,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "DEFAULT_PERSONA",
    "MODELS",
    "MODEL_DESCRIPTIONS",
    "PERSONAS",
    "ChatMeta",
    "Delta",
    "ErrorEvent",
    "Notice",
    "NotrackAPIError",
    "NotrackClient",
    "NotrackConfig",
    "NotrackConfigError",
    "NotrackError",
    "NotrackRateLimitError",
    "NotrackTransportError",
    "StreamEvent",
    "Thinking",
    "TurnEnd",
    "__version__",
    "count_tokens",
    "get_client",
    "normalize_model",
    "normalize_persona",
    "to_dict",
]
