"""Typed contracts for the experimental ACE-CT-inspired evaluator."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ACECTTranscriptWarning(BaseModel):
    """Non-fatal transcript projection issue tied to a source turn."""

    code: Literal["empty_text_retained"]
    source_turn_number: int = Field(strict=True, ge=1)
    message: str = Field(min_length=1, max_length=200)

    model_config = ConfigDict(extra="forbid", frozen=True)


class ACECTTranscriptTurn(BaseModel):
    """Minimal immutable turn supplied to the rubric evaluator."""

    turn_number: int = Field(strict=True, ge=1)
    source_turn_number: int = Field(strict=True, ge=1)
    speaker: Literal["clinician", "patient"]
    text: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class ACECTTranscript(BaseModel):
    """Immutable projected transcript without identity or database metadata."""

    turns: tuple[ACECTTranscriptTurn, ...]
    warnings: tuple[ACECTTranscriptWarning, ...] = ()
    transcript_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @property
    def turn_numbers(self) -> tuple[int, ...]:
        """Return source evidence coordinates in conversational order."""

        return tuple(turn.turn_number for turn in self.turns)


class ACECTDomain(str, Enum):
    """Proposed ACE-CT-inspired aggregation groups."""

    RESPOND = "respond"
    LISTEN = "listen"
    SPEAK = "speak"
    GENERAL = "general"


class ACECTDimensionId(str, Enum):
    """Stable identifiers for the eleven proposed dimensions."""

    RESPOND_TO_EMOTION = "respond_to_emotion"
    ELICIT_PERSON_PERSPECTIVE = "elicit_person_perspective"
    AVOID_INTERRUPTING_OR_DIVERTING = "avoid_interrupting_or_diverting"
    ASSESS_UNDERSTANDING = "assess_understanding"
    DISCUSS_HOPES_PRIORITIES_WORRIES_FEARS = "discuss_hopes_priorities_worries_fears"
    ASK_PERMISSION_TO_PROGRESS = "ask_permission_to_progress"
    AVOID_UNEXPLAINED_CLINICAL_TERMINOLOGY = "avoid_unexplained_clinical_terminology"
    OFFER_QUESTION_OPPORTUNITIES = "offer_question_opportunities"
    SUMMARIZE_CONVERSATION = "summarize_conversation"
    REVIEW_NEXT_STEPS = "review_next_steps"
    MANAGE_CONVERSATION_PACE = "manage_conversation_pace"


class ACECTAssessability(str, Enum):
    """How directly a behavior can be assessed from transcript text."""

    TEXT_ASSESSABLE = "text_assessable"
    PARTIALLY_ASSESSABLE = "partially_assessable"
    NOT_ASSESSABLE = "not_assessable"


class ACECTRubricApprovalStatus(str, Enum):
    """Expert-approval state used for live-evaluation gating."""

    PENDING_EXPERT_REVIEW = "pending_expert_review"
    APPROVED_EXPERIMENTAL = "approved_experimental"


class ACECTScoreAnchor(BaseModel):
    """Original high-level placeholder for one integer score level."""

    score: int = Field(strict=True, ge=1, le=5)
    description: str = Field(min_length=1, max_length=500)
    is_placeholder: bool
    source_provenance: str = Field(min_length=1, max_length=300)

    model_config = ConfigDict(extra="forbid", frozen=True)


class ACECTDimensionSpec(BaseModel):
    """Versioned metadata for one ACE-CT-inspired dimension."""

    identifier: ACECTDimensionId
    domain: ACECTDomain
    display_name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    assessability: ACECTAssessability
    modality_limitations: tuple[str, ...]
    score_anchors: tuple[ACECTScoreAnchor, ...]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_score_anchors(self) -> Self:
        scores = [anchor.score for anchor in self.score_anchors]
        if scores and scores != [1, 2, 3, 4, 5]:
            raise ValueError("Score anchors, when present, must contain ordered levels 1-5.")
        return self


EXPECTED_ACE_CT_DIMENSION_ORDER = tuple(ACECTDimensionId)
EXPECTED_ACE_CT_DOMAIN_BY_DIMENSION = {
    ACECTDimensionId.RESPOND_TO_EMOTION: ACECTDomain.RESPOND,
    ACECTDimensionId.ELICIT_PERSON_PERSPECTIVE: ACECTDomain.LISTEN,
    ACECTDimensionId.AVOID_INTERRUPTING_OR_DIVERTING: ACECTDomain.LISTEN,
    ACECTDimensionId.ASSESS_UNDERSTANDING: ACECTDomain.LISTEN,
    ACECTDimensionId.DISCUSS_HOPES_PRIORITIES_WORRIES_FEARS: ACECTDomain.LISTEN,
    ACECTDimensionId.ASK_PERMISSION_TO_PROGRESS: ACECTDomain.SPEAK,
    ACECTDimensionId.AVOID_UNEXPLAINED_CLINICAL_TERMINOLOGY: ACECTDomain.SPEAK,
    ACECTDimensionId.OFFER_QUESTION_OPPORTUNITIES: ACECTDomain.GENERAL,
    ACECTDimensionId.SUMMARIZE_CONVERSATION: ACECTDomain.GENERAL,
    ACECTDimensionId.REVIEW_NEXT_STEPS: ACECTDomain.GENERAL,
    ACECTDimensionId.MANAGE_CONVERSATION_PACE: ACECTDomain.GENERAL,
}


class ACECTRubricSpec(BaseModel):
    """Complete immutable rubric specification and approval metadata."""

    framework_name: Literal["ACE-CT-inspired"]
    rubric_version: str = Field(min_length=1, max_length=50)
    source_citation: str = Field(min_length=1, max_length=1000)
    source_publication_status: Literal[
        "public_bibliographic_record_exact_anchors_not_publicly_verified"
    ]
    source_provenance: str = Field(min_length=1, max_length=500)
    approval_status: ACECTRubricApprovalStatus
    implementation_status: Literal["experimental_placeholder_anchors"]
    dimensions: tuple[ACECTDimensionSpec, ...]
    score_minimum: Literal[1]
    score_maximum: Literal[5]
    score_increment: Literal[1]
    null_score_policy: Literal["allowed_only_for_insufficient_evidence"]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_dimensions(self) -> Self:
        identifiers = tuple(dimension.identifier for dimension in self.dimensions)
        if len(identifiers) != 11:
            raise ValueError("ACE-CT-inspired rubric must contain exactly 11 dimensions.")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("ACE-CT-inspired dimension identifiers must be unique.")
        if identifiers != EXPECTED_ACE_CT_DIMENSION_ORDER:
            raise ValueError("ACE-CT-inspired dimensions must use the stable defined order.")
        for dimension in self.dimensions:
            expected_domain = EXPECTED_ACE_CT_DOMAIN_BY_DIMENSION[dimension.identifier]
            if dimension.domain != expected_domain:
                raise ValueError(
                    f"Dimension '{dimension.identifier.value}' must use domain "
                    f"'{expected_domain.value}'."
                )
        if set(dimension.domain for dimension in self.dimensions) != set(ACECTDomain):
            raise ValueError("Every proposed ACE-CT-inspired domain must have members.")
        return self


class ACECTRubricApprovalError(ValueError):
    """Raised before live evaluation when the rubric has not been approved."""


_PLACEHOLDER_ANCHOR_DESCRIPTIONS = (
    "Little or no transcript evidence of the target behavior when an opportunity is observable.",
    "Limited or inconsistent evidence with substantial improvement apparent from the text.",
    "Mixed or developing evidence with both effective and missed elements.",
    "Strong and consistent transcript evidence with only minor improvement opportunities.",
    "Exceptionally consistent and skillful transcript evidence across relevant opportunities.",
)
_PLACEHOLDER_PROVENANCE = (
    "Original high-level implementation placeholder; pending expert review; not an official "
    "ACE-CT scoring anchor."
)


def _placeholder_anchors() -> tuple[ACECTScoreAnchor, ...]:
    return tuple(
        ACECTScoreAnchor(
            score=score,
            description=description,
            is_placeholder=True,
            source_provenance=_PLACEHOLDER_PROVENANCE,
        )
        for score, description in enumerate(_PLACEHOLDER_ANCHOR_DESCRIPTIONS, start=1)
    )


def _dimension(
    identifier: ACECTDimensionId,
    domain: ACECTDomain,
    display_name: str,
    description: str,
    assessability: ACECTAssessability,
    *modality_limitations: str,
) -> ACECTDimensionSpec:
    return ACECTDimensionSpec(
        identifier=identifier,
        domain=domain,
        display_name=display_name,
        description=description,
        assessability=assessability,
        modality_limitations=tuple(modality_limitations),
        score_anchors=_placeholder_anchors(),
    )


ACE_CT_RUBRIC_V0_1 = ACECTRubricSpec(
    framework_name="ACE-CT-inspired",
    rubric_version="0.1.0-experimental",
    source_citation=(
        "Arora, A. K., et al. (2026). Multi-methods development and validation of a tool "
        "for use in measuring serious illness communication competence: Assessment of "
        "clinical encounters - Communication tool (ACE-CT). Patient Education and "
        "Counseling, 144, 109465. https://doi.org/10.1016/j.pec.2025.109465"
    ),
    source_publication_status=("public_bibliographic_record_exact_anchors_not_publicly_verified"),
    source_provenance=(
        "Authorized confidential manuscript informed dimension organization; exact anchors "
        "are not reproduced. Public citation and repository wording require expert confirmation."
    ),
    approval_status=ACECTRubricApprovalStatus.PENDING_EXPERT_REVIEW,
    implementation_status="experimental_placeholder_anchors",
    dimensions=(
        _dimension(
            ACECTDimensionId.RESPOND_TO_EMOTION,
            ACECTDomain.RESPOND,
            "Respond to emotion",
            "Recognize and respond constructively to expressed emotion.",
            ACECTAssessability.PARTIALLY_ASSESSABLE,
            "Tone, gesture, facial expression, and silence duration are unavailable.",
        ),
        _dimension(
            ACECTDimensionId.ELICIT_PERSON_PERSPECTIVE,
            ACECTDomain.LISTEN,
            "Elicit the person's perspective",
            "Invite the person's perspective using listening-oriented techniques.",
            ACECTAssessability.TEXT_ASSESSABLE,
            "Tone and meaningful silence are unavailable.",
        ),
        _dimension(
            ACECTDimensionId.AVOID_INTERRUPTING_OR_DIVERTING,
            ACECTDomain.LISTEN,
            "Avoid interrupting or diverting",
            "Preserve the person's conversational lead without unnecessary interruption or redirection.",
            ACECTAssessability.PARTIALLY_ASSESSABLE,
            "Speech overlap, interruption timing, and pause duration are unavailable.",
        ),
        _dimension(
            ACECTDimensionId.ASSESS_UNDERSTANDING,
            ACECTDomain.LISTEN,
            "Assess understanding",
            "Explore what the person understands about the illness or issue.",
            ACECTAssessability.TEXT_ASSESSABLE,
            "Non-verbal signs of confusion or comprehension are unavailable.",
        ),
        _dimension(
            ACECTDimensionId.DISCUSS_HOPES_PRIORITIES_WORRIES_FEARS,
            ACECTDomain.LISTEN,
            "Discuss hopes, priorities, worries, or fears",
            "Invite discussion of personally important hopes, priorities, worries, or fears.",
            ACECTAssessability.TEXT_ASSESSABLE,
            "Unspoken affect and visual cues are unavailable.",
        ),
        _dimension(
            ACECTDimensionId.ASK_PERMISSION_TO_PROGRESS,
            ACECTDomain.SPEAK,
            "Ask permission to progress",
            "Seek permission before moving the conversation forward or changing focus.",
            ACECTAssessability.TEXT_ASSESSABLE,
            "Prosody and non-verbal assent are unavailable.",
        ),
        _dimension(
            ACECTDimensionId.AVOID_UNEXPLAINED_CLINICAL_TERMINOLOGY,
            ACECTDomain.SPEAK,
            "Avoid unexplained clinical terminology",
            "Use accessible language and explain necessary clinical terms.",
            ACECTAssessability.TEXT_ASSESSABLE,
            "Audience-specific prior knowledge is unknown unless stated.",
        ),
        _dimension(
            ACECTDimensionId.OFFER_QUESTION_OPPORTUNITIES,
            ACECTDomain.GENERAL,
            "Offer question opportunities",
            "Make space for the person to ask questions.",
            ACECTAssessability.TEXT_ASSESSABLE,
            "Non-verbal invitation or discouragement is unavailable.",
        ),
        _dimension(
            ACECTDimensionId.SUMMARIZE_CONVERSATION,
            ACECTDomain.GENERAL,
            "Summarize the conversation",
            "Summarize and clarify important content.",
            ACECTAssessability.TEXT_ASSESSABLE,
            "Non-verbal confirmation is unavailable.",
        ),
        _dimension(
            ACECTDimensionId.REVIEW_NEXT_STEPS,
            ACECTDomain.GENERAL,
            "Review next steps",
            "Make next steps understandable and, where observable, collaborative.",
            ACECTAssessability.TEXT_ASSESSABLE,
            "Visual aids and off-record planning are unavailable.",
        ),
        _dimension(
            ACECTDimensionId.MANAGE_CONVERSATION_PACE,
            ACECTDomain.GENERAL,
            "Manage conversation pace",
            "Manage conversational pace in a way that supports the person.",
            ACECTAssessability.PARTIALLY_ASSESSABLE,
            "Timing, pause length, overlap, delivery speed, and video are unavailable.",
        ),
    ),
    score_minimum=1,
    score_maximum=5,
    score_increment=1,
    null_score_policy="allowed_only_for_insufficient_evidence",
)


def require_ace_ct_rubric_approval(
    rubric: ACECTRubricSpec,
    *,
    allow_experimental_override: bool = False,
) -> None:
    """Refuse evaluation of pending rubric content without explicit authorization."""

    if (
        rubric.approval_status != ACECTRubricApprovalStatus.APPROVED_EXPERIMENTAL
        and not allow_experimental_override
    ):
        raise ACECTRubricApprovalError(
            "ACE-CT-inspired rubric is pending expert review; an explicit experimental "
            "override is required."
        )
