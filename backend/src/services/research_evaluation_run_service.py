"""Server-run persistence boundary for immutable research evaluation runs."""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from config.settings import get_settings
from core.time import parse_utc_datetime, utc_now
from domain.entities.research_annotation import ResearchEvaluationRun
from domain.entities.user import User
from domain.models.research_annotation import (
    EvaluationRunRecord,
    EvaluationRunSummary,
    ResearchEvaluationRunSaveRequest,
)
from domain.models.research_evaluation import (
    ResearchEvaluationEnvelope,
    ResearchEvaluationRequest,
    ResearchTranscriptTurn,
)
from repositories.research_annotation_repo import ResearchAnnotationRepository
from services.research_annotation_policy import (
    AnnotationPolicyError,
    policy_for_envelope,
)
from services.research_evaluation_service import (
    ResearchEvaluationService,
    ResearchEvaluationServiceError,
)

_TRANSCRIPT_SNAPSHOT_ADAPTER = TypeAdapter(tuple[ResearchTranscriptTurn, ...])


class ResearchEvaluationRunServiceError(ValueError):
    """Allowlisted saved-run error safe for API status mapping."""

    def __init__(
        self,
        category: Literal[
            "run_not_found",
            "evaluation_failed",
            "live_execution_refused",
            "unsupported_annotation_policy",
            "persistence_failed",
        ],
        message: str,
    ):
        self.category = category
        super().__init__(message)


def pseudonymous_reviewer_reference(user_id: int) -> str:
    """Return a stable deployment-scoped reviewer reference without identity data."""

    salt = get_settings().research_anon_salt
    digest = hashlib.sha256(f"reviewer:{user_id}:{salt}".encode()).hexdigest()
    return f"reviewer_{digest[:16]}"


