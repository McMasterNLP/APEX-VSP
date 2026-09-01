"""Research adapter protocol and immutable execution context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain.models.evaluator_comparison import EvaluatorRunResult
from domain.models.research_evaluation import (
    FrameworkNativeResult,
    ResearchCapabilities,
    ResearchProjection,
    ResearchTranscriptTurn,
)


@dataclass(frozen=True)
class ResearchAdapterContext:
    """Canonical, identity-free transcript and evaluator context for projection."""

    transcript_hash: str
    transcript_turns: tuple[ResearchTranscriptTurn, ...]
    evaluator_identifier: str
    framework_identifier: str


class ResearchResultAdapter(Protocol):
    """Deterministic translation from validated native output to projection."""

    identifier: str
    version: str
    supported_native_types: tuple[str, ...]
    capabilities: ResearchCapabilities

    def build_native_result(
        self,
        result: EvaluatorRunResult,
        context: ResearchAdapterContext,
    ) -> FrameworkNativeResult:
        """Build the complete typed authoritative framework result."""
        ...

    def project(
        self,
        native_result: FrameworkNativeResult,
        context: ResearchAdapterContext,
    ) -> ResearchProjection:
        """Derive and return a validated normalized research projection."""
        ...
