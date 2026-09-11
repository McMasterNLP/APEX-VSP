"""Sanitized exports for immutable Item 3A validation runs.

@remarks
Mirrors `research_annotation_export_service.py`'s pattern: constructor
injection, a `render(...) -> artifact` frozen-dataclass return, profile
branching, and reuse of `pseudonymous_reviewer_reference`/email redaction --
never raw reviewer identity. A validation run's `results` payload never
contains transcript quoted text (only span-classification counts and exact
fraction strings), so the only sensitive content this export can ever surface
is the optional raw transcript snapshot itself, gated by
`include_transcript_content` exactly as Item 2A's export does.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from uuid import UUID

from core.time import serialize_utc_datetime, utc_now
from domain.models.research_validation import ValidationRunExportRequest
from services.research_evaluation_run_service import ResearchEvaluationRunService
from services.research_validation_service import ResearchValidationService

EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
    re.IGNORECASE,
)
REDACTED_EMAIL = "[EMAIL_REDACTED]"


@dataclass(frozen=True)
class ResearchValidationExportArtifact:
    content: bytes
    media_type: str
    filename: str


def _redact_emails(value: str) -> str:
    return EMAIL_PATTERN.sub(REDACTED_EMAIL, value)


def _sanitize(value: object) -> object:
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    if isinstance(value, str):
        return _redact_emails(value)
    return value


class ResearchValidationExportService:
    """Render a validation-run export artifact, transcript inclusion explicit."""

    def __init__(
        self,
        validation_service: ResearchValidationService,
        run_service: ResearchEvaluationRunService,
    ):
        self.validation_service = validation_service
        self.run_service = run_service

    def render(
        self,
        validation_run_uuid: UUID,
        request: ValidationRunExportRequest,
    ) -> ResearchValidationExportArtifact:
        validation_run = self.validation_service.get_validation_run(validation_run_uuid)
        payload: dict[str, object] = {
            "schema_version": "1.0",
            "profile": request.profile,
            "exported_at": serialize_utc_datetime(utc_now()),
            "raw_transcript_included": request.include_transcript_content,
            "validation_run": {
                "validation_run_uuid": str(validation_run.validation_run_uuid),
                "evaluation_run_uuid": str(validation_run.evaluation_run_uuid),
                "annotation_set_uuid": str(validation_run.annotation_set_uuid),
                "annotation_set_revision_at_validation": (
                    validation_run.annotation_set_revision_at_validation
                ),
                "transcript_hash": validation_run.transcript_hash,
                "evaluator_identifier": validation_run.evaluator_identifier,
                "evaluator_version": validation_run.evaluator_version,
                "matching_policy_identifier": validation_run.matching_policy_identifier,
                "matching_policy_version": validation_run.matching_policy_version,
                "metric_implementation_version": validation_run.metric_implementation_version,
                "coverage_level": validation_run.coverage_level,
                "created_by_reference": validation_run.created_by_reference,
                "created_at": serialize_utc_datetime(validation_run.created_at),
                "warnings": list(validation_run.warnings),
            },
            "results": validation_run.results.model_dump(mode="json"),
        }

        if request.profile == "full" and request.include_transcript_content:
            run = self.run_service.get_run(validation_run.evaluation_run_uuid)
            payload["transcript_snapshot"] = [
                turn.model_dump(mode="json") for turn in run.transcript_snapshot
            ]
            payload["sensitive_data_warning"] = (
                "This explicitly requested export contains transcript text; email-like "
                "strings remain redacted."
            )

        payload = _sanitize(payload)
        return ResearchValidationExportArtifact(
            content=json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode(
                "utf-8"
            ),
            media_type="application/json",
            filename=f"apex_research_validation_{request.profile}.json",
        )
