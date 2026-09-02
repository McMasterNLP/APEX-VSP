"""Sanitized full, resolved, and audit exports for annotation sets."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from core.time import serialize_utc_datetime, utc_now
from domain.models.research_annotation import (
    AnnotationExportRequest,
    REVIEWED_PROJECTION_LIMITATION,
)
from services.research_annotation_service import ResearchAnnotationService
from services.research_evaluation_run_service import ResearchEvaluationRunService
from services.research_export_service import (
    REDACTED_TRANSCRIPT_TEXT,
    sanitize_envelope_for_export,
)
from services.research_service import generate_anon_session_id

EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
    re.IGNORECASE,
)
REDACTED_EMAIL = "[EMAIL_REDACTED]"


@dataclass(frozen=True)
class ResearchAnnotationExportArtifact:
    content: bytes
    media_type: str
    filename: str


def _redact_string(value: str, transcript_texts: tuple[str, ...]) -> str:
    redacted = value
    for text in sorted(transcript_texts, key=len, reverse=True):
        if text:
            redacted = redacted.replace(text, REDACTED_TRANSCRIPT_TEXT)
    return EMAIL_PATTERN.sub(REDACTED_EMAIL, redacted)


def _sanitize_annotation_node(
    value: Any,
    transcript_texts: tuple[str, ...],
    *,
    redact_transcript_fields: bool = True,
) -> Any:
    if isinstance(value, list):
        return [
            _sanitize_annotation_node(
                item,
                transcript_texts,
                redact_transcript_fields=redact_transcript_fields,
            )
            for item in value
        ]
    if not isinstance(value, dict):
        return _redact_string(value, transcript_texts) if isinstance(value, str) else value
    output: dict[str, Any] = {}
    for key, item in value.items():
        if (
            redact_transcript_fields
            and key in {"quoted_text", "evidence_text", "text"}
            and isinstance(item, str)
        ):
            output[key] = REDACTED_TRANSCRIPT_TEXT if item else item
        else:
            output[key] = _sanitize_annotation_node(
                item,
                transcript_texts,
                redact_transcript_fields=redact_transcript_fields,
            )
    return output


class ResearchAnnotationExportService:
    """Render review artifacts while keeping transcript inclusion explicit."""

    def __init__(
        self,
        annotation_service: ResearchAnnotationService,
        run_service: ResearchEvaluationRunService,
    ):
        self.annotation_service = annotation_service
        self.run_service = run_service

    def render(
        self,
        annotation_set_uuid,
        request: AnnotationExportRequest,
    ) -> ResearchAnnotationExportArtifact:
        annotation_set = self.annotation_service.get_annotation_set(annotation_set_uuid)
        run = self.run_service.get_run(annotation_set.evaluation_run_uuid)
        transcript_texts = tuple(turn.text for turn in run.transcript_snapshot if turn.text)
        common = {
            "schema_version": "1.0",
            "profile": request.profile,
            "exported_at": serialize_utc_datetime(utc_now()),
            "raw_transcript_included": request.include_transcript_content,
            "scientific_limitation": REVIEWED_PROJECTION_LIMITATION,
            "run": {
                "run_uuid": str(run.run_uuid),
                "item1_run_id": run.envelope.run.run_id,
                "source_session_reference": generate_anon_session_id(
                    run.source_session_id
                ),
                "transcript_hash": run.envelope.transcript.canonical_transcript_hash,
                "transcript_projection_version": (
                    run.envelope.transcript.transcript_projection_version
                ),
                "evaluator": run.envelope.evaluator.model_dump(mode="json"),
                "framework": run.envelope.framework.model_dump(mode="json"),
                "adapter": run.envelope.adapter.model_dump(mode="json"),
                "creator_reference": run.creator_reference,
                "created_at": serialize_utc_datetime(run.created_at),
            },
            "annotation_set": {
                "annotation_set_uuid": str(annotation_set.annotation_set_uuid),
                "reviewer_reference": annotation_set.reviewer_reference,
                "guideline_identifier": annotation_set.guideline_identifier,
                "guideline_version": annotation_set.guideline_version,
                "annotation_policy": annotation_set.annotation_policy.model_dump(
                    mode="json"
                ),
                "status": annotation_set.status,
                "locked": annotation_set.locked,
                "revision": annotation_set.revision,
                "created_at": annotation_set.created_at,
                "updated_at": annotation_set.updated_at,
                "completed_at": annotation_set.completed_at,
                "locked_at": annotation_set.locked_at,
                "reopened_at": annotation_set.reopened_at,
                "set_note": annotation_set.set_note,
                "progress": annotation_set.progress.model_dump(mode="json"),
            },
        }

        if request.profile == "full_review":
            envelope = (
                run.envelope.model_dump(mode="json", exclude_none=True)
                if request.include_transcript_content
                else sanitize_envelope_for_export(
                    run.envelope, run.transcript_snapshot
                )
            )
            payload = {
                **common,
                "authoritative_envelope": envelope,
                "eligible_predictions": [
                    item.model_dump(mode="json")
                    for item in annotation_set.eligible_predictions
                ],
                "decision_revisions": [
                    item.model_dump(mode="json")
                    for item in annotation_set.decision_revisions
                ],
                "effective_decisions": [
                    item.model_dump(mode="json")
                    for item in annotation_set.effective_decisions
                ],
                "transitions": [
                    item.model_dump(mode="json") for item in annotation_set.transitions
                ],
                "resolved_projection": annotation_set.resolved_projection.model_dump(
                    mode="json"
                ),
            }
        elif request.profile == "resolved_projection":
            payload = {
                **common,
                "effective_decisions": [
                    item.model_dump(mode="json")
                    for item in annotation_set.effective_decisions
                ],
                "resolved_projection": annotation_set.resolved_projection.model_dump(
                    mode="json"
                ),
            }
        else:
            payload = {
                **common,
                "original_predictions": [
                    {
                        "prediction_id": item.prediction_id,
                        "projection_type": item.projection_type,
                        "original_prediction": item.original_prediction.model_dump(
                            mode="json"
                        ),
                    }
                    for item in annotation_set.eligible_predictions
                ],
                "decision_revisions": [
                    item.model_dump(mode="json")
                    for item in annotation_set.decision_revisions
                ],
                "transitions": [
                    item.model_dump(mode="json") for item in annotation_set.transitions
                ],
            }

        if request.include_transcript_content:
            payload["transcript_snapshot"] = [
                turn.model_dump(mode="json") for turn in run.transcript_snapshot
            ]
            payload["sensitive_data_warning"] = (
                "This explicitly requested export contains transcript text; "
                "email-like strings remain redacted."
            )
            payload = _sanitize_annotation_node(
                payload,
                (),
                redact_transcript_fields=False,
            )
        else:
            payload = _sanitize_annotation_node(payload, transcript_texts)

        return ResearchAnnotationExportArtifact(
            content=json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                default=str,
            ).encode("utf-8"),
            media_type="application/json",
            filename=f"apex_research_annotation_{request.profile}.json",
        )
