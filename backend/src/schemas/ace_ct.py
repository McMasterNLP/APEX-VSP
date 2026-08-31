"""Typed contracts for the experimental ACE-CT-inspired evaluator."""

from __future__ import annotations

import math
from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class ACECTDimensionResult(BaseModel):
    """Strict model-produced assessment for one rubric dimension."""

    dimension_id: ACECTDimensionId
    domain: ACECTDomain
    score: int | None = Field(default=None, strict=True, ge=1, le=5)
    insufficient_evidence: bool
    assessability: ACECTAssessability
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    evidence_turn_numbers: tuple[int, ...] = Field(max_length=100)
    reasoning: str = Field(min_length=1, max_length=500)
    improvement_recommendation: str = Field(min_length=1, max_length=400)
    modality_limitation_notes: tuple[str, ...] = Field(max_length=10)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("evidence_turn_numbers", mode="before")
    @classmethod
    def validate_raw_evidence_turn_numbers(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)) or any(
            not isinstance(number, int) or isinstance(number, bool) or number < 1
            for number in value
        ):
            raise ValueError("Evidence turn numbers must be positive integers.")
        return value

    @model_validator(mode="after")
    def validate_evidence_and_null_policy(self) -> Self:
        if self.score is None and not self.insufficient_evidence:
            raise ValueError("A null score requires insufficient_evidence=true.")
        if self.score is not None and self.insufficient_evidence:
            raise ValueError("A scored dimension requires insufficient_evidence=false.")
        if self.assessability == ACECTAssessability.NOT_ASSESSABLE and self.score is not None:
            raise ValueError("A not-assessable dimension cannot receive a score.")

        turn_numbers = self.evidence_turn_numbers
        if any(
            not isinstance(number, int) or isinstance(number, bool) or number < 1
            for number in turn_numbers
        ):
            raise ValueError("Evidence turn numbers must be positive integers.")
        if tuple(sorted(set(turn_numbers))) != turn_numbers:
            raise ValueError("Evidence turn numbers must be unique and sorted.")
        if any(not note.strip() or len(note) > 300 for note in self.modality_limitation_notes):
            raise ValueError("Modality limitation notes must contain 1-300 characters.")
        return self


class ACECTDomainScore(BaseModel):
    """Deterministic native-scale aggregate for one proposed domain."""

    domain: ACECTDomain
    mean_score: float | None = Field(default=None, ge=1.0, le=5.0, allow_inf_nan=False)
    scored_dimension_count: int = Field(strict=True, ge=0, le=11)
    insufficient_evidence_count: int = Field(strict=True, ge=0, le=11)

    model_config = ConfigDict(extra="forbid", frozen=True)


class ACECTScoreSources(BaseModel):
    """Allowlisted origin labels for model and aggregate scores."""

    dimension_scores: Literal["experimental_llm_transcript_rubric"]
    domain_scores: Literal["arithmetic_mean_of_non_null_dimensions"]
    compatibility_scores: Literal["not_computed_in_model_response"]

    model_config = ConfigDict(extra="forbid", frozen=True)


class ACECTEvaluationLimitations(BaseModel):
    """Mandatory boundaries carried with every evaluation result."""

    transcript_only: Literal[True]
    missing_modalities: tuple[Literal["audio", "video", "timing", "overlap"], ...]
    notes: tuple[str, ...] = Field(min_length=1, max_length=20)
    official_model_reproduction: Literal[False]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_limitations(self) -> Self:
        if self.missing_modalities != ("audio", "video", "timing", "overlap"):
            raise ValueError("All transcript-only missing modalities must be declared in order.")
        if any(not note.strip() or len(note) > 500 for note in self.notes):
            raise ValueError("Limitation notes must contain 1-500 characters.")
        return self


