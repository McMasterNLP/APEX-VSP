"""Typed in-memory results produced by the deterministic scoring core."""

from typing import Any

from pydantic import BaseModel, ConfigDict

from domain.models.sessions import SuggestedResponse, TimelineEvent


class ComputedFeedback(BaseModel):
    """Complete scoring output calculated before any database persistence."""

    session_id: int
    empathy_score: float
    communication_score: float
    spikes_completion_score: float
    overall_score: float

    eo_counts_by_dimension: dict[str, Any]
    elicitation_counts_by_type: dict[str, Any]
    response_counts_by_type: dict[str, Any]
    linkage_stats: dict[str, Any] | None = None
    missed_opportunities_by_dimension: dict[str, Any] | None = None
    eo_to_elicitation_links: dict[str, Any] | None = None
    eo_to_response_links: dict[str, Any] | None = None
    missed_opportunities: list[Any] | None = None

    eo_spans: list[dict[str, Any]]
    elicitation_spans: list[dict[str, Any]]
    response_spans: list[dict[str, Any]]

    spikes_coverage: dict[str, Any]
    spikes_timestamps: dict[str, Any] | None = None
    spikes_strategies: dict[str, Any] | None = None
    question_breakdown: dict[str, Any]

    bias_probe_info: dict[str, Any] | None = None
    evaluator_meta: dict[str, Any]
    latency_ms_avg: float

    strengths: str | None = None
    areas_for_improvement: str | None = None
    detailed_feedback: str | None = None
    timeline_events: list[TimelineEvent] | None = None
    suggested_responses: list[SuggestedResponse] | None = None

    model_config = ConfigDict(frozen=True)
