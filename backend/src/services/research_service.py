"""Research service for data anonymization and export."""

import csv
import hashlib
import json
import re
from io import StringIO
from typing import Any, Iterator
from uuid import uuid4

from sqlalchemy.orm import Session

from config.settings import get_settings
from core.time import json_utc_default, serialize_utc_datetime, utc_now
from domain.entities.case import Case
from domain.models.admin import ResearchExportRequest, ResearchExportResponse
from repositories.case_repo import CaseRepository
from repositories.feedback_repo import FeedbackRepository
from repositories.session_repo import SessionRepository
from repositories.turn_repo import TurnRepository


def generate_anon_session_id(session_id: int) -> str:
    """Deterministic anonymized session ID. Never expose raw session_id in research API."""
    salt = get_settings().research_anon_salt
    h = hashlib.sha256(f"{session_id}{salt}".encode()).hexdigest()
    return f"anon_{h[:12]}"


def pseudonymous_participant_reference(user_id: int) -> str:
    """Stable, deployment-scoped reference for the trainee/participant a session belongs
    to -- never their real name or email.

    @remarks
    Same salted-hash pattern as `generate_anon_session_id` and (in the research-run
    services) `pseudonymous_reviewer_reference`, but a distinct `participant_` prefix:
    a "reviewer" reference identifies the researcher who authored an annotation or
    validation run, while this identifies the trainee whose session is being viewed --
    conflating the two in one prefix would be actively misleading in a UI that can show
    both roles side by side. Used to redact identity from admin-session endpoints when
    the caller is a researcher rather than an admin: researchers need the real transcript
    to annotate and evaluate, but never need the trainee's real identity to do that work.
    """
    salt = get_settings().research_anon_salt
    digest = hashlib.sha256(f"participant:{user_id}:{salt}".encode()).hexdigest()
    return f"participant_{digest[:16]}"


def _plugin_field_csv(val: str | None) -> str:
    """Single plugin id/path for a CSV cell (plain string, not JSON)."""
    if val is None:
        return ""
    return str(val).strip()


def _format_metrics_plugins_csv(raw: str | None) -> str:
    """Flatten session.metrics_plugins JSON text to a comma-separated string for CSV."""
    if not raw:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return ", ".join(
                str(x).strip() for x in parsed if x is not None and str(x).strip()
            )
    except (json.JSONDecodeError, TypeError):
        pass
    return text


def resolve_anon_to_session_id(anon_session_id: str, session_repo: SessionRepository) -> int | None:
    """Reverse lookup: anon_session_id -> internal session id. Returns None if not found."""
    if not anon_session_id or not anon_session_id.startswith("anon_"):
        return None
    # Iterate sessions and match by computed anon id (no raw id stored)
    skip, limit = 0, 5000
    while True:
        sessions = session_repo.get_all(skip=skip, limit=limit)
        if not sessions:
            return None
        for s in sessions:
            if generate_anon_session_id(s.id) == anon_session_id:
                return s.id
        if len(sessions) < limit:
            return None
        skip += limit


