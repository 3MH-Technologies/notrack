"""Static model catalogue and persona list.

The dispatch API accepts single-letter model codes and a fixed set of
persona names. Display names below are the upstream service's own labels —
applications are free to rebrand them (the worm-ai platform, for example,
publishes them as *Worm Core / Pro / Flash / Synth*).

See https://github.com/3MH-Technologies/notrack for the full protocol.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_PERSONA",
    "MODELS",
    "MODEL_DESCRIPTIONS",
    "PERSONAS",
    "normalize_model",
    "normalize_persona",
]

#: Model code → upstream display name. ``C`` is the default.
MODELS: Final[dict[str, str]] = {
    "A": "AI-Minimax",
    "B": "AI-ChatGPT",
    "C": "NoTrack",
    "F": "Synthesis",
}

#: Model code → short neutral description (vendor-agnostic).
MODEL_DESCRIPTIONS: Final[dict[str, str]] = {
    "A": "Fast internal model",
    "B": "General-purpose internal model",
    "C": "Balanced internal model (default)",
    "F": "Multi-model internal synthesis",
}

#: Persona names accepted by ``/api/dispatch``.
PERSONAS: Final[tuple[str, ...]] = (
    "normal",
    "creative",
    "precise",
    "concise",
    "socratic",
    "tutor",
    "coder",
)

DEFAULT_MODEL: Final[str] = "C"
DEFAULT_PERSONA: Final[str] = "normal"


def normalize_model(code: str | None) -> str:
    """Return a valid model code, falling back to the default (``C``)."""
    candidate = (code or "").strip().upper()
    return candidate if candidate in MODELS else DEFAULT_MODEL


def normalize_persona(name: str | None) -> str:
    """Return a valid persona name, falling back to ``normal``."""
    candidate = (name or "").strip().lower()
    return candidate if candidate in PERSONAS else DEFAULT_PERSONA
