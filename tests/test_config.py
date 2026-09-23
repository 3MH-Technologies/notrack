"""Unit tests for configuration parsing and validation (fully offline)."""

from __future__ import annotations

import dataclasses

import pytest

from notrack import NotrackConfig, NotrackConfigError, normalize_model, normalize_persona
from notrack.config import DEFAULT_BASE_URL


def test_default_config_is_valid_and_keyless() -> None:
    cfg = NotrackConfig()
    assert cfg.base_url == DEFAULT_BASE_URL
    assert cfg.cookie == ""
    assert cfg.default_model == "C"
    assert cfg.default_persona == "normal"
    assert cfg.max_turns == 6
    assert cfg.max_attempts >= 1


def test_base_url_trailing_slash_stripped() -> None:
    assert NotrackConfig(base_url="https://example.com///").base_url == "https://example.com"


@pytest.mark.parametrize("bad", ["ftp://x", "not-a-url", ""])
def test_invalid_base_url_rejected(bad: str) -> None:
    with pytest.raises(NotrackConfigError):
        NotrackConfig(base_url=bad)


@pytest.mark.parametrize("field,value", [("max_turns", 0), ("max_attempts", 0), ("timeout", 0)])
def test_non_positive_limits_rejected(field: str, value: int) -> None:
    with pytest.raises(NotrackConfigError):
        NotrackConfig(**{field: value})  # type: ignore[arg-type]


def test_from_env_reads_all_supported_vars() -> None:
    cfg = NotrackConfig.from_env(
        {
            "NOTRACK_BASE": "https://upstream.internal/",
            "NOTRACK_COOKIE": "k1=v1; k2=v2",
            "NOTRACK_MODEL": "F",
            "NOTRACK_PERSONA": "coder",
            "NOTRACK_MAX_TURNS": "9",
            "NOTRACK_TIMEOUT": "30.5",
            "NOTRACK_MAX_ATTEMPTS": "2",
            "IGNORED": "x",
        }
    )
    assert cfg.base_url == "https://upstream.internal"
    assert cfg.cookie == "k1=v1; k2=v2"
    assert cfg.default_model == "F"
    assert cfg.default_persona == "coder"
    assert cfg.max_turns == 9
    assert cfg.timeout == 30.5
    assert cfg.max_attempts == 2


def test_from_env_empty_returns_defaults() -> None:
    cfg = NotrackConfig.from_env({})
    assert cfg.base_url == DEFAULT_BASE_URL
    assert cfg.default_model == "C"


@pytest.mark.parametrize("raw", ["abc", "1.5"])  # 1.5 is not an int
def test_from_env_bad_int_raises(raw: str) -> None:
    with pytest.raises(NotrackConfigError):
        NotrackConfig.from_env({"NOTRACK_MAX_TURNS": raw})


def test_from_env_bad_float_raises() -> None:
    with pytest.raises(NotrackConfigError):
        NotrackConfig.from_env({"NOTRACK_TIMEOUT": "soon"})


def test_config_is_frozen() -> None:
    cfg = NotrackConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.base_url = "https://evil.example"  # type: ignore[misc]


def test_normalizers_fall_back_and_casefold() -> None:
    assert normalize_model("f") == "F"
    assert normalize_model("Z") == "C"
    assert normalize_model(None) == "C"
    assert normalize_model("  b ") == "B"
    assert normalize_persona("CODER") == "coder"
    assert normalize_persona("chaotic") == "normal"
    assert normalize_persona(None) == "normal"
