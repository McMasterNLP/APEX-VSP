"""Strict model tests for Item 2A annotation requests and corrections."""

import pytest
from pydantic import ValidationError

from domain.models.research_annotation import (
    AnnotationSetReopenRequest,
    DimensionRatingCorrection,
    ReviewDecisionWriteRequest,
    SpanCorrection,
)


def test_span_correction_reserves_but_rejects_boundary_editing():
    correction = SpanCorrection(
        corrected_label="empathic_opportunity",
        corrected_dimension="Feeling",
    )
    assert correction.corrected_start_char is None
    with pytest.raises(ValidationError):
        SpanCorrection(
            corrected_label="empathic_opportunity",
            corrected_dimension="Feeling",
            corrected_start_char=2,
        )


def test_decision_shape_requires_typed_correction_and_bounded_note():
    with pytest.raises(ValidationError, match="typed correction"):
        ReviewDecisionWriteRequest(
            expected_set_revision=0,
            decision="corrected",
        )
    with pytest.raises(ValidationError):
        ReviewDecisionWriteRequest(
            expected_set_revision=0,
            decision="confirmed",
            reviewer_note="x" * 1_001,
        )


def test_insufficient_evidence_is_a_rating_only_typed_decision():
    correction = DimensionRatingCorrection(
        corrected_score=None,
        corrected_score_status="insufficient_evidence",
        corrected_assessability="partially_assessable",
        corrected_evidence_turns=(1, 3),
    )
    request = ReviewDecisionWriteRequest(
        expected_set_revision=2,
        expected_decision_revision=1,
        decision="insufficient_evidence",
        correction=correction,
    )
    assert request.correction.corrected_score is None

    with pytest.raises(ValidationError, match="ratings"):
        ReviewDecisionWriteRequest(
            expected_set_revision=0,
            decision="insufficient_evidence",
            correction=SpanCorrection(
                corrected_label="elicitation",
                corrected_dimension=None,
            ),
        )


@pytest.mark.parametrize("evidence", [(2, 1), (1, 1), (0,)])
def test_rating_correction_rejects_invalid_evidence_turns(evidence):
    with pytest.raises(ValidationError):
        DimensionRatingCorrection(
            corrected_score=4,
            corrected_score_status="available",
            corrected_assessability="text_assessable",
            corrected_evidence_turns=evidence,
        )


def test_reopen_requires_bounded_reason():
    with pytest.raises(ValidationError):
        AnnotationSetReopenRequest(expected_set_revision=1, reason="")
    with pytest.raises(ValidationError):
        AnnotationSetReopenRequest(expected_set_revision=1, reason="x" * 501)
