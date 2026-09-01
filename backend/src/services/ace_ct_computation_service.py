"""Reusable non-persisting ACE-CT-inspired session computation core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from domain.models.evaluator_comparison import (
    ACECTCompatibilityProjection,
    EvaluatorFrameworkResults,
)
from domain.models.scoring import ComputedFeedback
from repositories.session_repo import SessionRepository
from repositories.turn_repo import TurnRepository
from schemas.ace_ct import (
    ACE_CT_RUBRIC_V0_1,
    ACECTEvaluationFailure,
    ACECTRubricSpec,
)
from services.ace_ct_evaluator_service import ACECTEvaluatorService
from services.ace_ct_prompt import PROMPT_VERSION
from services.ace_ct_results import (
    FRAMEWORK_EQUIVALENCE_WARNING,
    build_ace_ct_framework_results,
    project_ace_ct_compatibility_scores,
    sanitize_ace_ct_framework_results,
)
from services.ace_ct_transcript import project_ace_ct_transcript
from services.evaluator_llm_adapter_factory import resolve_evaluator_llm_adapter
from services.scoring_service import ScoringService

ACE_CT_PLUGIN_IDENTIFIER = (
    "plugins.evaluators.ace_ct_inspired_evaluator:ACECTInspiredRubricEvaluator"
)
ACE_CT_PLUGIN_VERSION = "0.1.0-experimental"


class ACECTComputationError(RuntimeError):
    """Sanitized computation failure safe for plugin and comparison boundaries."""

    def __init__(self, category: str):
        self.category = category
        super().__init__(f"ACE-CT-inspired computation failed category={category}.")


@dataclass(frozen=True)
class ACECTComputationResult:
    """Framework-first result with optional persistable APEX feedback."""

    transcript_hash: str
    llm_provider: str
    model_identifier: str
    framework_results: EvaluatorFrameworkResults
    compatibility_projection: ACECTCompatibilityProjection
    computed_feedback: ComputedFeedback | None


def _feedback_summary(
    framework_results: EvaluatorFrameworkResults,
) -> tuple[str, str]:
    scored = [result for result in framework_results.dimension_results if result.score is not None]
    if not scored:
        return (
            "No dimension had sufficient transcript evidence for compatibility feedback.",
            "Expert review is required before interpreting this transcript-only result.",
        )
    strongest_score = max(result.score for result in scored if result.score is not None)
    lowest_score = min(result.score for result in scored if result.score is not None)
    strongest = [result.dimension_id.value for result in scored if result.score == strongest_score][
        :3
    ]
    review = [result.dimension_id.value for result in scored if result.score == lowest_score][:3]
    return (
        "Experimental transcript evidence was strongest for: " + ", ".join(strongest) + ".",
        "Proposed review areas from the experimental rubric: " + ", ".join(review) + ".",
    )


async def compute_ace_ct_evaluation(
    db: Session,
    session_id: int,
    *,
    llm_provider: str,
    model_identifier: str | None = None,
    llm_adapter: Any | None = None,
    rubric: ACECTRubricSpec = ACE_CT_RUBRIC_V0_1,
    allow_experimental_override: bool = False,
) -> ACECTComputationResult:
    """Compute framework and compatibility output without writing database state."""

    session = SessionRepository(db).get_by_id(session_id)
    if session is None:
        raise ACECTComputationError("session_not_found")
    turns = TurnRepository(db).get_by_session(session_id)
    transcript = project_ace_ct_transcript(turns)
    resolved = resolve_evaluator_llm_adapter(
        llm_provider,
        model_identifier=model_identifier,
        adapter_override=llm_adapter,
    )
    evaluation_result = await ACECTEvaluatorService(resolved.adapter).evaluate(
        transcript,
        rubric,
        allow_experimental_override=allow_experimental_override,
    )
    if isinstance(evaluation_result, ACECTEvaluationFailure):
        raise ACECTComputationError(evaluation_result.category)

    baseline = await ScoringService(db).compute_baseline_feedback(
        session_id,
        evaluator_plugin_override=(ACE_CT_PLUGIN_IDENTIFIER, ACE_CT_PLUGIN_VERSION),
    )
    compatibility = project_ace_ct_compatibility_scores(
        evaluation_result.evaluation,
        apex_baseline_spikes_completion_score=baseline.spikes_completion_score,
    )
    framework = build_ace_ct_framework_results(
        evaluation_result.evaluation,
        compatibility_projection=compatibility,
    )
    framework = sanitize_ace_ct_framework_results(
        framework,
        raw_turn_texts={str(turn.text) for turn in turns if getattr(turn, "text", None)},
    )

    scores = compatibility.scores
    computed_feedback: ComputedFeedback | None = None
    if (
        scores.empathy_score is not None
        and scores.communication_score is not None
        and scores.overall_score is not None
        and scores.spikes_completion_score is not None
    ):
        strengths, improvements = _feedback_summary(framework)
        computed_feedback = baseline.model_copy(
            update={
                "empathy_score": scores.empathy_score,
                "communication_score": scores.communication_score,
                "spikes_completion_score": scores.spikes_completion_score,
                "overall_score": scores.overall_score,
                "strengths": strengths,
                "areas_for_improvement": improvements,
                "detailed_feedback": FRAMEWORK_EQUIVALENCE_WARNING,
                "evaluator_meta": {
                    "phase": "ace_ct_inspired_experimental_v1",
                    "status": "completed",
                    "framework": "ACE-CT-inspired",
                    "implementation_type": "experimental_transcript_rubric",
                    "validation_status": "experimental_unvalidated",
                    "publication_reproduction": False,
                    "rubric_version": rubric.rubric_version,
                    "approval_status": rubric.approval_status.value,
                    "prompt_version": PROMPT_VERSION,
                    "llm_provider": resolved.provider,
                    "model_identifier": resolved.model_identifier,
                    "experimental_override_used": allow_experimental_override,
                    "framework_results": framework.model_dump(mode="json"),
                    "compatibility_score_sources": compatibility.score_sources.model_dump(
                        mode="json"
                    ),
                    "warnings": list(compatibility.warnings),
                    "session_plugins": baseline.evaluator_meta.get("session_plugins", {}),
                },
            }
        )

    return ACECTComputationResult(
        transcript_hash=transcript.transcript_hash,
        llm_provider=resolved.provider,
        model_identifier=resolved.model_identifier,
        framework_results=framework,
        compatibility_projection=compatibility,
        computed_feedback=computed_feedback,
    )
