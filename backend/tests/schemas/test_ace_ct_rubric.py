"""Schema and approval tests for the versioned ACE-CT-inspired rubric."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.ace_ct import (
    ACE_CT_RUBRIC_V0_1,
    EXPECTED_ACE_CT_DIMENSION_ORDER,
    EXPECTED_ACE_CT_DOMAIN_BY_DIMENSION,
    ACECTDimensionSpec,
    ACECTDomain,
    ACECTRubricApprovalError,
    ACECTRubricApprovalStatus,
    ACECTRubricSpec,
    ACECTScoreAnchor,
    require_ace_ct_rubric_approval,
)


def _rubric_payload() -> dict:
    return ACE_CT_RUBRIC_V0_1.model_dump(mode="python")


def test_rubric_has_exactly_eleven_unique_dimensions_in_stable_order() -> None:
    dimensions = ACE_CT_RUBRIC_V0_1.dimensions
    identifiers = tuple(dimension.identifier for dimension in dimensions)

    assert len(dimensions) == 11
    assert len(set(identifiers)) == 11
    assert identifiers == EXPECTED_ACE_CT_DIMENSION_ORDER


def test_dimension_domains_and_complete_membership_match_contract() -> None:
    dimensions = ACE_CT_RUBRIC_V0_1.dimensions

    assert {
        dimension.identifier: dimension.domain for dimension in dimensions
    } == EXPECTED_ACE_CT_DOMAIN_BY_DIMENSION
    assert set(dimension.domain for dimension in dimensions) == set(ACECTDomain)


def test_every_dimension_has_valid_placeholder_levels_one_through_five() -> None:
    for dimension in ACE_CT_RUBRIC_V0_1.dimensions:
        assert [anchor.score for anchor in dimension.score_anchors] == [1, 2, 3, 4, 5]
        assert all(anchor.is_placeholder for anchor in dimension.score_anchors)
        assert all(
            "pending expert review" in anchor.source_provenance
            for anchor in dimension.score_anchors
        )


@pytest.mark.parametrize("scores", [[1, 2, 3, 4], [1, 2, 3, 4, 6], [1, 2, 2, 4, 5]])
def test_invalid_anchor_sets_are_rejected(scores: list[int]) -> None:
    source_dimension = ACE_CT_RUBRIC_V0_1.dimensions[0]
    with pytest.raises(ValidationError):
        anchors = tuple(
            ACECTScoreAnchor(
                score=score,
                description="Original placeholder",
                is_placeholder=True,
                source_provenance="pending expert review",
            )
            for score in scores
        )
        ACECTDimensionSpec(
            **source_dimension.model_dump(exclude={"score_anchors"}),
            score_anchors=anchors,
        )


def test_unknown_dimension_identifier_is_rejected() -> None:
    payload = ACE_CT_RUBRIC_V0_1.dimensions[0].model_dump(mode="python")
    payload["identifier"] = "unknown_dimension"

    with pytest.raises(ValidationError):
        ACECTDimensionSpec.model_validate(payload)


def test_duplicate_dimension_identifier_is_rejected() -> None:
    payload = _rubric_payload()
    dimensions = list(payload["dimensions"])
    dimensions[-1] = dimensions[0]
    payload["dimensions"] = tuple(dimensions)

    with pytest.raises(ValidationError, match="identifiers must be unique"):
        ACECTRubricSpec.model_validate(payload)


def test_wrong_domain_assignment_is_rejected() -> None:
    payload = _rubric_payload()
    dimensions = list(payload["dimensions"])
    changed = dict(dimensions[0])
    changed["domain"] = ACECTDomain.LISTEN
    dimensions[0] = changed
    payload["dimensions"] = tuple(dimensions)

    with pytest.raises(ValidationError, match="must use domain 'respond'"):
        ACECTRubricSpec.model_validate(payload)


def test_required_provenance_and_publication_metadata_are_present() -> None:
    rubric = ACE_CT_RUBRIC_V0_1

    assert rubric.framework_name == "ACE-CT-inspired"
    assert rubric.rubric_version == "0.1.0-experimental"
    assert "10.1016/j.pec.2025.109465" in rubric.source_citation
    assert "Authorized confidential manuscript" in rubric.source_provenance
    assert rubric.source_publication_status == (
        "public_bibliographic_record_exact_anchors_not_publicly_verified"
    )
    assert rubric.approval_status == ACECTRubricApprovalStatus.PENDING_EXPERT_REVIEW
    assert rubric.implementation_status == "experimental_placeholder_anchors"


def test_missing_provenance_is_rejected() -> None:
    payload = _rubric_payload()
    payload["source_provenance"] = ""

    with pytest.raises(ValidationError):
        ACECTRubricSpec.model_validate(payload)


def test_pending_rubric_is_gated_without_explicit_override() -> None:
    with pytest.raises(ACECTRubricApprovalError, match="pending expert review"):
        require_ace_ct_rubric_approval(ACE_CT_RUBRIC_V0_1)

    require_ace_ct_rubric_approval(
        ACE_CT_RUBRIC_V0_1,
        allow_experimental_override=True,
    )


def test_approved_experimental_rubric_does_not_require_override() -> None:
    payload = _rubric_payload()
    payload["approval_status"] = ACECTRubricApprovalStatus.APPROVED_EXPERIMENTAL
    approved = ACECTRubricSpec.model_validate(payload)

    require_ace_ct_rubric_approval(approved)
