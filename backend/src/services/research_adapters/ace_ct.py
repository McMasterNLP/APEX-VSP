"""Research adapter for the experimental ACE-CT-inspired evaluator."""

from __future__ import annotations

from domain.models.evaluator_comparison import EvaluatorRunResult
from domain.models.research_evaluation import (
    ACECTNativeResearchResult,
    COMPATIBILITY_COMPARABILITY_STATEMENT,
    DimensionRating,
    FrameworkNativeResult,
    GlobalMetric,
    OutputCapabilities,
    ProjectionProvenance,
    ResearchCapabilities,
    ResearchFinding,
    ResearchLimitation,
    ResearchProjection,
    SourceReference,
)
from services.research_adapters.base import ResearchAdapterContext
from services.research_adapters.identifiers import (
    canonical_result_digest,
    stable_research_identifier,
)

_ACE_NATIVE_COMPARABILITY = (
    "Native ACE-CT-inspired values are comparable only within this experimental rubric "
    "version; they do not establish official ACE-CT validity."
)

ACE_FRAMEWORK_FIELD_MAPPING = {
    "framework": "framework_results.framework",
    "implementation_type": "framework_results.implementation_type",
    "validation_status": "framework_results.validation_status",
    "publication_reproduction": "framework_results.publication_reproduction",
    "rubric_version": "framework_results.rubric_version",
    "approval_status": "framework_results.approval_status",
    "dimension_results": "framework_results.dimension_results and dimension_ratings",
    "domain_scores": "framework_results.domain_scores and global_metrics",
    "assessability_counts": "framework_results.assessability_counts",
    "score_sources": "framework_results.score_sources",
    "limitations": "framework_results.limitations and limitations",
}


