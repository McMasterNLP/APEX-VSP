"""Tests for deterministic transcript identity and safe evaluator provenance."""

from __future__ import annotations

import hashlib
import json

import pytest

from services.evaluator_comparison_service import (
    build_evaluator_provenance,
    canonicalize_transcript,
    hash_transcript,
    serialize_canonical_transcript,
)

TRANSCRIPT = [
    {"turn_number": 1, "role": "user", "text": "How are you feeling?"},
    {"turn_number": 2, "role": "assistant", "text": "I am worried."},
]


def test_transcript_hash_is_stable_and_uses_stable_turn_order() -> None:
    first = hash_transcript(TRANSCRIPT)
    reordered_input = hash_transcript(list(reversed(TRANSCRIPT)))

    assert first == reordered_input
    assert canonicalize_transcript(list(reversed(TRANSCRIPT)))[0].turn_number == 1
    assert first == hash_transcript(TRANSCRIPT)


@pytest.mark.parametrize(
    "changed",
    [
        [{"turn_number": 1, "role": "user", "text": "Changed"}, TRANSCRIPT[1]],
        [{"turn_number": 1, "role": "assistant", "text": TRANSCRIPT[0]["text"]}, TRANSCRIPT[1]],
        [{"turn_number": 3, "role": "user", "text": TRANSCRIPT[0]["text"]}, TRANSCRIPT[1]],
        [
            {"turn_number": 1, "role": "user", "text": TRANSCRIPT[1]["text"]},
            {"turn_number": 2, "role": "assistant", "text": TRANSCRIPT[0]["text"]},
        ],
    ],
)
def test_transcript_hash_changes_with_canonical_content(changed: list[dict]) -> None:
    assert hash_transcript(changed) != hash_transcript(TRANSCRIPT)


def test_transcript_hash_handles_unicode_as_utf8() -> None:
    transcript = [{"turn_number": 1, "role": "assistant", "text": "Crainte — 痛み 🫶"}]
    serialized = serialize_canonical_transcript(transcript)

    assert "Crainte — 痛み 🫶".encode() in serialized
    assert hash_transcript(transcript) == hashlib.sha256(serialized).hexdigest()


def test_empty_transcript_has_explicit_deterministic_hash() -> None:
    assert serialize_canonical_transcript([]) == b"[]"
    assert hash_transcript([]) == hashlib.sha256(b"[]").hexdigest()


def test_canonical_json_has_only_allowlisted_fields() -> None:
    serialized = serialize_canonical_transcript(
        [
            {
                "turn_number": 1,
                "role": "user",
                "text": "Hello",
                "user_id": 88,
                "metrics_json": "private",
            }
        ]
    )

    assert json.loads(serialized) == [{"role": "user", "text": "Hello", "turn_number": 1}]
    assert b"user_id" not in serialized
    assert b"metrics_json" not in serialized


def test_provenance_serialization_is_explicit_and_secret_free() -> None:
    provenance = build_evaluator_provenance(
        "hybrid_v2",
        model_identifier="gpt-test-model",
    )
    payload = provenance.model_dump(mode="json")

    assert payload == {
        "evaluator_identifier": "hybrid_v2",
        "plugin_identifier": ("plugins.evaluators.apex_hybrid_v2_evaluator:ApexHybridV2Evaluator"),
        "class_name": "ApexHybridV2Evaluator",
        "version": "2.0",
        "evaluator_type": "hybrid_llm",
        "llm_provider": "openai",
        "model_identifier": "gpt-test-model",
        "reviewer_version": "v2",
        "prompt_version": "v2",
    }
    assert not any("key" in key or "secret" in key or "token" in key for key in payload)


def test_rule_provenance_omits_llm_details() -> None:
    provenance = build_evaluator_provenance("baseline", model_identifier="ignored")

    assert provenance.evaluator_type == "rule_based"
    assert provenance.llm_provider is None
    assert provenance.model_identifier is None
    assert provenance.reviewer_version is None


def test_unknown_provenance_identifier_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown evaluator identifier"):
        build_evaluator_provenance("unknown")
