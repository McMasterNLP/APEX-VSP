"""Item 2B selection, Unicode, and strict authoring contract tests."""

import pytest
from pydantic import ValidationError

from domain.models.research_annotation import (
    CanonicalSpanSelection,
    HumanAnnotationCreateRequest,
    SpanAttributeValue,
)
from domain.models.research_evaluation import ResearchTranscriptTurn
from services.research_annotation_service import (
    ResearchAnnotationService,
    ResearchAnnotationServiceError,
)


HASH = "a" * 64


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        ("plain ASCII", 0, 5),
        ("café déjà vu", 3, 8),
        ("She said “hello”.", 9, 14),
        ("A😀B", 1, 2),
        ("e\u0301motion", 0, 2),
        ("line one\nline two", 8, 17),
        ("same same", 5, 9),
        ("bookends", 0, 8),
    ],
)
def test_server_verifies_unicode_code_point_half_open_selections(text, start, end):
    turn = ResearchTranscriptTurn(
        turn_number=1, role="clinician", source_role="user", text=text
    )
    selection = CanonicalSpanSelection(
        transcript_hash=HASH,
        start_turn_number=1,
        end_turn_number=1,
        speaker="clinician",
        start_offset=start,
        end_offset=end,
        selected_text=text[start:end],
    )
    ResearchAnnotationService._validate_selection(selection, HASH, (turn,))


def test_selection_contract_rejects_cross_turn_zero_length_and_whitespace():
    base = {
        "transcript_hash": HASH,
        "start_turn_number": 1,
        "end_turn_number": 1,
        "speaker": "clinician",
        "start_offset": 0,
        "end_offset": 1,
        "selected_text": "x",
    }
    with pytest.raises(ValidationError, match="one transcript turn"):
        CanonicalSpanSelection(**{**base, "end_turn_number": 2})
    with pytest.raises(ValidationError, match="greater than start"):
        CanonicalSpanSelection(**{**base, "end_offset": 0})
    with pytest.raises(ValidationError, match="whitespace"):
        CanonicalSpanSelection(**{**base, "selected_text": " "})


def test_server_rejects_stale_hash_speaker_bounds_and_text():
    turn = ResearchTranscriptTurn(
        turn_number=1, role="clinician", source_role="user", text="canonical"
    )
    base = {
        "transcript_hash": HASH,
        "start_turn_number": 1,
        "end_turn_number": 1,
        "speaker": "clinician",
        "start_offset": 0,
        "end_offset": 3,
        "selected_text": "can",
    }
    for replacement in (
        {"transcript_hash": "b" * 64},
        {"speaker": "patient"},
        {"end_offset": 30},
        {"selected_text": "wrong"},
    ):
        selection = CanonicalSpanSelection(**{**base, **replacement})
        with pytest.raises(ResearchAnnotationServiceError) as error:
            ResearchAnnotationService._validate_selection(selection, HASH, (turn,))
        assert error.value.category == "invalid_selection"


def test_authoring_request_forbids_unknown_fields_and_requires_sorted_attributes():
    selection = CanonicalSpanSelection(
        transcript_hash=HASH,
        start_turn_number=1,
        end_turn_number=1,
        speaker="clinician",
        start_offset=0,
        end_offset=1,
        selected_text="x",
    )
    with pytest.raises(ValidationError, match="sorted"):
        HumanAnnotationCreateRequest(
            expected_set_revision=0,
            selection=selection,
            label="test",
            attributes=(
                SpanAttributeValue(identifier="z_value", value="one"),
                SpanAttributeValue(identifier="a_value", value="two"),
            ),
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        HumanAnnotationCreateRequest(
            expected_set_revision=0,
            selection=selection,
            label="test",
            attributes=(),
            unexpected=True,
        )
