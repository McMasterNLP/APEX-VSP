"""Shared primitives for local, non-persisting evaluator comparisons."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from domain.models.evaluator_comparison import (
    CanonicalTranscriptTurn,
    EvaluatorComparisonAnalysis,
    EvaluatorProvenance,
    EvaluatorRunResult,
    EvaluatorScores,
    NumericMetricSummary,
    PairwiseEvaluatorDifference,
    PairwiseFindingAgreement,
    SanitizedEvaluatorError,
)
from domain.models.scoring import ComputedFeedback
from plugins.evaluators.apex_baseline_evaluator import ApexBaselineEvaluator
from plugins.evaluators.apex_hybrid_evaluator import ApexHybridEvaluator
from plugins.evaluators.apex_hybrid_v2_evaluator import ApexHybridV2Evaluator
from repositories.session_repo import SessionRepository
from repositories.turn_repo import TurnRepository
from services.scoring_service import ScoringService


@dataclass(frozen=True)
class EvaluatorDefinition:
    """Static evaluator metadata used for validation and safe provenance."""

    identifier: str
    plugin_identifier: str
    class_name: str
    version: str
    evaluator_type: Literal["rule_based", "hybrid_llm"]
    llm_provider: str | None = None
    reviewer_version: str | None = None
    prompt_version: str | None = None


EVALUATOR_DEFINITIONS: dict[str, EvaluatorDefinition] = {
    "baseline": EvaluatorDefinition(
        identifier="baseline",
        plugin_identifier=ApexBaselineEvaluator.name,
        class_name=ApexBaselineEvaluator.__name__,
        version=ApexBaselineEvaluator.version,
        evaluator_type="rule_based",
    ),
    "hybrid_v1": EvaluatorDefinition(
        identifier="hybrid_v1",
        plugin_identifier=ApexHybridEvaluator.name,
        class_name=ApexHybridEvaluator.__name__,
        version=ApexHybridEvaluator.version,
        evaluator_type="hybrid_llm",
        llm_provider="openai",
        reviewer_version="v1",
        prompt_version="v1",
    ),
    "hybrid_v2": EvaluatorDefinition(
        identifier="hybrid_v2",
        plugin_identifier=ApexHybridV2Evaluator.name,
        class_name=ApexHybridV2Evaluator.__name__,
        version=ApexHybridV2Evaluator.version,
        evaluator_type="hybrid_llm",
        llm_provider="openai",
        reviewer_version="v2",
        prompt_version="v2",
    ),
}

SCORE_METRICS = (
    "empathy_score",
    "communication_score",
    "spikes_completion_score",
    "overall_score",
)
NUMERIC_PRECISION = 4


def _turn_value(turn: Any, field: str) -> Any:
    if isinstance(turn, dict):
        return turn.get(field)
    return getattr(turn, field)


def canonicalize_transcript(turns: Iterable[Any]) -> list[CanonicalTranscriptTurn]:
    """Return the minimal transcript in stable turn-number order."""
    canonical = [
        CanonicalTranscriptTurn(
            turn_number=int(_turn_value(turn, "turn_number")),
            role=str(_turn_value(turn, "role")),
            text=str(_turn_value(turn, "text") or ""),
        )
        for turn in turns
    ]
    return sorted(canonical, key=lambda turn: turn.turn_number)


def serialize_canonical_transcript(turns: Iterable[Any]) -> bytes:
    """Serialize canonical turns as deterministic, compact UTF-8 JSON."""
    payload = [turn.model_dump(mode="json") for turn in canonicalize_transcript(turns)]
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def hash_transcript(turns: Iterable[Any]) -> str:
    """Return a SHA-256 hex digest, including the explicit empty transcript ``[]``."""
    return hashlib.sha256(serialize_canonical_transcript(turns)).hexdigest()


def build_evaluator_provenance(
    evaluator_identifier: str,
    *,
    model_identifier: str | None = None,
) -> EvaluatorProvenance:
    """Build allowlisted provenance without inspecting environment or adapter state."""
    try:
        definition = EVALUATOR_DEFINITIONS[evaluator_identifier]
    except KeyError as exc:
        allowed = ", ".join(EVALUATOR_DEFINITIONS)
        raise ValueError(
            f"Unknown evaluator identifier '{evaluator_identifier}'. Expected one of: {allowed}."
        ) from exc

    return EvaluatorProvenance(
        evaluator_identifier=definition.identifier,
        plugin_identifier=definition.plugin_identifier,
        class_name=definition.class_name,
        version=definition.version,
        evaluator_type=definition.evaluator_type,
        llm_provider=definition.llm_provider,
        model_identifier=model_identifier if definition.llm_provider else None,
        reviewer_version=definition.reviewer_version,
        prompt_version=definition.prompt_version,
    )


def _normalize_number(value: Any) -> float | None:
    """Normalize finite numeric values for deterministic JSON output."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    normalized = round(number, NUMERIC_PRECISION)
    return 0.0 if normalized == 0 else normalized


