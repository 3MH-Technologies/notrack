"""Exception hierarchy for the NoTrack SDK.

Every error raised by the SDK derives from :class:`NotrackError`, so callers
can catch a single base class:

    try:
        await client.complete("hi")
    except NotrackError as exc:
        log.warning("notrack failed (code=%s): %s", exc.code, exc)
"""

from __future__ import annotations

__all__ = [
    "NotrackAPIError",
    "NotrackConfigError",
    "NotrackError",
    "NotrackRateLimitError",
    "NotrackTransportError",
]


class NotrackError(Exception):
    """Base class for every error raised by the SDK."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class NotrackConfigError(NotrackError):
    """Invalid configuration (base URL, limits, credentials)."""


class NotrackRateLimitError(NotrackError):
    """Rate limit still enforced after every retry attempt."""


class NotrackTransportError(NotrackError):
    """Network-level failure after every retry attempt."""


class NotrackAPIError(NotrackError):
    """Non-200 response from the dispatch endpoint."""

    def __init__(self, message: str, status_code: int, code: str | None = None) -> None:
        super().__init__(message, code=code)
        self.status_code = status_code
