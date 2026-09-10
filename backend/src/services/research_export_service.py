"""Sanitized authoritative JSON and multi-table CSV research exports."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass
from typing import Any

from domain.models.research_evaluation import (
    ResearchEvaluationEnvelope,
    ResearchExportRequest,
    ResearchTranscriptTurn,
)

REDACTED_TRANSCRIPT_TEXT = "[TRANSCRIPT_TEXT_REDACTED]"


@dataclass(frozen=True)
class ResearchExportArtifact:
    content: bytes
    media_type: str
    filename: str


def _redact_string(value: str, raw_turn_texts: tuple[str, ...]) -> str:
    redacted = value
    for text in sorted(raw_turn_texts, key=len, reverse=True):
        if text:
            redacted = redacted.replace(text, REDACTED_TRANSCRIPT_TEXT)
    return redacted


def _sanitize_node(value: Any, raw_turn_texts: tuple[str, ...]) -> Any:
    if isinstance(value, list):
        return [_sanitize_node(item, raw_turn_texts) for item in value]
    if not isinstance(value, dict):
        return _redact_string(value, raw_turn_texts) if isinstance(value, str) else value

    is_span_like = "start_char" in value and "end_char" in value
    output: dict[str, Any] = {}
    for key, item in value.items():
        if key in {"quoted_text", "evidence_text", "patient_text"}:
            output[key] = REDACTED_TRANSCRIPT_TEXT if item else item
        elif key == "text" and (is_span_like or "span_id" in value):
            output[key] = REDACTED_TRANSCRIPT_TEXT if item else item
        else:
            output[key] = _sanitize_node(item, raw_turn_texts)
    return output


def sanitize_envelope_for_export(
    envelope: ResearchEvaluationEnvelope,
    transcript_turns: tuple[ResearchTranscriptTurn, ...],
) -> dict[str, Any]:
    """Remove raw transcript content while preserving result structure/provenance."""

    raw_turn_texts = tuple(turn.text for turn in transcript_turns if turn.text)
    payload = envelope.model_dump(mode="json", exclude_none=True)
    payload["transcript"]["raw_transcript_included"] = False
    return _sanitize_node(payload, raw_turn_texts)


class ResearchExportService:
    """Serialize validated envelopes without claiming CSV losslessness."""

    def render(
        self,
        request: ResearchExportRequest,
        transcript_turns: tuple[ResearchTranscriptTurn, ...],
    ) -> ResearchExportArtifact:
        transcript_hashes = {
            envelope.transcript.canonical_transcript_hash for envelope in request.envelopes
        }
        if len(transcript_hashes) != 1:
            raise ValueError("Export envelopes must share one canonical transcript hash.")
        sanitized = [
            sanitize_envelope_for_export(envelope, transcript_turns)
            for envelope in request.envelopes
        ]
        if request.profile == "tabular":
            return ResearchExportArtifact(
                content=self._render_tabular_zip(request.envelopes, transcript_turns),
                media_type="application/zip",
                filename="apex_research_tabular.zip",
            )
        payload = self._json_profile(sanitized, request.profile)
        return ResearchExportArtifact(
            content=json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
            media_type="application/json",
            filename=f"apex_research_{request.profile}.json",
        )

    @staticmethod
    def _json_profile(sanitized: list[dict[str, Any]], profile: str) -> dict[str, Any]:
        if profile == "full":
            results = sanitized
        elif profile == "framework_native":
            results = [
                {
                    "schema_version": item["schema_version"],
                    "run": item["run"],
                    "transcript": item["transcript"],
                    "evaluator": item["evaluator"],
                    "framework": item["framework"],
                    "adapter": item["adapter"],
                    "framework_result": item.get("framework_result"),
                    "status": item["status"],
                    "error": item.get("error"),
                }
                for item in sanitized
            ]
        elif profile == "projection":
            results = [
                {
                    "schema_version": item["schema_version"],
                    "run": item["run"],
                    "transcript": item["transcript"],
                    "evaluator": item["evaluator"],
                    "framework": item["framework"],
                    "adapter": item["adapter"],
                    "capabilities": item["capabilities"],
                    "projection": item["projection"],
                    "status": item["status"],
                    "error": item.get("error"),
                }
                for item in sanitized
            ]
        else:
            raise ValueError("Unsupported JSON research export profile.")
        return {
            "schema_version": "1.0",
            "profile": profile,
            "raw_transcript_included": False,
            "results": results,
        }

    def _render_tabular_zip(
        self,
        envelopes: tuple[ResearchEvaluationEnvelope, ...],
        transcript_turns: tuple[ResearchTranscriptTurn, ...],
    ) -> bytes:
        tables = self._tabular_rows(envelopes, transcript_turns)
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for filename, rows in tables.items():
                if filename != "runs.csv" and not rows:
                    continue
                content = self._csv(rows)
                info = zipfile.ZipInfo(filename=filename, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                bundle.writestr(info, content.encode("utf-8"))
        return output.getvalue()

    @staticmethod
    def _csv(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return ""
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return stream.getvalue()

    @staticmethod
    def _tabular_rows(
        envelopes: tuple[ResearchEvaluationEnvelope, ...],
        transcript_turns: tuple[ResearchTranscriptTurn, ...],
    ) -> dict[str, list[dict[str, Any]]]:
        raw_turn_texts = tuple(turn.text for turn in transcript_turns if turn.text)
        tables = {
            "runs.csv": [],
            "spans.csv": [],
            "turn_labels.csv": [],
            "relations.csv": [],
            "ratings.csv": [],
            "metrics.csv": [],
            "findings.csv": [],
            "limitations.csv": [],
        }
        for envelope in envelopes:
            common = {
                "schema_version": envelope.schema_version,
                "run_id": envelope.run.run_id,
                "transcript_hash": envelope.transcript.canonical_transcript_hash,
                "evaluator_identifier": envelope.evaluator.identifier,
                "evaluator_version": envelope.evaluator.version,
                "framework_identifier": envelope.framework.identifier,
                "framework_version": envelope.framework.version,
                "adapter_identifier": envelope.adapter.identifier,
                "adapter_version": envelope.adapter.version,
            }
            tables["runs.csv"].append(
                {
                    **common,
                    "status": envelope.status,
                    "timestamp": envelope.run.timestamp,
                    "runtime_ms": envelope.run.runtime_ms,
                    "execution_mode": envelope.run.execution_mode,
                    "provider": envelope.evaluator.provider or "",
                    "model_identifier": envelope.evaluator.model_identifier or "",
                    "failure_category": envelope.run.failure_category or "",
                }
            )
            for item in envelope.projection.spans:
                tables["spans.csv"].append(
                    {
                        **common,
                        "prediction_id": item.prediction_id,
                        "turn_number": item.turn_number,
                        "start_offset": item.start_offset,
                        "end_offset": item.end_offset,
                        "quoted_text": "",
                        "label": item.label,
                        "dimension": item.dimension or "",
                        "subtype": item.subtype or "",
                        "confidence": item.confidence if item.confidence is not None else "",
                        "source_path": item.source_reference.native_path,
                    }
                )
            for item in envelope.projection.turn_labels:
                tables["turn_labels.csv"].append(
                    {
                        **common,
                        "prediction_id": item.prediction_id,
                        "turn_number": item.turn_number,
                        "label": item.label,
                        "dimension": item.dimension or "",
                        "subtype": item.subtype or "",
                        "confidence": item.confidence if item.confidence is not None else "",
                        "source_path": item.source_reference.native_path,
                    }
                )
            for item in envelope.projection.relations:
                tables["relations.csv"].append(
                    {
                        **common,
                        "relation_id": item.relation_id,
                        "source_annotation_id": item.source_annotation_id,
                        "target_annotation_id": item.target_annotation_id,
                        "relation_type": item.relation_type,
                        "confidence": item.confidence if item.confidence is not None else "",
                        "source_path": item.source_reference.native_path,
                    }
                )
            for item in envelope.projection.dimension_ratings:
                tables["ratings.csv"].append(
                    {
                        **common,
                        "rating_id": item.rating_id,
                        "dimension_identifier": item.dimension_identifier,
                        "domain_identifier": item.domain_identifier or "",
                        "score": item.score if item.score is not None else "",
                        "scale_minimum": item.scale_minimum,
                        "scale_maximum": item.scale_maximum,
                        "score_status": item.score_status,
                        "assessability": item.assessability,
                        "confidence": item.confidence if item.confidence is not None else "",
                        "evidence_turns": "|".join(map(str, item.evidence_turns)),
                        "source_path": item.source_reference.native_path,
                    }
                )
            for item in envelope.projection.global_metrics:
                tables["metrics.csv"].append(
                    {
                        **common,
                        "metric_id": item.metric_id,
                        "metric_name": item.metric_name,
                        "value": item.value if item.value is not None else "",
                        "value_status": item.value_status,
                        "unit_or_scale": item.unit_or_scale,
                        "source_label": item.source_label,
                        "comparability_statement": item.comparability_statement,
                        "source_path": item.source_reference.native_path,
                    }
                )
            for item in envelope.projection.findings:
                tables["findings.csv"].append(
                    {
                        **common,
                        "finding_id": item.finding_id,
                        "finding_type": item.finding_type,
                        "description": _redact_string(item.description, raw_turn_texts),
                        "evidence_turns": "|".join(map(str, item.evidence_turns)),
                        "confidence": item.confidence if item.confidence is not None else "",
                        "source_path": item.source_reference.native_path,
                    }
                )
            for item in envelope.projection.limitations:
                tables["limitations.csv"].append(
                    {
                        **common,
                        "limitation_id": item.limitation_id,
                        "code": item.code,
                        "description": _redact_string(item.description, raw_turn_texts),
                        "affected_outputs": "|".join(item.affected_outputs),
                        "severity_or_scope": item.severity_or_scope,
                        "source_label": item.source_label,
                        "source_path": item.source_reference.native_path,
                    }
                )
        return tables
