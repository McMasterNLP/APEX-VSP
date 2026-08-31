"""Shared primitives for local, non-persisting evaluator comparisons."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from domain.models.evaluator_comparison import CanonicalTranscriptTurn, EvaluatorProvenance
from plugins.evaluators.apex_baseline_evaluator import ApexBaselineEvaluator
from plugins.evaluators.apex_hybrid_evaluator import ApexHybridEvaluator
from plugins.evaluators.apex_hybrid_v2_evaluator import ApexHybridV2Evaluator


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
