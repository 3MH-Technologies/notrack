"""Unit tests for the model catalogue and persona list (offline)."""

from __future__ import annotations

from notrack import DEFAULT_MODEL, MODEL_DESCRIPTIONS, MODELS, PERSONAS


def test_catalogue_is_static_and_keyless() -> None:
    assert set(MODELS) == {"A", "B", "C", "F"}
    assert DEFAULT_MODEL in MODELS
    # No vendor API keys or endpoints are baked into the catalogue.
    for name in MODELS.values():
        assert "key" not in name.lower()
        assert "token" not in name.lower()


def test_descriptions_cover_every_model() -> None:
    assert set(MODEL_DESCRIPTIONS) == set(MODELS)
    for desc in MODEL_DESCRIPTIONS.values():
        assert desc.strip()


def test_personas_are_unique_and_sorted_readably() -> None:
    assert len(PERSONAS) == len(set(PERSONAS))
    assert "normal" in PERSONAS
    assert "coder" in PERSONAS
    assert all(p.islower() for p in PERSONAS)