def _metric_summary(
    values_by_evaluator: dict[str, Any],
) -> NumericMetricSummary:
    values: list[float] = []
    missing: list[str] = []
    for evaluator, raw_value in values_by_evaluator.items():
        value = _normalize_number(raw_value)
        if value is None:
            missing.append(evaluator)
        else:
            values.append(value)
    if not values:
        return NumericMetricSummary(
            available_count=0,
            missing_evaluators=missing,
        )
    minimum = min(values)
    maximum = max(values)
    return NumericMetricSummary(
        minimum=minimum,
        maximum=maximum,
        mean=_normalize_number(math.fsum(values) / len(values)),
        range=_normalize_number(maximum - minimum),
        available_count=len(values),
        missing_evaluators=missing,
    )


def _result_score(result: EvaluatorRunResult, metric: str) -> float | None:
    if result.status != "success" or result.scores is None:
        return None
    return _normalize_number(getattr(result.scores, metric, None))


def _spikes_findings(result: EvaluatorRunResult) -> set[str] | None:
    feedback = result.structured_feedback
    if result.status != "success" or feedback is None:
        return None
    coverage = feedback.spikes_coverage
    covered = coverage.get("covered") if isinstance(coverage, dict) else None
    if not isinstance(covered, list):
        return None
    return {str(stage).strip().lower() for stage in covered if str(stage).strip()}


def _evidence_findings(result: EvaluatorRunResult) -> set[str] | None:
    feedback = result.structured_feedback
    if result.status != "success" or feedback is None:
        return None

    findings: set[str] = set()
    for missed in feedback.missed_opportunities or []:
        if isinstance(missed, dict) and isinstance(missed.get("turn_number"), int):
            findings.add(f"missed:turn:{missed['turn_number']}")
    span_groups = (
        ("eo", feedback.eo_spans),
        ("elicitation", feedback.elicitation_spans),
        ("response", feedback.response_spans),
    )
    for group, spans in span_groups:
        for span in spans or []:
            if not isinstance(span, dict):
                continue
            turn_number = span.get("turn_number")
            if not isinstance(turn_number, int):
                continue
            subtype = span.get("dimension") or span.get("type") or "unspecified"
            findings.add(f"{group}:turn:{turn_number}:{str(subtype).strip().lower()}")
    return findings


def _agreement(
    evaluator_a: str,
    evaluator_b: str,
    findings_a: set[str] | None,
    findings_b: set[str] | None,
) -> PairwiseFindingAgreement:
    if findings_a is None or findings_b is None:
        return PairwiseFindingAgreement(
            evaluator_a=evaluator_a,
            evaluator_b=evaluator_b,
            comparable=False,
        )
    shared = sorted(findings_a & findings_b)
    only_a = sorted(findings_a - findings_b)
    only_b = sorted(findings_b - findings_a)
    union_count = len(findings_a | findings_b)
    jaccard = 1.0 if union_count == 0 else len(shared) / union_count
    return PairwiseFindingAgreement(
        evaluator_a=evaluator_a,
        evaluator_b=evaluator_b,
        comparable=True,
        intersection_count=len(shared),
        union_count=union_count,
        jaccard=_normalize_number(jaccard),
        shared=shared,
        only_a=only_a,
        only_b=only_b,
    )


