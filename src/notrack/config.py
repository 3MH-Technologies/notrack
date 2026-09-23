"""Client configuration.

All values can be supplied programmatically or through ``NOTRACK_*``
environment variables (identical names to the worm-ai platform ``.env``):

=====================  =====================================================
``NOTRACK_BASE``       Service base URL (default ``https://notrack.ai``)
``NOTRACK_COOKIE``     Browser-style cookie string ``"k1=v1; k2=v2"``
``NOTRACK_MODEL``      Default model code: ``A`` / ``B`` / ``C`` / ``F``
``NOTRACK_PERSONA``    Default persona name (see :data:`notrack.PERSONAS`)
``NOTRACK_MAX_TURNS``  Agent turns per dispatch (default ``6``)
``NOTRACK_TIMEOUT``    Read timeout in seconds (default ``120``)
``NOTRACK_MAX_ATTEMPTS``  Rate-limit retries (default ``5``)
=====================  =====================================================
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from .exceptions import NotrackConfigError
from .models import DEFAULT_MODEL, DEFAULT_PERSONA, normalize_model, normalize_persona

__all__ = ["DEFAULT_BASE_URL", "NotrackConfig"]

DEFAULT_BASE_URL = "https://notrack.ai"

# Browser-like UA: the upstream service expects a familiar client fingerprint.
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


@dataclass(frozen=True, slots=True)
class NotrackConfig:
    """Immutable client settings.

    Raises:
        NotrackConfigError: If a value is structurally invalid (bad URL,
            non-positive limits, unknown default model/persona).
    """

    base_url: str = DEFAULT_BASE_URL
    cookie: str = ""
    default_model: str = DEFAULT_MODEL
    default_persona: str = DEFAULT_PERSONA
    max_turns: int = 6
    timeout: float = 120.0
    connect_timeout: float = 30.0
    max_attempts: int = 5
    rate_limit_backoff: float = 4.0
    transport_backoff: float = 2.0
    user_agent: str = _DEFAULT_UA

    def __post_init__(self) -> None:
        base = self.base_url.strip().rstrip("/")
        if not base.startswith(("http://", "https://")):
            raise NotrackConfigError(f"base_url must start with http(s):// — got {self.base_url!r}")
        object.__setattr__(self, "base_url", base)
        object.__setattr__(self, "default_model", normalize_model(self.default_model))
        object.__setattr__(self, "default_persona", normalize_persona(self.default_persona))
        if self.max_turns < 1:
            raise NotrackConfigError(f"max_turns must be >= 1 — got {self.max_turns}")
        if self.max_attempts < 1:
            raise NotrackConfigError(f"max_attempts must be >= 1 — got {self.max_attempts}")
        if self.timeout <= 0 or self.connect_timeout <= 0:
            raise NotrackConfigError("timeouts must be positive")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> NotrackConfig:
        """Build a config from ``NOTRACK_*`` variables (see module docstring).

        Unset variables fall back to the dataclass defaults, so an empty
        environment yields a fully functional default config.
        """
        env = os.environ if environ is None else environ
        kwargs: dict[str, object] = {}

        if base := env.get("NOTRACK_BASE", "").strip():
            kwargs["base_url"] = base
        if cookie := env.get("NOTRACK_COOKIE", "").strip():
            kwargs["cookie"] = cookie
        if model := env.get("NOTRACK_MODEL", "").strip():
            kwargs["default_model"] = model
        if persona := env.get("NOTRACK_PERSONA", "").strip():
            kwargs["default_persona"] = persona
        if raw := env.get("NOTRACK_MAX_TURNS", "").strip():
            kwargs["max_turns"] = _parse_int("NOTRACK_MAX_TURNS", raw)
        if raw := env.get("NOTRACK_TIMEOUT", "").strip():
            kwargs["timeout"] = _parse_float("NOTRACK_TIMEOUT", raw)
        if raw := env.get("NOTRACK_MAX_ATTEMPTS", "").strip():
            kwargs["max_attempts"] = _parse_int("NOTRACK_MAX_ATTEMPTS", raw)

        return cls(**kwargs)  # type: ignore[arg-type]


def _parse_int(name: str, raw: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise NotrackConfigError(f"{name} must be an integer — got {raw!r}") from exc


def _parse_float(name: str, raw: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise NotrackConfigError(f"{name} must be a number — got {raw!r}") from exc
