"""Versioned framework-aware annotation policies for Item 2A."""

from __future__ import annotations

from domain.models.research_annotation import (
    AnnotationPolicyDescriptor,
    LabelPolicy,
    RatingScalePolicy,
    ReviewablePrediction,
    prediction_identifier,
)
from domain.models.research_evaluation import (
    AnnotationOperationCapabilities,
    ProjectionAnnotationCapabilities,
    ResearchEvaluationEnvelope,
)


class AnnotationPolicyError(ValueError):
    """An envelope or requested guideline is unsupported for annotation."""


APEX_GUIDELINE_IDENTIFIER = "apex-afce-expert-review"
APEX_GUIDELINE_VERSION = "1.0"
ACE_GUIDELINE_IDENTIFIER = "ace-ct-experimental-expert-review"
ACE_GUIDELINE_VERSION = "0.1.0-experimental"


def _apex_operations() -> ProjectionAnnotationCapabilities:
    return ProjectionAnnotationCapabilities(
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
    )


def _ace_operations() -> ProjectionAnnotationCapabilities:
    return ProjectionAnnotationCapabilities(
        dimension_rating=AnnotationOperationCapabilities(
            confirm=True,
            change_rating=True,
            mark_insufficient_evidence=True,
            change_evidence=True,
        ),
        finding=AnnotationOperationCapabilities(confirm=True, reject=True),
    )


def policy_for_envelope(envelope: ResearchEvaluationEnvelope) -> AnnotationPolicyDescriptor:
    """Build the supported policy from framework/native versioned semantics."""

    if envelope.status != "success":
        raise AnnotationPolicyError("Only successful evaluation runs can be annotated.")
    if envelope.schema_version != "1.0":
        raise AnnotationPolicyError("The evaluation envelope schema is not supported.")

    if envelope.framework.identifier == "apex-spikes-afce":
        if envelope.adapter.identifier != "apex.feedback.adapter" or envelope.adapter.version != "1.0":
            raise AnnotationPolicyError("The APEX adapter version is not supported for review.")
        return AnnotationPolicyDescriptor(
            policy_identifier="apex-afce-annotation-policy",
            policy_version="1.0",
            guideline_identifier=APEX_GUIDELINE_IDENTIFIER,
            guideline_version=APEX_GUIDELINE_VERSION,
            guideline_validation_status="engineering_unvalidated",
            framework_identifier=envelope.framework.identifier,
            supported_adapter_versions=("1.0",),
            operations=_apex_operations(),
            label_policies=(
                LabelPolicy(
                    projection_type="span_annotation",
                    allowed_labels=(
                        "elicitation",
                        "empathic_opportunity",
                        "empathic_response",
                    ),
                    allowed_dimensions=("Feeling", "Judgment", "Appreciation"),
                ),
                LabelPolicy(
                    projection_type="turn_label",
                    allowed_labels=("spikes_stage",),
                    allowed_dimensions=(
                        "setting",
                        "perception",
                        "invitation",
                        "knowledge",
                        "empathy",
                        "strategy_summary",
                    ),
                ),
            ),
        )

    if envelope.framework.identifier == "ace-ct-inspired":
        if envelope.adapter.identifier != "ace-ct-inspired.adapter" or envelope.adapter.version != "1.0":
            raise AnnotationPolicyError("The ACE-CT-inspired adapter version is unsupported.")
        scales = tuple(
            RatingScalePolicy(
                dimension_identifier=rating.dimension_identifier,
                allowed_scores=tuple(
                    float(value)
                    for value in range(
                        int(rating.scale_minimum), int(rating.scale_maximum) + 1
                    )
                ),
            )
            for rating in envelope.projection.dimension_ratings
        )
        return AnnotationPolicyDescriptor(
            policy_identifier="ace-ct-experimental-annotation-policy",
            policy_version="0.1.0-experimental",
            guideline_identifier=ACE_GUIDELINE_IDENTIFIER,
            guideline_version=ACE_GUIDELINE_VERSION,
            guideline_validation_status="experimental_unvalidated",
            framework_identifier=envelope.framework.identifier,
            supported_adapter_versions=("1.0",),
            operations=_ace_operations(),
            rating_scales=scales,
        )

    raise AnnotationPolicyError("This framework has no approved Item 2A annotation policy.")


def eligible_prediction_inventory(
    envelope: ResearchEvaluationEnvelope,
    policy: AnnotationPolicyDescriptor,
) -> tuple[ReviewablePrediction, ...]:
    """Capture the stable reviewable prediction inventory for one saved run."""

    projection = envelope.projection
    collections = (
        projection.spans,
        projection.turn_labels,
        projection.relations,
        projection.dimension_ratings,
        projection.findings,
    )
    predictions = tuple(item for collection in collections for item in collection)
    inventory: list[ReviewablePrediction] = []
    for prediction in predictions:
        operations = getattr(policy.operations, prediction.projection_type)
        if not (operations.confirm or operations.reject):
            continue
        inventory.append(
            ReviewablePrediction(
                prediction_id=prediction_identifier(prediction),
                projection_type=prediction.projection_type,
                original_prediction=prediction,
                allowed_operations=operations,
            )
        )
    return tuple(inventory)


def validate_requested_guideline(
    policy: AnnotationPolicyDescriptor,
    guideline_identifier: str,
    guideline_version: str,
) -> None:
    if (
        guideline_identifier != policy.guideline_identifier
        or guideline_version != policy.guideline_version
    ):
        raise AnnotationPolicyError(
            "The requested guideline is incompatible with this saved evaluation run."
        )
