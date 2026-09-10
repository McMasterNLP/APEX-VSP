"""Research adapter for APEX baseline and shared hybrid native feedback."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import JsonValue, TypeAdapter

from domain.models.evaluator_comparison import EvaluatorRunResult
from domain.models.research_evaluation import (
    AFCE_IMPLEMENTATION_STATEMENT,
    ApexExplicitImplicitCounts,
    ApexFeedbackNativeResult,
    ApexLinkageStats,
    ApexMissedOpportunity,
    ApexNativeRelation,
    ApexNativeSpan,
    ApexQuestionBreakdown,
    ApexScores,
    ApexSpikesCoverage,
    ApexSuggestedResponse,
    ApexTimelineEvent,
    FrameworkNativeResult,
    GlobalMetric,
    AnnotationOperationCapabilities,
    OutputCapabilities,
    ProjectionAnnotationCapabilities,
    ProjectedRelation,
    ProjectionProvenance,
    ResearchCapabilities,
    ResearchFinding,
    ResearchLimitation,
    ResearchProjection,
    SourceReference,
    SpanAnnotation,
    TurnLabel,
)
from services.research_adapters.base import ResearchAdapterContext
from services.research_adapters.identifiers import (
    canonical_result_digest,
    stable_research_identifier,
)

_JSON_DICT = TypeAdapter(dict[str, JsonValue])
_APEX_COMPARABILITY = (
    "Comparable only within the declared APEX scoring and adapter versions; "
    "no equivalence to another framework is implied."
)

APEX_COMPUTED_FEEDBACK_FIELD_MAPPING = {
    "session_id": "not exported: internal lookup coordinate",
    "empathy_score": "scores.empathy_score",
    "communication_score": "scores.communication_score",
    "spikes_completion_score": "scores.spikes_completion_score",
    "overall_score": "scores.overall_score",
    "eo_counts_by_dimension": "eo_counts_by_dimension",
    "elicitation_counts_by_type": "elicitation_counts_by_type",
    "response_counts_by_type": "response_counts_by_type",
    "linkage_stats": "linkage_stats",
    "missed_opportunities_by_dimension": "missed_opportunities_by_dimension",
    "eo_to_elicitation_links": "eo_to_elicitation_links",
    "eo_to_response_links": "eo_to_response_links",
    "missed_opportunities": "missed_opportunities",
    "eo_spans": "eo_spans",
    "elicitation_spans": "elicitation_spans",
    "response_spans": "response_spans",
    "spikes_coverage": "spikes_coverage",
    "spikes_timestamps": "spikes_timestamps",
    "spikes_strategies": "spikes_strategies",
    "question_breakdown": "question_breakdown",
    "bias_probe_info": "bias_probe_info",
    "evaluator_meta": "evaluator_metadata",
    "latency_ms_avg": "latency_ms_avg",
    "strengths": "strengths",
    "areas_for_improvement": "areas_for_improvement",
    "detailed_feedback": "detailed_feedback",
    "timeline_events": "timeline_events",
    "suggested_responses": "suggested_responses",
}


def _json_dict(value: dict[str, Any] | None) -> dict[str, JsonValue] | None:
    if value is None:
        return None
    return _JSON_DICT.validate_python(value)


def _flatten_relations(
    value: Any,
    *,
    expected_type: str,
) -> tuple[ApexNativeRelation, ...]:
    if value is None:
        return ()
    if not isinstance(value, dict):
        raise ValueError("APEX native relation collections must be dictionaries.")
    relations: list[ApexNativeRelation] = []
    for source_id, rows in value.items():
        if not isinstance(rows, list):
            raise ValueError("APEX native relation entries must be lists.")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("APEX native relations must be objects.")
            if row.get("source_span_id") != source_id:
                raise ValueError("APEX native relation source key does not match its row.")
            if row.get("relation_type") != expected_type:
                raise ValueError("APEX native relation has an unsupported type.")
            relations.append(ApexNativeRelation.model_validate(row))
    return tuple(relations)


class ApexResearchAdapter:
    """Preserve complete APEX feedback and derive common research objects."""

    identifier = "apex.feedback.adapter"
    version = "1.0"
    supported_native_types = ("apex_feedback",)

    def __init__(self, *, live_execution: bool):
        self.capabilities = ResearchCapabilities(
            outputs=OutputCapabilities(
                character_spans=True,
                turn_labels=True,
                relations=True,
                dimension_ratings=False,
                global_metrics=True,
                narrative_findings=True,
                evidence_turns=True,
                framework_native_view=True,
                live_execution=live_execution,
            ),
            annotation_operations=AnnotationOperationCapabilities(
                confirm=True,
                reject=True,
                change_label=True,
                change_dimension=True,
            ),
            annotation_by_projection=ProjectionAnnotationCapabilities(
                span_annotation=AnnotationOperationCapabilities(
                    confirm=True,
                    reject=True,
                    change_label=True,
                    change_dimension=True,
                ),
                turn_label=AnnotationOperationCapabilities(
                    confirm=True,
                    reject=True,
                    change_label=True,
                    change_dimension=True,
                ),
                relation=AnnotationOperationCapabilities(confirm=True, reject=True),
                finding=AnnotationOperationCapabilities(confirm=True, reject=True),
            ),
        )

    @staticmethod
    def _native_span(
        raw: dict[str, Any],
        *,
        expected_type: str,
        turn_text_by_number: dict[int, str],
    ) -> ApexNativeSpan:
        if not isinstance(raw, dict):
            raise ValueError("APEX span output must contain objects.")
        turn_number = raw.get("turn_number")
        start = raw.get("start_char")
        end = raw.get("end_char")
        text = raw.get("text")
        if turn_number not in turn_text_by_number:
            raise ValueError("APEX native span references an unknown turn.")
        if not isinstance(start, int) or isinstance(start, bool):
            raise ValueError("APEX native span start_char must be an integer.")
        if not isinstance(end, int) or isinstance(end, bool):
            raise ValueError("APEX native span end_char must be an integer.")
        turn_text = turn_text_by_number[turn_number]
        if start < 0 or end <= start or end > len(turn_text):
            raise ValueError("APEX native span offsets are outside the source turn.")
        if text != turn_text[start:end]:
            raise ValueError("APEX native span text does not exactly match its offsets.")
        return ApexNativeSpan(
            span_type=expected_type,
            turn_number=turn_number,
            start_char=start,
            end_char=end,
            text=text,
            confidence=raw.get("confidence"),
            provenance=raw.get("provenance"),
            dimension=raw.get("dimension"),
            explicit_or_implicit=raw.get("explicit_or_implicit"),
            subtype=raw.get("type"),
        )

    def build_native_result(
        self,
        result: EvaluatorRunResult,
        context: ResearchAdapterContext,
    ) -> FrameworkNativeResult:
        if result.status != "success" or result.structured_feedback is None:
            raise ValueError("APEX adapter requires successful structured feedback.")
        if context.evaluator_identifier not in {"baseline", "hybrid_v1", "hybrid_v2"}:
            raise ValueError("APEX adapter received an unsupported evaluator family.")
        feedback = result.structured_feedback
        if set(type(feedback).model_fields) != set(APEX_COMPUTED_FEEDBACK_FIELD_MAPPING):
            raise ValueError(
                "ComputedFeedback fields changed without an explicit APEX research mapping."
            )
        turn_text_by_number = {
            turn.turn_number: turn.text for turn in context.transcript_turns
        }

        eo_spans = tuple(
            self._native_span(
                span,
                expected_type="eo",
                turn_text_by_number=turn_text_by_number,
            )
            for span in feedback.eo_spans
        )
        elicitation_spans = tuple(
            self._native_span(
                span,
                expected_type="elicitation",
                turn_text_by_number=turn_text_by_number,
            )
            for span in feedback.elicitation_spans
        )
        response_spans = tuple(
            self._native_span(
                span,
                expected_type="response",
                turn_text_by_number=turn_text_by_number,
            )
            for span in feedback.response_spans
        )
        role_by_number = {
            turn.turn_number: turn.role for turn in context.transcript_turns
        }
        if any(role_by_number[span.turn_number] != "patient" for span in eo_spans):
            raise ValueError("APEX empathy opportunities must be attributed to patient turns.")
        if any(
            role_by_number[span.turn_number] != "clinician"
            for span in (*elicitation_spans, *response_spans)
        ):
            raise ValueError(
                "APEX elicitations and responses must be attributed to clinician turns."
            )

        return ApexFeedbackNativeResult(
            evaluator_family=context.evaluator_identifier,
            scores=ApexScores(
                empathy_score=feedback.empathy_score,
                communication_score=feedback.communication_score,
                spikes_completion_score=feedback.spikes_completion_score,
                overall_score=feedback.overall_score,
            ),
            eo_counts_by_dimension={
                dimension: ApexExplicitImplicitCounts.model_validate(counts)
                for dimension, counts in feedback.eo_counts_by_dimension.items()
            },
            elicitation_counts_by_type=feedback.elicitation_counts_by_type,
            response_counts_by_type=feedback.response_counts_by_type,
            linkage_stats=(
                ApexLinkageStats.model_validate(feedback.linkage_stats)
                if feedback.linkage_stats is not None
                else None
            ),
            missed_opportunities_by_dimension=feedback.missed_opportunities_by_dimension,
            eo_to_elicitation_links=_flatten_relations(
                feedback.eo_to_elicitation_links,
                expected_type="elicits",
            ),
            eo_to_response_links=_flatten_relations(
                feedback.eo_to_response_links,
                expected_type="responds_to",
            ),
            missed_opportunities=tuple(
                ApexMissedOpportunity.model_validate(item)
                for item in (feedback.missed_opportunities or [])
            ),
            eo_spans=eo_spans,
            elicitation_spans=elicitation_spans,
            response_spans=response_spans,
            spikes_coverage=ApexSpikesCoverage.model_validate(feedback.spikes_coverage),
            spikes_timestamps=_json_dict(feedback.spikes_timestamps),
            spikes_strategies=_json_dict(feedback.spikes_strategies),
            question_breakdown=ApexQuestionBreakdown.model_validate(
                feedback.question_breakdown
            ),
            bias_probe_info=_json_dict(feedback.bias_probe_info),
            evaluator_metadata=_json_dict(feedback.evaluator_meta) or {},
            latency_ms_avg=feedback.latency_ms_avg,
            strengths=feedback.strengths,
            areas_for_improvement=feedback.areas_for_improvement,
            detailed_feedback=feedback.detailed_feedback,
            timeline_events=tuple(
                ApexTimelineEvent.model_validate(event.model_dump())
                for event in (feedback.timeline_events or [])
            ),
            suggested_responses=tuple(
                ApexSuggestedResponse.model_validate(response.model_dump())
                for response in (feedback.suggested_responses or [])
            ),
        )

    def project(
        self,
        native_result: FrameworkNativeResult,
        context: ResearchAdapterContext,
    ) -> ResearchProjection:
        if not isinstance(native_result, ApexFeedbackNativeResult):
            raise ValueError("APEX adapter requires an apex_feedback native result.")
        digest = canonical_result_digest(native_result)

        def source(path: str) -> SourceReference:
            return SourceReference(
                native_result_type="apex_feedback",
                native_identifier="apex-spikes-afce",
                native_path=path,
                adapter_version=self.version,
            )

        def identifier(prefix: str, projection_type: str, location: str) -> str:
            return stable_research_identifier(
                prefix,  # type: ignore[arg-type]
                transcript_hash=context.transcript_hash,
                evaluator_identifier=context.evaluator_identifier,
                framework_identifier=context.framework_identifier,
                native_identifier="apex-spikes-afce",
                adapter_version=self.version,
                projection_type=projection_type,
                object_location=location,
                native_result_digest=digest,
            )

        projected_spans: list[SpanAnnotation] = []
        native_alias_to_projection_id: dict[str, str] = {}
        span_groups: tuple[tuple[str, tuple[ApexNativeSpan, ...]], ...] = (
            ("eo_spans", native_result.eo_spans),
            ("elicitation_spans", native_result.elicitation_spans),
            ("response_spans", native_result.response_spans),
        )
        for group_name, spans in span_groups:
            for index, span in enumerate(spans):
                location = (
                    f"{group_name}[{index}].turn-{span.turn_number}."
                    f"chars-{span.start_char}-{span.end_char}"
                )
                prediction_id = identifier("span", "span_annotation", location)
                if group_name == "eo_spans":
                    native_alias = f"eo_{index + 1}"
                    label = "empathic_opportunity"
                    subtype = span.explicit_or_implicit
                elif group_name == "elicitation_spans":
                    native_alias = f"elic_{len(native_result.eo_spans) + index + 1}"
                    label = "elicitation"
                    subtype = span.subtype
                else:
                    native_alias = f"resp_{len(native_result.eo_spans) + index + 1}"
                    label = "empathic_response"
                    subtype = span.subtype
                native_alias_to_projection_id[native_alias] = prediction_id
                projected_spans.append(
                    SpanAnnotation(
                        prediction_id=prediction_id,
                        framework_identifier=context.framework_identifier,
                        turn_number=span.turn_number,
                        start_offset=span.start_char,
                        end_offset=span.end_char,
                        quoted_text=span.text,
                        label=label,
                        dimension=span.dimension,
                        subtype=subtype,
                        confidence=span.confidence,
                        source_reference=source(f"{group_name}[{index}]"),
                        provenance=ProjectionProvenance(
                            method=(
                                "native_rule"
                                if span.provenance in {None, "rule"}
                                else "native_model"
                            )
                        ),
                    )
                )

        projected_relations: list[ProjectedRelation] = []
        relation_groups: tuple[tuple[str, tuple[ApexNativeRelation, ...]], ...] = (
            ("eo_to_elicitation_links", native_result.eo_to_elicitation_links),
            ("eo_to_response_links", native_result.eo_to_response_links),
        )
        for group_name, relations in relation_groups:
            for index, relation in enumerate(relations):
                source_id = native_alias_to_projection_id.get(relation.source_span_id)
                target_id = native_alias_to_projection_id.get(relation.target_span_id)
                if source_id is None or target_id is None:
                    raise ValueError("APEX native relation endpoint cannot be projected.")
                location = (
                    f"{group_name}[{index}].{relation.source_span_id}."
                    f"{relation.target_span_id}"
                )
                projected_relations.append(
                    ProjectedRelation(
                        relation_id=identifier("relation", "relation", location),
                        framework_identifier=context.framework_identifier,
                        source_annotation_id=source_id,
                        target_annotation_id=target_id,
                        relation_type=relation.relation_type,
                        confidence=relation.confidence,
                        source_reference=source(f"{group_name}[{index}]"),
                        provenance=ProjectionProvenance(method="deterministic_adapter"),
                    )
                )

        turn_labels = self._project_turn_labels(native_result, identifier, source, context)
        metrics = self._project_metrics(native_result, identifier, source, context)
        findings = self._project_findings(native_result, identifier, source, context)
        limitations = self._project_limitations(native_result, identifier, source, context)
        return ResearchProjection(
            spans=tuple(projected_spans),
            turn_labels=turn_labels,
            relations=tuple(projected_relations),
            global_metrics=metrics,
            findings=findings,
            limitations=limitations,
        )

    @staticmethod
    def _project_turn_labels(native_result, identifier, source, context):
        rows: list[tuple[int, str, str]] = []
        llm_output = native_result.evaluator_metadata.get("llm_output")
        mapping = llm_output.get("stage_turn_mapping") if isinstance(llm_output, dict) else None
        if isinstance(mapping, list):
            for index, row in enumerate(mapping):
                if isinstance(row, dict) and isinstance(row.get("turn_number"), int):
                    rows.append(
                        (
                            row["turn_number"],
                            str(row.get("stage") or "unknown"),
                            f"evaluator_metadata.llm_output.stage_turn_mapping[{index}]",
                        )
                    )
        if not rows:
            rows = [
                (event.turn_number, event.label.removeprefix("SPIKES "), f"timeline_events[{i}]")
                for i, event in enumerate(native_result.timeline_events)
                if event.type == "spikes"
            ]
        return tuple(
            TurnLabel(
                prediction_id=identifier(
                    "turn", "turn_label", f"{path}.turn-{turn_number}.{stage}"
                ),
                framework_identifier=context.framework_identifier,
                turn_number=turn_number,
                label="spikes_stage",
                subtype=stage.lower().replace(" ", "_"),
                source_reference=source(path),
                provenance=ProjectionProvenance(method="deterministic_adapter"),
            )
            for turn_number, stage, path in rows
        )

    @staticmethod
    def _project_metrics(native_result, identifier, source, context):
        score_items = (
            ("empathy_score", native_result.scores.empathy_score),
            ("communication_score", native_result.scores.communication_score),
            ("spikes_completion_score", native_result.scores.spikes_completion_score),
            ("overall_score", native_result.scores.overall_score),
        )
        metrics = [
            GlobalMetric(
                metric_id=identifier("metric", "global_metric", f"scores.{name}"),
                framework_identifier=context.framework_identifier,
                metric_name=name,
                value=value,
                value_status="available",
                unit_or_scale="0-100",
                source_label=f"APEX {native_result.native_version}",
                comparability_statement=_APEX_COMPARABILITY,
                source_reference=source(f"scores.{name}"),
                provenance=ProjectionProvenance(method="deterministic_adapter"),
            )
            for name, value in score_items
        ]
        if native_result.linkage_stats is not None:
            for name in ("addressed_rate", "missed_rate"):
                metrics.append(
                    GlobalMetric(
                        metric_id=identifier(
                            "metric", "global_metric", f"linkage_stats.{name}"
                        ),
                        framework_identifier=context.framework_identifier,
                        metric_name=f"empathic_opportunity_{name}",
                        value=getattr(native_result.linkage_stats, name),
                        value_status="available",
                        unit_or_scale="proportion_0-1",
                        source_label="APEX opportunity-response linking",
                        comparability_statement=_APEX_COMPARABILITY,
                        source_reference=source(f"linkage_stats.{name}"),
                        provenance=ProjectionProvenance(method="deterministic_adapter"),
                    )
                )
        return tuple(metrics)

    @staticmethod
    def _project_findings(native_result, identifier, source, context):
        findings: list[ResearchFinding] = []

        def add(kind: str, description: str | None, path: str, turns: Iterable[int] = ()):
            if not description or not description.strip():
                return
            evidence = tuple(sorted(set(turns)))
            findings.append(
                ResearchFinding(
                    finding_id=identifier(
                        "finding", "finding", f"{path}.item-{len(findings)}"
                    ),
                    framework_identifier=context.framework_identifier,
                    finding_type=kind,
                    description=description.strip(),
                    evidence_turns=evidence,
                    source_reference=source(path),
                    provenance=ProjectionProvenance(method="deterministic_adapter"),
                )
            )

        add("strength", native_result.strengths, "strengths")
        add("improvement", native_result.areas_for_improvement, "areas_for_improvement")
        add("general_observation", native_result.detailed_feedback, "detailed_feedback")
        for index, missed in enumerate(native_result.missed_opportunities):
            description = "Missed empathic opportunity"
            if missed.dimension:
                description += f" ({missed.dimension})"
            add(
                "missed_opportunity",
                description + ".",
                f"missed_opportunities[{index}]",
                (missed.turn_number,),
            )
        for index, suggestion in enumerate(native_result.suggested_responses):
            add(
                "improvement",
                suggestion.suggestion,
                f"suggested_responses[{index}]",
                (suggestion.turn_number,),
            )
        return tuple(findings)

    @staticmethod
    def _project_limitations(native_result, identifier, source, context):
        rows = [
            (
                "transcript_only_assessment",
                "The selected communication constructs are assessed primarily from transcript text; audio, timing, overlap, and non-verbal behavior are not fully represented.",
                ("spans", "turn_labels", "metrics", "findings"),
                "framework_statement",
            ),
            (
                "afce_selected_constructs",
                AFCE_IMPLEMENTATION_STATEMENT,
                ("spans", "relations", "metrics"),
                "framework_statement",
            ),
        ]
        if native_result.evaluator_family != "baseline":
            rows.append(
                (
                    "provider_variability",
                    "Hybrid narrative and score components may vary across model/provider executions.",
                    ("metrics", "findings", "turn_labels"),
                    "evaluator_metadata",
                )
            )
        return tuple(
            ResearchLimitation(
                limitation_id=identifier(
                    "limitation", "limitation", f"{path}.{code}"
                ),
                framework_identifier=context.framework_identifier,
                code=code,
                description=description,
                affected_outputs=affected,
                severity_or_scope="framework",
                source_label="APEX research adapter",
                source_reference=source(path),
                provenance=ProjectionProvenance(method="deterministic_adapter"),
            )
            for code, description, affected, path in rows
        )