def analyze_evaluator_results(
    results: Iterable[EvaluatorRunResult],
) -> EvaluatorComparisonAnalysis:
    """Derive deterministic descriptive analysis without ranking evaluator quality."""
    observed = list(results)
    successful = [result for result in observed if result.status == "success"]
    failed_count = len(observed) - len(successful)

    score_metrics = {
        metric: _metric_summary(
            {result.evaluator_identifier: _result_score(result, metric) for result in observed}
        )
        for metric in SCORE_METRICS
    }
    runtime = _metric_summary(
        {result.evaluator_identifier: result.runtime_ms for result in observed}
    )

    pairwise: list[PairwiseEvaluatorDifference] = []
    spikes_agreement: list[PairwiseFindingAgreement] = []
    evidence_agreement: list[PairwiseFindingAgreement] = []
    for index, result_a in enumerate(observed):
        for result_b in observed[index + 1 :]:
            differences: dict[str, float | None] = {}
            for metric in SCORE_METRICS:
                value_a = _result_score(result_a, metric)
                value_b = _result_score(result_b, metric)
                differences[metric] = (
                    _normalize_number(value_a - value_b)
                    if value_a is not None and value_b is not None
                    else None
                )
            pairwise.append(
                PairwiseEvaluatorDifference(
                    evaluator_a=result_a.evaluator_identifier,
                    evaluator_b=result_b.evaluator_identifier,
                    evaluator_a_status=result_a.status,
                    evaluator_b_status=result_b.status,
                    score_differences=differences,
                    runtime_difference_ms=(
                        _normalize_number(result_a.runtime_ms - result_b.runtime_ms) or 0.0
                    ),
                )
            )
            spikes_agreement.append(
                _agreement(
                    result_a.evaluator_identifier,
                    result_b.evaluator_identifier,
                    _spikes_findings(result_a),
                    _spikes_findings(result_b),
                )
            )
            evidence_agreement.append(
                _agreement(
                    result_a.evaluator_identifier,
                    result_b.evaluator_identifier,
                    _evidence_findings(result_a),
                    _evidence_findings(result_b),
                )
            )

    all_findings = {
        result.evaluator_identifier: (_evidence_findings(result) or set()) for result in successful
    }
    unique_findings: dict[str, list[str]] = {}
    for evaluator, findings in all_findings.items():
        findings_from_others: set[str] = set()
        for other_evaluator, other_findings in all_findings.items():
            if other_evaluator != evaluator:
                findings_from_others.update(other_findings)
        unique_findings[evaluator] = sorted(findings - findings_from_others)

    return EvaluatorComparisonAnalysis(
        successful_evaluator_count=len(successful),
        failed_evaluator_count=failed_count,
        score_metrics=score_metrics,
        runtime=runtime,
        pairwise_differences=pairwise,
        spikes_stage_agreement=spikes_agreement,
        evidence_agreement=evidence_agreement,
        unique_findings=unique_findings,
        limitations=[
            "Agreement is descriptive and does not establish clinical correctness.",
            "No evaluator is ranked without external reference labels.",
            "Missing or failed evaluator outputs are excluded from numeric summaries.",
        ],
    )


def validate_evaluator_identifiers(evaluator_identifiers: Iterable[str]) -> list[str]:
    """Validate identifiers while preserving requested order and removing duplicates."""
    requested: list[str] = []
    for raw_identifier in evaluator_identifiers:
        identifier = str(raw_identifier).strip()
        if not identifier:
            continue
        if identifier not in EVALUATOR_DEFINITIONS:
            allowed = ", ".join(EVALUATOR_DEFINITIONS)
            raise ValueError(
                f"Unknown evaluator identifier '{identifier}'. Expected one of: {allowed}."
            )
        if identifier not in requested:
            requested.append(identifier)
    if not requested:
        raise ValueError("At least one evaluator identifier is required.")
    return requested


