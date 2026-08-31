"""Structural snapshots for the original ACE-CT-inspired prompt builder."""

from __future__ import annotations

from schemas.ace_ct import ACE_CT_RUBRIC_V0_1
from services.ace_ct_prompt import (
    DIMENSION_SCHEMA_END,
    DIMENSION_SCHEMA_START,
    TRANSCRIPT_END,
    TRANSCRIPT_START,
    build_ace_ct_prompt,
)
from services.ace_ct_transcript import project_ace_ct_transcript


def _prompt():
    transcript = project_ace_ct_transcript(
        [
            {
                "id": 9001,
                "session_id": 72,
                "user_id": 44,
                "turn_number": 3,
                "role": "user",
                "text": "What feels most important right now?",
            },
            {
                "id": 9000,
                "session_id": 72,
                "user_id": 44,
                "turn_number": 1,
                "role": "user",
                "text": "I want to understand your concerns.",
            },
            {
                "id": 9002,
                "session_id": 72,
                "user_id": 44,
                "turn_number": 2,
                "role": "assistant",
                "text": "I am worried about what comes next.",
            },
        ]
    )
    return build_ace_ct_prompt(transcript, ACE_CT_RUBRIC_V0_1)


def _section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def test_prompt_has_exactly_system_and_user_messages() -> None:
    prompt = _prompt()

    assert [message.role for message in prompt.messages] == ["system", "user"]
    assert prompt.system_message == prompt.messages[0].content
    assert prompt.user_message == prompt.messages[1].content


def test_all_eleven_identifiers_appear_once_in_ordered_schema_section() -> None:
    prompt = _prompt().user_message
    schema = _section(prompt, DIMENSION_SCHEMA_START, DIMENSION_SCHEMA_END)
    positions = []

    for dimension in ACE_CT_RUBRIC_V0_1.dimensions:
        identifier = dimension.identifier.value
        assert schema.count(identifier) == 1
        positions.append(schema.index(identifier))

    assert positions == sorted(positions)
    assert prompt.count(DIMENSION_SCHEMA_START) == 1
    assert prompt.count(DIMENSION_SCHEMA_END) == 1


def test_interleaved_turns_are_serialized_in_order_with_clinical_roles() -> None:
    transcript = _section(_prompt().user_message, TRANSCRIPT_START, TRANSCRIPT_END)

    expected = [
        "[Turn 1 | Clinician] I want to understand your concerns.",
        "[Turn 2 | Patient] I am worried about what comes next.",
        "[Turn 3 | Clinician] What feels most important right now?",
    ]
    assert all(line in transcript for line in expected)
    assert [transcript.index(line) for line in expected] == sorted(
        transcript.index(line) for line in expected
    )
    assert "| User]" not in transcript
    assert "| Assistant]" not in transcript


def test_prompt_states_modality_and_scope_limitations() -> None:
    combined = _prompt().system_message + _prompt().user_message

    for phrase in ("transcript-only", "audio", "video", "tone", "overlap", "timing"):
        assert phrase in combined
    assert "Do not evaluate diagnosis, treatment" in combined
    assert "clinical competence" in combined
    assert "not an official model reproduction" in combined


def test_prompt_requires_strict_json_evidence_and_bounded_rationale() -> None:
    combined = _prompt().system_message + _prompt().user_message

    assert "strict JSON only" in combined
    assert "exactly eleven dimension results" in combined
    assert "Every cited number must exist" in combined
    assert "Do not invent evidence" in combined
    assert "at most 500 characters" in combined
    assert "at most 400 characters" in combined
    assert "Do not provide chain-of-thought" in combined
    assert '"official_model_reproduction": false' in combined


def test_prompt_includes_rubric_version_and_pending_approval_status() -> None:
    user_message = _prompt().user_message

    assert f"Rubric version: {ACE_CT_RUBRIC_V0_1.rubric_version}" in user_message
    assert f"Rubric approval status: {ACE_CT_RUBRIC_V0_1.approval_status.value}" in user_message


def test_prompt_excludes_confidential_source_language_and_paths() -> None:
    combined = (_prompt().system_message + _prompt().user_message).lower()

    forbidden = (
        "private dataset",
        "hyperparameter",
    )
    assert not any(value in combined for value in forbidden)


def test_prompt_excludes_identity_database_and_configuration_fields() -> None:
    combined = _prompt().system_message + _prompt().user_message

    forbidden = (
        "9000",
        "9001",
        "9002",
        "session_id",
        "user_id",
        "api_key",
        "database_url",
        "gemini_api_key",
        "openai_api_key",
    )
    assert not any(value in combined for value in forbidden)