class ACECTEvaluationResult(BaseModel):
    """Strict complete output for an ACE-CT-inspired model evaluation."""

    framework_name: Literal["ACE-CT-inspired"]
    implementation_type: Literal["experimental_transcript_rubric"]
    validation_status: Literal["experimental_unvalidated"]
    publication_reproduction: Literal[False]
    rubric_version: str = Field(min_length=1, max_length=50)
    approval_status: ACECTRubricApprovalStatus
    dimension_results: tuple[ACECTDimensionResult, ...]
    domain_scores: tuple[ACECTDomainScore, ...]
    score_sources: ACECTScoreSources
    limitations: ACECTEvaluationLimitations

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_against_rubric(self) -> Self:
        if self.rubric_version != ACE_CT_RUBRIC_V0_1.rubric_version:
            raise ValueError("Evaluation rubric version does not match the implemented rubric.")

        dimension_ids = tuple(result.dimension_id for result in self.dimension_results)
        if len(dimension_ids) != 11:
            raise ValueError("Evaluation must contain exactly 11 dimension results.")
        if len(set(dimension_ids)) != len(dimension_ids):
            raise ValueError("Evaluation dimension results must be unique.")
        if dimension_ids != EXPECTED_ACE_CT_DIMENSION_ORDER:
            raise ValueError("Evaluation dimensions must use the stable rubric order.")

        rubric_dimensions = {
            dimension.identifier: dimension for dimension in ACE_CT_RUBRIC_V0_1.dimensions
        }
        for result in self.dimension_results:
            spec = rubric_dimensions[result.dimension_id]
            if result.domain != spec.domain:
                raise ValueError(
                    f"Returned domain for '{result.dimension_id.value}' does not match rubric."
                )
            if result.assessability != spec.assessability:
                raise ValueError(
                    f"Returned assessability for '{result.dimension_id.value}' does not "
                    "match rubric."
                )

        domains = tuple(score.domain for score in self.domain_scores)
        if len(domains) != len(ACECTDomain) or len(set(domains)) != len(domains):
            raise ValueError("Evaluation must contain every domain score exactly once.")
        if domains != tuple(ACECTDomain):
            raise ValueError("Domain scores must use the stable domain order.")

        for domain_score in self.domain_scores:
            results = [
                result for result in self.dimension_results if result.domain == domain_score.domain
            ]
            scores = [result.score for result in results if result.score is not None]
            expected_mean = math.fsum(scores) / len(scores) if scores else None
            expected_insufficient = sum(result.score is None for result in results)
            if domain_score.scored_dimension_count != len(scores):
                raise ValueError(
                    f"Scored dimension count for domain '{domain_score.domain.value}' is invalid."
                )
            if domain_score.insufficient_evidence_count != expected_insufficient:
                raise ValueError(
                    "Insufficient-evidence count for domain "
                    f"'{domain_score.domain.value}' is invalid."
                )
            if expected_mean is None:
                if domain_score.mean_score is not None:
                    raise ValueError(
                        f"All-null domain '{domain_score.domain.value}' must have a null mean."
                    )
            elif domain_score.mean_score is None or not math.isclose(
                domain_score.mean_score,
                expected_mean,
                rel_tol=0.0,
                abs_tol=1e-6,
            ):
                raise ValueError(f"Mean score for domain '{domain_score.domain.value}' is invalid.")
        return self


class ACECTEvaluationSuccess(BaseModel):
    """Typed successful service result."""

    status: Literal["success"] = "success"
    evaluation: ACECTEvaluationResult

    model_config = ConfigDict(extra="forbid", frozen=True)


class ACECTEvaluationFailure(BaseModel):
    """Typed allowlisted failure without raw provider data."""

    status: Literal["failed"] = "failed"
    category: Literal[
        "rubric_not_approved",
        "adapter_error",
        "invalid_json",
        "invalid_output",
        "invalid_evidence_turn",
        "excess_output",
    ]
    diagnostic: str = Field(min_length=1, max_length=200)

    model_config = ConfigDict(extra="forbid", frozen=True)


ACECTEvaluationServiceResult = ACECTEvaluationSuccess | ACECTEvaluationFailure