class ACECTResearchAdapter:
    """Preserve complete ACE-CT-inspired semantics and derive generic ratings."""

    identifier = "ace-ct-inspired.adapter"
    version = "1.0"
    supported_native_types = ("ace_ct_inspired",)
    capabilities = ResearchCapabilities(
        outputs=OutputCapabilities(
            character_spans=False,
            turn_labels=False,
            relations=False,
            dimension_ratings=True,
            global_metrics=True,
            narrative_findings=True,
            evidence_turns=True,
            framework_native_view=True,
            live_execution=True,
        )
    )

    def build_native_result(
        self,
        result: EvaluatorRunResult,
        context: ResearchAdapterContext,
    ) -> FrameworkNativeResult:
        if result.status != "success" or result.framework_results is None:
            raise ValueError("ACE-CT adapter requires successful framework results.")
        if result.compatibility_projection is None:
            raise ValueError("ACE-CT adapter requires its compatibility projection.")
        if set(type(result.framework_results).model_fields) != set(
            ACE_FRAMEWORK_FIELD_MAPPING
        ):
            raise ValueError(
                "ACE-CT framework fields changed without an explicit research mapping."
            )
        return ACECTNativeResearchResult(
            framework_results=result.framework_results,
            compatibility_projection=result.compatibility_projection,
        )

    def project(
        self,
        native_result: FrameworkNativeResult,
        context: ResearchAdapterContext,
    ) -> ResearchProjection:
        if not isinstance(native_result, ACECTNativeResearchResult):
            raise ValueError("ACE-CT adapter requires an ace_ct_inspired native result.")
        digest = canonical_result_digest(native_result)

        def source(path: str) -> SourceReference:
            return SourceReference(
                native_result_type="ace_ct_inspired",
                native_identifier="ace-ct-inspired",
                native_path=path,
                adapter_version=self.version,
            )

        def identifier(prefix: str, projection_type: str, location: str) -> str:
            return stable_research_identifier(
                prefix,  # type: ignore[arg-type]
                transcript_hash=context.transcript_hash,
                evaluator_identifier=context.evaluator_identifier,
                framework_identifier=context.framework_identifier,
                native_identifier="ace-ct-inspired",
                adapter_version=self.version,
                projection_type=projection_type,
                object_location=location,
                native_result_digest=digest,
            )

        framework = native_result.framework_results
        ratings = tuple(
            DimensionRating(
                rating_id=identifier(
                    "rating",
                    "dimension_rating",
                    f"dimension_results.{result.dimension_id.value}",
                ),
                framework_identifier=context.framework_identifier,
                dimension_identifier=result.dimension_id.value,
                domain_identifier=result.domain.value,
                score=float(result.score) if result.score is not None else None,
                scale_minimum=1,
                scale_maximum=5,
                score_status=(
                    "not_assessable"
                    if result.assessability.value == "not_assessable"
                    else (
                        "insufficient_evidence"
                        if result.score is None
                        else "available"
                    )
                ),
                assessability=result.assessability.value,
                confidence=result.confidence,
                evidence_turns=result.evidence_turn_numbers,
                rationale=result.reasoning,
                source_reference=source(f"framework_results.dimension_results[{index}]"),
                provenance=ProjectionProvenance(method="native_model"),
            )
            for index, result in enumerate(framework.dimension_results)
        )

        metrics: list[GlobalMetric] = []
        for index, domain in enumerate(framework.domain_scores):
            metrics.append(
                GlobalMetric(
                    metric_id=identifier(
                        "metric", "global_metric", f"domain_scores.{domain.domain.value}"
                    ),
                    framework_identifier=context.framework_identifier,
                    metric_name=f"domain_{domain.domain.value}_mean",
                    value=domain.mean_score,
                    value_status=(
                        "available" if domain.mean_score is not None else "unavailable"
                    ),
                    unit_or_scale="native_ordinal_mean_1-5",
                    source_label="ACE-CT-inspired experimental domain aggregate",
                    comparability_statement=_ACE_NATIVE_COMPARABILITY,
                    source_reference=source(f"framework_results.domain_scores[{index}]"),
                    provenance=ProjectionProvenance(method="deterministic_adapter"),
                )
            )

        compatibility = native_result.compatibility_projection
        compatibility_sources = compatibility.score_sources.model_dump(mode="json")
        for name, value in compatibility.scores.model_dump(mode="json").items():
            metrics.append(
                GlobalMetric(
                    metric_id=identifier(
                        "metric", "global_metric", f"compatibility_projection.scores.{name}"
                    ),
                    framework_identifier=context.framework_identifier,
                    metric_name=f"compatibility_{name}",
                    value=value,
                    value_status="available" if value is not None else "unavailable",
                    unit_or_scale="engineering_projection_0-100",
                    source_label=compatibility_sources[name],
                    comparability_statement=COMPATIBILITY_COMPARABILITY_STATEMENT,
                    source_reference=source(f"compatibility_projection.scores.{name}"),
                    provenance=ProjectionProvenance(method="deterministic_adapter"),
                )
            )

        findings: list[ResearchFinding] = []
        for index, result in enumerate(framework.dimension_results):
            base = f"framework_results.dimension_results[{index}]"
            findings.extend(
                (
                    ResearchFinding(
                        finding_id=identifier(
                            "finding",
                            "finding",
                            f"dimension_results.{result.dimension_id.value}.rationale",
                        ),
                        framework_identifier=context.framework_identifier,
                        finding_type="general_observation",
                        description=result.reasoning,
                        evidence_turns=result.evidence_turn_numbers,
                        confidence=result.confidence,
                        source_reference=source(f"{base}.reasoning"),
                        provenance=ProjectionProvenance(method="native_model"),
                    ),
                    ResearchFinding(
                        finding_id=identifier(
                            "finding",
                            "finding",
                            f"dimension_results.{result.dimension_id.value}.improvement",
                        ),
                        framework_identifier=context.framework_identifier,
                        finding_type="improvement",
                        description=result.improvement_recommendation,
                        evidence_turns=result.evidence_turn_numbers,
                        confidence=result.confidence,
                        source_reference=source(f"{base}.improvement_recommendation"),
                        provenance=ProjectionProvenance(method="native_model"),
                    ),
                )
            )

        limitations: list[ResearchLimitation] = [
            ResearchLimitation(
                limitation_id=identifier(
                    "limitation", "limitation", "limitations.transcript_only"
                ),
                framework_identifier=context.framework_identifier,
                code="transcript_only_assessment",
                description="The experimental rubric assessment uses transcript text only.",
                affected_outputs=("dimension_ratings", "global_metrics", "findings"),
                severity_or_scope="framework",
                source_label="ACE-CT-inspired framework result",
                source_reference=source("framework_results.limitations.transcript_only"),
                provenance=ProjectionProvenance(method="deterministic_adapter"),
            ),
            ResearchLimitation(
                limitation_id=identifier(
                    "limitation", "limitation", "validation_status.experimental"
                ),
                framework_identifier=context.framework_identifier,
                code="experimental_unvalidated_rubric",
                description=(
                    "Experimental, unvalidated, non-official, and not a reproduction of "
                    "the confidential manuscript's trained models."
                ),
                affected_outputs=("dimension_ratings", "global_metrics", "findings"),
                severity_or_scope="framework",
                source_label="ACE-CT-inspired validation status",
                source_reference=source("framework_results.validation_status"),
                provenance=ProjectionProvenance(method="deterministic_adapter"),
            ),
        ]
        for index, modality in enumerate(framework.limitations.missing_modalities):
            limitations.append(
                ResearchLimitation(
                    limitation_id=identifier(
                        "limitation", "limitation", f"missing_modalities.{modality}"
                    ),
                    framework_identifier=context.framework_identifier,
                    code=f"missing_{modality}",
                    description=f"The {modality} modality is unavailable to this assessment.",
                    affected_outputs=("dimension_ratings", "findings"),
                    severity_or_scope="output",
                    source_label="ACE-CT-inspired modality declaration",
                    source_reference=source(
                        f"framework_results.limitations.missing_modalities[{index}]"
                    ),
                    provenance=ProjectionProvenance(method="deterministic_adapter"),
                )
            )
        return ResearchProjection(
            dimension_ratings=ratings,
            global_metrics=tuple(metrics),
            findings=tuple(findings),
            limitations=tuple(limitations),
        )