class EvaluatorComparisonService:
    """Run supported evaluators independently without invoking persistence entrypoints."""

    def __init__(self, db: Session, *, model_identifier: str | None = None):
        self.db = db
        self.model_identifier = model_identifier
        self.session_repo = SessionRepository(db)
        self.turn_repo = TurnRepository(db)
        self.scoring_service = ScoringService(db)

    async def run_evaluators(
        self,
        session_id: int,
        evaluator_identifiers: Iterable[str] = tuple(EVALUATOR_DEFINITIONS),
        *,
        require_completed: bool = True,
    ) -> list[EvaluatorRunResult]:
        """Run each requested evaluator and retain successes when another evaluator fails."""
        requested = validate_evaluator_identifiers(evaluator_identifiers)
        session = self.session_repo.get_by_id(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} was not found.")
        if require_completed and session.state != "completed":
            raise ValueError(f"Session {session_id} must be completed before comparison.")

        initial_turns = self.turn_repo.get_by_session(session_id)
        transcript_hash = hash_transcript(initial_turns)
        results: list[EvaluatorRunResult] = []
        for identifier in requested:
            results.append(
                await self._run_one(
                    session_id,
                    identifier,
                    transcript_hash=transcript_hash,
                )
            )

        final_hash = hash_transcript(self.turn_repo.get_by_session(session_id))
        if final_hash != transcript_hash:
            raise RuntimeError("Session transcript changed during evaluator comparison.")
        return results

    async def _run_one(
        self,
        session_id: int,
        evaluator_identifier: str,
        *,
        transcript_hash: str,
    ) -> EvaluatorRunResult:
        definition = EVALUATOR_DEFINITIONS[evaluator_identifier]
        provenance = build_evaluator_provenance(
            evaluator_identifier,
            model_identifier=self.model_identifier,
        )
        started = time.perf_counter()
        try:
            feedback = await self._compute(evaluator_identifier, session_id)
            runtime_ms = max(0.0, round((time.perf_counter() - started) * 1000.0, 3))
            meta = feedback.evaluator_meta or {}
            if evaluator_identifier != "baseline" and meta.get("status") == "failed":
                return self._failed_result(
                    definition,
                    provenance,
                    transcript_hash,
                    runtime_ms,
                    category="evaluation_failed",
                    message="Evaluator did not produce a complete review.",
                )
            return EvaluatorRunResult(
                evaluator_identifier=evaluator_identifier,
                evaluator_name=definition.class_name,
                evaluator_version=definition.version,
                status="success",
                runtime_ms=runtime_ms,
                transcript_hash=transcript_hash,
                provenance=provenance,
                scores=self._scores_from_feedback(feedback),
                structured_feedback=feedback,
            )
        # Isolation boundary: every evaluator failure must become a sanitized result so
        # remaining evaluators still run. Raw exception content is deliberately discarded.
        except Exception:  # noqa: BLE001
            runtime_ms = max(0.0, round((time.perf_counter() - started) * 1000.0, 3))
            return self._failed_result(
                definition,
                provenance,
                transcript_hash,
                runtime_ms,
                category="unexpected_error",
                message="Evaluator execution failed; raw exception details were omitted.",
            )

    async def _compute(self, evaluator_identifier: str, session_id: int) -> ComputedFeedback:
        if evaluator_identifier == "baseline":
            definition = EVALUATOR_DEFINITIONS["baseline"]
            return await self.scoring_service.compute_baseline_feedback(
                session_id,
                evaluator_plugin_override=(definition.plugin_identifier, definition.version),
            )
        if evaluator_identifier == "hybrid_v1":
            return await self.scoring_service.compute_hybrid_feedback(session_id)
        if evaluator_identifier == "hybrid_v2":
            return await self.scoring_service.compute_hybrid_v2_feedback(session_id)
        raise ValueError(f"Unsupported evaluator identifier '{evaluator_identifier}'.")

    @staticmethod
    def _scores_from_feedback(feedback: ComputedFeedback) -> EvaluatorScores:
        return EvaluatorScores(
            empathy_score=feedback.empathy_score,
            communication_score=feedback.communication_score,
            spikes_completion_score=feedback.spikes_completion_score,
            overall_score=feedback.overall_score,
        )

    @staticmethod
    def _failed_result(
        definition: EvaluatorDefinition,
        provenance: EvaluatorProvenance,
        transcript_hash: str,
        runtime_ms: float,
        *,
        category: Literal["evaluation_failed", "unexpected_error"],
        message: str,
    ) -> EvaluatorRunResult:
        return EvaluatorRunResult(
            evaluator_identifier=definition.identifier,
            evaluator_name=definition.class_name,
            evaluator_version=definition.version,
            status="failed",
            runtime_ms=runtime_ms,
            transcript_hash=transcript_hash,
            provenance=provenance,
            error=SanitizedEvaluatorError(category=category, message=message),
        )