class ResearchService:
    """Service for research data export with anonymization."""

    def __init__(self, db: Session):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.turn_repo = TurnRepository(db)
        self.feedback_repo = FeedbackRepository(db)
        self.case_repo = CaseRepository(db)
    
    async def export_research_data(
        self,
        export_request: ResearchExportRequest,
    ) -> ResearchExportResponse:
        """Export anonymized research data."""
        # Get sessions based on filters
        sessions = self._get_filtered_sessions(export_request)
        
        # Prepare export data
        export_data = []
        for session in sessions:
            session_data = self._anonymize_session(session, export_request)
            export_data.append(session_data)
        
        # Generate CSV
        csv_content = self._generate_csv(export_data)
        
        # In production, this would upload to storage and return presigned URL
        export_id = str(uuid4())
        download_url = f"/api/research/exports/{export_id}/download"
        
        return ResearchExportResponse(
            export_id=export_id,
            download_url=download_url,
            generated_at=utc_now(),
            record_count=len(export_data),
        )
    
    def get_all_sessions(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return list of anonymized sessions (no PII), including aggregate feedback metrics when available."""
        sessions = self.session_repo.get_all(skip=skip, limit=limit)
        case_ids = list({s.case_id for s in sessions if getattr(s, "case_id", None) is not None})
        cases_by_id: dict[int, str] = {}
        if case_ids:
            rows = self.db.query(Case).filter(Case.id.in_(case_ids)).all()
            cases_by_id = {c.id: c.title for c in rows}

        request = ResearchExportRequest(
            anonymize=True,
            include_turns=False,
            include_feedback=True,
        )
        results: list[dict[str, Any]] = []
        for session in sessions:
            base = self._anonymize_session(session, request)
            feedback = (base.get("feedback") or {}) if isinstance(base, dict) else {}

            empathy = feedback.get("empathy_score")
            communication = feedback.get("communication_score")
            spikes_completion = feedback.get("spikes_completion_score")
            overall = feedback.get("overall_score")

            # clinical_score is represented by overall_score in our analytics CSV
            clinical = overall

            # If communication_score is missing, fall back to overall_score
            if communication is None and overall is not None:
                communication = overall

            timestamp: str | None
            if getattr(session, "started_at", None):
                timestamp = serialize_utc_datetime(session.started_at)
            else:
                timestamp = None

            # Flatten metrics into the top-level payload; preserve anonymized session_id
            base.update(
                {
                    "empathy_score": empathy,
                    "communication_score": communication,
                    "clinical_score": clinical,
                    "spikes_completion_score": spikes_completion,
                    "timestamp": timestamp,
                }
            )

            # Remove nested feedback blob to keep response lightweight
            base.pop("feedback", None)
            base["case_name"] = cases_by_id.get(session.case_id)
            results.append(base)

        return results

    def get_session_by_anon(self, anon_session_id: str) -> dict[str, Any]:
        """Return anonymized session details by anon_session_id (no PII). Raises ValueError if not found."""
        session_id = resolve_anon_to_session_id(anon_session_id, self.session_repo)
        if session_id is None:
            raise ValueError("Session not found")
        session = self.session_repo.get_by_id(session_id)
        if not session:
            raise ValueError("Session not found")
        request = ResearchExportRequest(anonymize=True, include_turns=True, include_feedback=True)
        data = self._anonymize_session(session, request)
        case = self.case_repo.get_by_id(session.case_id)
        data["case_name"] = case.title if case else None
        return data

    def get_export_json_content(
        self,
        export_request: ResearchExportRequest | None = None,
    ) -> str:
        """Return JSON string of anonymized export data for download."""
        request = export_request or ResearchExportRequest(anonymize=True)
        sessions = self._get_filtered_sessions(request)
        export_data = [self._anonymize_session(s, request) for s in sessions]
        return json.dumps(export_data, indent=2, default=json_utc_default)

    def get_export_csv_content(
        self,
        export_request: ResearchExportRequest | None = None,
    ) -> str:
        """Return CSV string of flattened anonymized session+turns (one row per turn)."""
        request = export_request or ResearchExportRequest(
            anonymize=True, include_turns=True, include_feedback=True
        )
        sessions = self._get_filtered_sessions(request)
        fieldnames = [
            "anon_session_id",
            "case_id",
            "started_at",
            "patient_model_plugin",
            "evaluator_plugin",
            "metrics_plugins",
            "empathy_score",
            "spikes_completion",
            "turn_number",
            "speaker",
            "text",
            "voice_tone_primary",
            "voice_tone_confidence",
            "voice_tone_valence",
            "voice_tone_arousal",
            "voice_tone_pace_wpm",
            "voice_tone_pitch_hz",
        ]
        rows: list[dict[str, Any]] = []
        for session in sessions:
            session_data = self._anonymize_session(session, request)
            feedback = session_data.get("feedback") or {}
            empathy = feedback.get("empathy_score", "")
            spikes = feedback.get("spikes_completion_score", "")
            started_at_str = (
                serialize_utc_datetime(session.started_at)
                if session.started_at
                else ""
            )
            patient_plugin = _plugin_field_csv(session.patient_model_plugin)
            evaluator_plugin = _plugin_field_csv(session.evaluator_plugin)
            metrics_plugins = _format_metrics_plugins_csv(session.metrics_plugins)
            for turn in session_data.get("turns", []):
                rows.append(
                    {
                        "anon_session_id": session_data["session_id"],
                        "case_id": session_data["case_id"],
                        "started_at": started_at_str,
                        "patient_model_plugin": patient_plugin,
                        "evaluator_plugin": evaluator_plugin,
                        "metrics_plugins": metrics_plugins,
                        "empathy_score": empathy,
                        "spikes_completion": spikes,
                        "turn_number": turn["turn_number"],
                        "speaker": turn["role"],
                        "text": turn["text"],
                        "voice_tone_primary": turn.get("voice_tone_primary", ""),
                        "voice_tone_confidence": turn.get("voice_tone_confidence", ""),
                        "voice_tone_valence": turn.get("voice_tone_valence", ""),
                        "voice_tone_arousal": turn.get("voice_tone_arousal", ""),
                        "voice_tone_pace_wpm": turn.get("voice_tone_pace_wpm", ""),
                        "voice_tone_pitch_hz": turn.get("voice_tone_pitch_hz", ""),
                    }
                )
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    def stream_metrics_csv(self) -> Iterator[bytes]:
        """Stream metrics CSV: one row per session. Reuses existing scoring logic."""
        header = [
            "anon_session_id",
            "case_id",
            "started_at",
            "duration_seconds",
            "patient_model_plugin",
            "evaluator_plugin",
            "metrics_plugins",
            "empathy_score",
            "spikes_completion",
            "communication_score",
            "clinical_score",
            "num_turns",
            "difficulty_level",
        ]
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        yield buf.getvalue().encode("utf-8")
        buf.seek(0)
        buf.truncate(0)

        sessions = self._get_filtered_sessions(ResearchExportRequest(anonymize=True))
        case_ids = [s.case_id for s in sessions]
        cases = {c.id: c for c in (self.case_repo.get_by_id(cid) for cid in set(case_ids)) if c is not None}
        for session in sessions:
            feedback = self.feedback_repo.get_by_session(session.id)
            turns = self.turn_repo.get_by_session(session.id)
            case = cases.get(session.case_id)
            row = [
                generate_anon_session_id(session.id),
                session.case_id,
                serialize_utc_datetime(session.started_at) if session.started_at else "",
                session.duration_seconds or 0,
                _plugin_field_csv(session.patient_model_plugin),
                _plugin_field_csv(session.evaluator_plugin),
                _format_metrics_plugins_csv(session.metrics_plugins),
                feedback.empathy_score if feedback else "",
                feedback.spikes_completion_score if feedback else "",
                feedback.communication_score if feedback else "",
                feedback.overall_score if feedback else "",
                len(turns),
                (case.difficulty_level or "") if case else "",
            ]
            writer.writerow(row)
            yield buf.getvalue().encode("utf-8")
            buf.seek(0)
            buf.truncate(0)

    def stream_transcripts_csv(self) -> Iterator[bytes]:
        """Stream all transcripts CSV: flattened rows with anonymized text."""
        header = [
            "anon_session_id",
            "case_id",
            "patient_model_plugin",
            "evaluator_plugin",
            "metrics_plugins",
            "turn_number",
            "speaker",
            "text",
            "timestamp",
            "voice_tone_primary",
            "voice_tone_confidence",
            "voice_tone_valence",
            "voice_tone_arousal",
            "voice_tone_pace_wpm",
            "voice_tone_pitch_hz",
        ]
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        yield buf.getvalue().encode("utf-8")
        buf.seek(0)
        buf.truncate(0)

        sessions = self._get_filtered_sessions(
            ResearchExportRequest(anonymize=True, include_turns=True)
        )
        for session in sessions:
            anon_id = generate_anon_session_id(session.id)
            patient_plugin = _plugin_field_csv(session.patient_model_plugin)
            evaluator_plugin = _plugin_field_csv(session.evaluator_plugin)
            metrics_plugins = _format_metrics_plugins_csv(session.metrics_plugins)
            turns = self.turn_repo.get_by_session(session.id)
            for turn in turns:
                voice_tone = self._extract_voice_tone_fields(turn.metrics_json)
                row = [
                    anon_id,
                    session.case_id,
                    patient_plugin,
                    evaluator_plugin,
                    metrics_plugins,
                    turn.turn_number,
                    turn.role,
                    self._anonymize_text(turn.text or ""),
                    serialize_utc_datetime(turn.timestamp) if turn.timestamp else "",
                    voice_tone["voice_tone_primary"],
                    voice_tone["voice_tone_confidence"],
                    voice_tone["voice_tone_valence"],
                    voice_tone["voice_tone_arousal"],
                    voice_tone["voice_tone_pace_wpm"],
                    voice_tone["voice_tone_pitch_hz"],
                ]
                writer.writerow(row)
                yield buf.getvalue().encode("utf-8")
                buf.seek(0)
                buf.truncate(0)

    def stream_session_transcript_csv(self, anon_session_id: str) -> Iterator[bytes]:
        """Stream single session transcript CSV. Raises ValueError if anon_session_id not found."""
        session_id = resolve_anon_to_session_id(anon_session_id, self.session_repo)
        if session_id is None:
            raise ValueError("Session not found")
        session = self.session_repo.get_by_id(session_id)
        if not session:
            raise ValueError("Session not found")

        header = [
            "anon_session_id",
            "case_id",
            "patient_model_plugin",
            "evaluator_plugin",
            "metrics_plugins",
            "turn_number",
            "speaker",
            "text",
            "timestamp",
            "voice_tone_primary",
            "voice_tone_confidence",
            "voice_tone_valence",
            "voice_tone_arousal",
            "voice_tone_pace_wpm",
            "voice_tone_pitch_hz",
        ]
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        yield buf.getvalue().encode("utf-8")
        buf.seek(0)
        buf.truncate(0)

        patient_plugin = _plugin_field_csv(session.patient_model_plugin)
        evaluator_plugin = _plugin_field_csv(session.evaluator_plugin)
        metrics_plugins = _format_metrics_plugins_csv(session.metrics_plugins)

        turns = self.turn_repo.get_by_session(session.id)
        aid = generate_anon_session_id(session.id)
        for turn in turns:
            voice_tone = self._extract_voice_tone_fields(turn.metrics_json)
            row = [
                aid,
                session.case_id,
                patient_plugin,
                evaluator_plugin,
                metrics_plugins,
                turn.turn_number,
                turn.role,
                self._anonymize_text(turn.text or ""),
                serialize_utc_datetime(turn.timestamp) if turn.timestamp else "",
                voice_tone["voice_tone_primary"],
                voice_tone["voice_tone_confidence"],
                voice_tone["voice_tone_valence"],
                voice_tone["voice_tone_arousal"],
                voice_tone["voice_tone_pace_wpm"],
                voice_tone["voice_tone_pitch_hz"],
            ]
            writer.writerow(row)
            yield buf.getvalue().encode("utf-8")
            buf.seek(0)
            buf.truncate(0)

    def _get_filtered_sessions(
        self,
        export_request: ResearchExportRequest,
    ) -> list:
        """Get sessions based on export filters."""
        # Basic implementation - would add date and case filters
        return self.session_repo.get_all(skip=0, limit=1000)
    
    def _anonymize_session(
        self,
        session,
        export_request: ResearchExportRequest,
    ) -> dict[str, Any]:
        """Anonymize session data for research."""
        data = {
            "session_id": generate_anon_session_id(session.id) if export_request.anonymize else str(session.id),
            "case_id": session.case_id,
            "patient_model_plugin": session.patient_model_plugin,
            "evaluator_plugin": session.evaluator_plugin,
            "metrics_plugins": session.metrics_plugins,
            "duration_seconds": session.duration_seconds,
            "state": session.state,
            "spikes_stage": session.current_spikes_stage,
        }
        
        if export_request.include_turns:
            turns = self.turn_repo.get_by_session(session.id)
            data["turn_count"] = len(turns)
            data["turns"] = [
                (
                    {
                        "turn_number": turn.turn_number,
                        "role": turn.role,
                        "text": self._anonymize_text(turn.text) if export_request.anonymize else turn.text,
                        "spikes_stage": turn.spikes_stage,
                    }
                    | self._extract_voice_tone_fields(turn.metrics_json)
                )
                for turn in turns
            ]
        
        if export_request.include_feedback:
            feedback = self.feedback_repo.get_by_session(session.id)
            if feedback:
                data["feedback"] = {
                    "empathy_score": feedback.empathy_score,
                    "communication_score": feedback.communication_score,
                    "spikes_completion_score": feedback.spikes_completion_score,
                    "overall_score": feedback.overall_score,
                }
        
        return data
    
    def _anonymize_text(self, text: str) -> str:
        """Anonymize text by redacting PII via deterministic regex patterns.
        Pure function: does not mutate input.
        """
        if not text or not isinstance(text, str):
            return text
        result = text

        # Email addresses
        result = re.sub(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "[REDACTED_EMAIL]",
            result,
        )

        # Phone numbers: (123) 456-7890, 123-456-7890, 123.456.7890, +1 123 456 7890, etc.
        result = re.sub(
            r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
            "[REDACTED_PHONE]",
            result,
        )

        # Long numeric sequences (>=5 digits), excluding already-redacted tokens
        result = re.sub(r"\d{5,}", "[REDACTED_NUMBER]", result)

        # "My name is X" -> "My name is [REDACTED_NAME]"
        result = re.sub(
            r"(My name is)\s+[A-Za-z][A-Za-z\-]*(?:\s+[A-Za-z][A-Za-z\-]*){0,2}",
            r"\1 [REDACTED_NAME]",
            result,
            flags=re.IGNORECASE,
        )

        # "I am X" -> "I am [REDACTED_NAME]" (name only; avoid "I am 25", "I am very")
        result = re.sub(
            r"(I am)\s+[A-Za-z][a-z\-]+(?:\s+[A-Za-z][a-z\-]+){0,2}(?=\s*[.,;:!?]|\s*$|\s+and\s|\s+from\s)",
            r"\1 [REDACTED_NAME]",
            result,
            flags=re.IGNORECASE,
        )

        # "Dr. Smith", "Mr. Jones", "Mrs. Smith", "Ms. Brown", "Prof. Lee"
        result = re.sub(
            r"(Dr\.|Mr\.|Mrs\.|Ms\.|Prof\.)\s+[A-Za-z][A-Za-z\-]*(?:\s+[A-Za-z][A-Za-z\-]*)?",
            r"\1 [REDACTED_NAME]",
            result,
        )

        return result
    
    def _generate_csv(self, data: list[dict]) -> str:
        """Generate CSV from export data."""
        if not data:
            return ""
        
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        
        return output.getvalue()

    def _extract_voice_tone_fields(self, metrics_json: str | None) -> dict[str, Any]:
        """Flatten persisted voice tone metrics for research exports."""
        default_fields = {
            "voice_tone_primary": "",
            "voice_tone_confidence": "",
            "voice_tone_valence": "",
            "voice_tone_arousal": "",
            "voice_tone_pace_wpm": "",
            "voice_tone_pitch_hz": "",
        }
        if not metrics_json:
            return default_fields

        try:
            metrics = json.loads(metrics_json)
        except (TypeError, json.JSONDecodeError):
            try:
                metrics = json.loads(metrics_json.replace("'", '"'))
            except (AttributeError, TypeError, json.JSONDecodeError):
                return default_fields

        voice_tone = metrics.get("voice_tone")
        if not isinstance(voice_tone, dict):
            return default_fields

        dimensions = voice_tone.get("dimensions")
        if not isinstance(dimensions, dict):
            dimensions = {}

        return {
            "voice_tone_primary": voice_tone.get("primary", ""),
            "voice_tone_confidence": voice_tone.get("confidence", ""),
            "voice_tone_valence": dimensions.get("valence", ""),
            "voice_tone_arousal": dimensions.get("arousal", ""),
            "voice_tone_pace_wpm": dimensions.get("pace_wpm", ""),
            "voice_tone_pitch_hz": dimensions.get("pitch_hz", ""),
        }