class ResearchEvaluationRunService:
    """Execute Item 1 on the server and save one exact successful envelope."""

    def __init__(
        self,
        db: Session,
        *,
        evaluation_service: ResearchEvaluationService | None = None,
        repository: ResearchAnnotationRepository | None = None,
    ):
        self.db = db
        self.evaluation_service = evaluation_service or ResearchEvaluationService(db)
        self.repository = repository or ResearchAnnotationRepository(db)

    async def run_and_save(
        self,
        session_id: int,
        request: ResearchEvaluationRunSaveRequest,
        creator: User,
    ) -> EvaluationRunRecord:
        """Rerun one evaluator and persist its validated result transactionally."""

        try:
            response = await self.evaluation_service.evaluate(
                session_id,
                ResearchEvaluationRequest(
                    evaluator_identifiers=(request.evaluator_identifier,),
                    allow_live=request.allow_live,
                    provider=request.provider,
                    model_identifier=request.model_identifier,
                ),
            )
        except ResearchEvaluationServiceError:
            raise

        envelope = response.results[0]
        if envelope.status != "success":
            category = (
                "live_execution_refused"
                if envelope.status == "refused"
                else "evaluation_failed"
            )
            message = (
                "Live evaluation was refused by the configured research policy."
                if envelope.status == "refused"
                else "The evaluator did not produce a successful saved research run."
            )
            raise ResearchEvaluationRunServiceError(category, message)

        try:
            policy = policy_for_envelope(envelope)
        except AnnotationPolicyError as error:
            raise ResearchEvaluationRunServiceError(
                "unsupported_annotation_policy", str(error)
            ) from error

        created_at = utc_now()
        entity = ResearchEvaluationRun(
            source_session_id=session_id,
            item1_run_id=envelope.run.run_id,
            transcript_hash=envelope.transcript.canonical_transcript_hash,
            transcript_projection_version=envelope.transcript.transcript_projection_version,
            transcript_snapshot_json=json.dumps(
                [turn.model_dump(mode="json") for turn in response.transcript_turns],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            turn_count=envelope.transcript.turn_count,
            envelope_schema_version=envelope.schema_version,
            envelope_json=envelope.model_dump_json(),
            evaluator_identifier=envelope.evaluator.identifier,
            evaluator_version=envelope.evaluator.version,
            framework_identifier=envelope.framework.identifier,
            framework_version=envelope.framework.version,
            adapter_identifier=envelope.adapter.identifier,
            adapter_version=envelope.adapter.version,
            provider=envelope.evaluator.provider,
            model_identifier=envelope.evaluator.model_identifier,
            rubric_version=envelope.framework.rubric_version,
            execution_mode=envelope.run.execution_mode,
            execution_timestamp=parse_utc_datetime(envelope.run.timestamp),
            runtime_ms=envelope.run.runtime_ms,
            status=envelope.status,
            failure_category=envelope.run.failure_category,
            created_by_user_id=creator.id,
            created_at=created_at,
        )
        try:
            self.repository.add_evaluation_run(entity)
            self.db.commit()
            self.db.refresh(entity)
        except Exception as error:
            self.db.rollback()
            raise ResearchEvaluationRunServiceError(
                "persistence_failed", "The validated research run could not be saved."
            ) from error

        return EvaluationRunRecord(
            run_uuid=entity.id,
            source_session_id=session_id,
            envelope=envelope,
            transcript_snapshot=response.transcript_turns,
            creator_reference=pseudonymous_reviewer_reference(creator.id),
            created_at=entity.created_at,
            transcript_matches_current=True,
            current_transcript_hash=envelope.transcript.canonical_transcript_hash,
            annotation_policy=policy,
        )

    def get_run(self, run_uuid: UUID) -> EvaluationRunRecord:
        entity = self.repository.get_evaluation_run(run_uuid)
        if entity is None:
            raise ResearchEvaluationRunServiceError(
                "run_not_found", "The requested research evaluation run was not found."
            )
        return self._record(entity)

    def list_for_session(self, session_id: int) -> tuple[EvaluationRunSummary, ...]:
        current_hash = self._current_transcript_hash(session_id)
        return tuple(
            EvaluationRunSummary(
                run_uuid=entity.id,
                item1_run_id=entity.item1_run_id,
                evaluator_identifier=entity.evaluator_identifier,
                evaluator_version=entity.evaluator_version,
                framework_identifier=entity.framework_identifier,
                framework_version=entity.framework_version,
                transcript_hash=entity.transcript_hash,
                execution_mode=entity.execution_mode,
                status=entity.status,
                created_at=entity.created_at,
                transcript_matches_current=current_hash == entity.transcript_hash,
            )
            for entity in self.repository.list_evaluation_runs_for_session(session_id)
        )

    def _record(self, entity: ResearchEvaluationRun) -> EvaluationRunRecord:
        envelope = ResearchEvaluationEnvelope.model_validate_json(entity.envelope_json)
        transcript = _TRANSCRIPT_SNAPSHOT_ADAPTER.validate_json(
            entity.transcript_snapshot_json
        )
        current_hash = self._current_transcript_hash(entity.source_session_id)
        try:
            policy = policy_for_envelope(envelope)
        except AnnotationPolicyError as error:
            raise ResearchEvaluationRunServiceError(
                "unsupported_annotation_policy", str(error)
            ) from error
        return EvaluationRunRecord(
            run_uuid=entity.id,
            source_session_id=entity.source_session_id,
            envelope=envelope,
            transcript_snapshot=transcript,
            creator_reference=pseudonymous_reviewer_reference(entity.created_by_user_id),
            created_at=entity.created_at,
            transcript_matches_current=current_hash == entity.transcript_hash,
            current_transcript_hash=current_hash,
            annotation_policy=policy,
        )

    def _current_transcript_hash(self, session_id: int) -> str | None:
        try:
            _, identity = self.evaluation_service.completed_transcript(session_id)
        except ResearchEvaluationServiceError:
            return None
        return identity.canonical_transcript_hash
