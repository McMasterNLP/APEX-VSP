"""Tests for strict, privacy-minimal ACE-CT transcript projection."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from schemas.ace_ct import ACECTTranscriptTurn
from services.ace_ct_transcript import (
    EMPTY_TURN_MARKER,
    ACECTTranscriptProjectionError,
    project_ace_ct_transcript,
    serialize_ace_ct_transcript,
)
from services.evaluator_comparison_service import hash_transcript


def test_roles_are_mapped_and_stable_source_order_is_used() -> None:
    transcript = project_ace_ct_transcript(
        [
            {"turn_number": 2, "role": "assistant", "text": "I am worried."},
            {"turn_number": 1, "role": "user", "text": "Tell me what worries you."},
        ]
    )

    assert [(turn.turn_number, turn.speaker) for turn in transcript.turns] == [
        (1, "clinician"),
        (2, "patient"),
    ]
    assert transcript.turn_numbers == (1, 2)
    assert [turn.source_turn_number for turn in transcript.turns] == [1, 2]


def test_equivalent_entity_objects_are_supported() -> None:
    transcript = project_ace_ct_transcript(
        [SimpleNamespace(turn_number=1, role="user", text="Hello")]
    )

    assert transcript.turns[0].speaker == "clinician"


@pytest.mark.parametrize("turn_number", [True, False, 0, -1, 1.0, "1", None])
def test_invalid_turn_numbers_are_rejected(turn_number: object) -> None:
    with pytest.raises(ACECTTranscriptProjectionError, match="positive integers"):
        project_ace_ct_transcript([{"turn_number": turn_number, "role": "user", "text": "Hello"}])


def test_duplicate_turn_numbers_are_rejected() -> None:
    with pytest.raises(ACECTTranscriptProjectionError, match="Duplicate turn number 2"):
        project_ace_ct_transcript(
            [
                {"turn_number": 2, "role": "user", "text": "First"},
                {"turn_number": 2, "role": "assistant", "text": "Second"},
            ]
        )


@pytest.mark.parametrize("role", ["system", "clinician", "patient", "", None])
def test_unknown_roles_are_rejected(role: object) -> None:
    with pytest.raises(ACECTTranscriptProjectionError, match="Unknown role"):
        project_ace_ct_transcript([{"turn_number": 1, "role": role, "text": "Hello"}])


def test_unicode_is_preserved() -> None:
    text = "Crainte — 痛み 🫶"
    transcript = project_ace_ct_transcript([{"turn_number": 1, "role": "assistant", "text": text}])

    assert transcript.turns[0].text == text
    assert text in serialize_ace_ct_transcript(transcript)


def test_line_endings_are_normalized_without_changing_internal_layout() -> None:
    transcript = project_ace_ct_transcript(
        [{"turn_number": 1, "role": "user", "text": "first\r\nsecond\rthird"}]
    )

    assert transcript.turns[0].text == "first\nsecond\nthird"


def test_only_surrounding_whitespace_is_removed() -> None:
    transcript = project_ace_ct_transcript(
        [{"turn_number": 1, "role": "user", "text": " \t two   words \n "}]
    )

    assert transcript.turns[0].text == "two   words"


def test_empty_text_is_retained_with_a_safe_warning() -> None:
    transcript = project_ace_ct_transcript(
        [{"turn_number": 3, "role": "assistant", "text": " \r\n\t "}]
    )

    assert transcript.turns[0].text == ""
    assert transcript.warnings[0].code == "empty_text_retained"
    assert transcript.warnings[0].source_turn_number == 3
    assert serialize_ace_ct_transcript(transcript) == (f"[Turn 3 | Patient] {EMPTY_TURN_MARKER}")


def test_non_string_and_missing_text_are_rejected() -> None:
    with pytest.raises(ACECTTranscriptProjectionError, match="must be a string"):
        project_ace_ct_transcript([{"turn_number": 1, "role": "user", "text": None}])
    with pytest.raises(ACECTTranscriptProjectionError, match="missing required field 'text'"):
        project_ace_ct_transcript([{"turn_number": 1, "role": "user"}])


def test_interleaving_and_model_serialization_are_preserved() -> None:
    source = [
        {"turn_number": 1, "role": "user", "text": "Question one"},
        {"turn_number": 2, "role": "assistant", "text": "Answer one"},
        {"turn_number": 3, "role": "user", "text": "Question two"},
        {"turn_number": 4, "role": "assistant", "text": "Answer two"},
    ]

    serialized = serialize_ace_ct_transcript(project_ace_ct_transcript(source))

    assert serialized.splitlines() == [
        "[Turn 1 | Clinician] Question one",
        "[Turn 2 | Patient] Answer one",
        "[Turn 3 | Clinician] Question two",
        "[Turn 4 | Patient] Answer two",
    ]


def test_hash_matches_comparison_input_even_when_projection_normalizes_text() -> None:
    source = [
        {"turn_number": 2, "role": "assistant", "text": " Patient \r\n reply "},
        {"turn_number": 1, "role": "user", "text": " Clinician "},
    ]

    transcript = project_ace_ct_transcript(source)

    assert transcript.transcript_hash == hash_transcript(source)
    assert transcript.turns[0].text == "Clinician"


def test_identity_and_database_fields_do_not_leak() -> None:
    source = [
        {
            "id": 9001,
            "session_id": 1002,
            "user_id": 77,
            "case_id": 12,
            "email": "private@example.test",
            "turn_number": 1,
            "role": "user",
            "text": "Hello",
        }
    ]

    transcript = project_ace_ct_transcript(source)
    payload = transcript.model_dump_json()
    serialized = serialize_ace_ct_transcript(transcript)

    assert "9001" not in payload
    assert "1002" not in payload
    assert "private@example.test" not in payload
    assert "user_id" not in payload
    assert "session_id" not in payload
    assert "case_id" not in payload
    assert "9001" not in serialized
    assert "private@example.test" not in serialized


def test_transcript_models_are_immutable() -> None:
    transcript = project_ace_ct_transcript([{"turn_number": 1, "role": "user", "text": "Hello"}])

    with pytest.raises(ValidationError):
        transcript.turns[0].text = "Changed"


def test_extra_fields_are_forbidden_on_typed_turns() -> None:
    with pytest.raises(ValidationError):
        ACECTTranscriptTurn(
            turn_number=1,
            source_turn_number=1,
            speaker="clinician",
            text="Hello",
            user_id=4,
        )
