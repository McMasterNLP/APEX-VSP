"""Admin research evaluation orchestration with no persistence side effects."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from sqlalchemy.orm import Session

from config.logging import get_logger
from config.settings import get_settings
from core.time import serialize_utc_datetime, utc_now
from domain.models.research_evaluation import (
    ResearchEvaluationEnvelope,
    ResearchEvaluationRequest,
    ResearchEvaluationResponse,
    ResearchEvaluatorDescriptor,
    ResearchEvaluatorDescriptorsResponse,
    ResearchEvaluatorMetadata,
    ResearchProvenance,
    ResearchProjection,
    ResearchRunMetadata,
    ResearchTranscriptIdentity,
    ResearchTranscriptTurn,
    SanitizedResearchError,
    validate_projection_against_transcript,
)
from repositories.session_repo import SessionRepository
from repositories.turn_repo import TurnRepository
from services.evaluator_comparison_service import EvaluatorComparisonService
from services.research_adapters.base import ResearchAdapterContext
from services.research_adapters.defaults import build_default_research_adapter_registry
from services.research_adapters.identifiers import (
    canonical_result_digest,
    stable_research_identifier,
)
from services.research_adapters.registry import (
    ResearchAdapterRegistration,
    ResearchAdapterRegistry,
)
from services.transcript_identity import canonicalize_transcript, hash_transcript

logger = get_logger(__name__)

MAX_TRANSCRIPT_CHARACTERS = 1_000_000
MAX_RESEARCH_RESPONSE_BYTES = 5_000_000


class ResearchEvaluationServiceError(ValueError):
    """Allowlisted request/session error safe for controller status mapping."""

    def __init__(
        self,
        category: Literal[
            "session_not_found",
            "session_incomplete",
            "invalid_evaluator",
            "invalid_request",
            "response_too_large",
        ],
        message: str,
    ):
        self.category = category
        super().__init__(message)


RunnerFactory = Callable[..., EvaluatorComparisonService]


class ResearchEvaluationService:
    """Execute registered evaluators independently and return validated envelopes."""

    def __init__(
        self,
        db: Session,
        *,
        registry: ResearchAdapterRegistry | None = None,
        runner_factory: RunnerFactory | None = None,
        live_execution_enabled: bool | None = None,
        ace_ct_experimental_enabled: bool | None = None,
        configured_models: dict[str, str] | None = None,
    ):
        settings = None
        if (
            live_execution_enabled is None
            or ace_ct_experimental_enabled is None
            or configured_models is None
        ):
            settings = get_settings()
        self.db = db
        self.session_repo = SessionRepository(db)
        self.turn_repo = TurnRepository(db)
        self.registry = registry or build_default_research_adapter_registry()
        self.runner_factory = runner_factory or self._default_runner_factory
        self.live_execution_enabled = (
            live_execution_enabled
            if live_execution_enabled is not None
            else settings.research_allow_live_evaluations
        )
        self.ace_ct_experimental_enabled = (
            ace_ct_experimental_enabled
            if ace_ct_experimental_enabled is not None
            else settings.ace_ct_allow_experimental_rubric
        )
        self.configured_models = (
            configured_models
            if configured_models is not None
            else {
                "openai": settings.openai_model_id,
                "gemini": settings.gemini_model_id,
            }
        )

    def _default_runner_factory(self, **kwargs) -> EvaluatorComparisonService:
        return EvaluatorComparisonService(self.db, **kwargs)

    def descriptors(self) -> ResearchEvaluatorDescriptorsResponse:
        descriptors: list[ResearchEvaluatorDescriptor] = []
        for registration in self.registry.list():
            if not registration.requires_live_execution:
                availability = "available"
            elif not self.live_execution_enabled:
                availability = "server_live_disabled"
            elif registration.experimental and not self.ace_ct_experimental_enabled:
                availability = "experimental_disabled"
            else:
                availability = "available"
            descriptors.append(
                ResearchEvaluatorDescriptor(
                    identifier=registration.evaluator_identifier,
                    display_name=registration.display_name,
                    version=registration.evaluator_version,
                    framework=registration.framework,
                    adapter=registration.adapter_metadata,
                    capabilities=registration.capabilities,
                    requires_live_execution=registration.requires_live_execution,
                    supported_providers=registration.supported_providers,
                    default_selected=registration.default_selected,
                    availability=availability,
                    warnings=registration.warnings,
                )
            )
        return ResearchEvaluatorDescriptorsResponse(evaluators=tuple(descriptors))

    async def evaluate(
        self,
        session_id: int,
        request: ResearchEvaluationRequest,
    ) -> ResearchEvaluationResponse:
        transcript_turns, response_identity = self.completed_transcript(session_id)
        envelope_identity = response_identity.model_copy(
            update={"raw_transcript_included": False}
        )

        registrations: list[ResearchAdapterRegistration] = []
        for identifier in request.evaluator_identifiers:
            try:
                registrations.append(self.registry.get(identifier))
            except ValueError as exc:
                raise ResearchEvaluationServiceError(
                    "invalid_evaluator", "A requested research evaluator is not registered."
                ) from exc

        results: list[ResearchEvaluationEnvelope] = []
        for registration in registrations:
            results.append(
                await self._evaluate_one(
                    session_id,
                    registration,
                    request,
                    transcript_turns,
                    envelope_identity,
                )
            )

        response = ResearchEvaluationResponse(
            transcript=response_identity,
            transcript_turns=transcript_turns,
            results=tuple(results),
        )
        if len(response.model_dump_json().encode("utf-8")) > MAX_RESEARCH_RESPONSE_BYTES:
            raise ResearchEvaluationServiceError(
                "response_too_large", "The validated research response exceeds its size limit."
            )
        return response

    def completed_transcript(
        self, session_id: int
    ) -> tuple[tuple[ResearchTranscriptTurn, ...], ResearchTranscriptIdentity]:
        """Return authorized export/run transcript context after session-state checks."""

        session = self.session_repo.get_by_id(session_id)
        if session is None:
            raise ResearchEvaluationServiceError(
                "session_not_found", "The requested session was not found."
            )
        if session.state != "completed":
            raise ResearchEvaluationServiceError(
                "session_incomplete",
                "Research evaluation requires a completed session.",
            )

        transcript_turns, transcript_hash = self._build_transcript(session_id)
        identity = ResearchTranscriptIdentity(
            canonical_transcript_hash=transcript_hash,
            turn_count=len(transcript_turns),
            raw_transcript_included=True,
        )
        return transcript_turns, identity

    def _build_transcript(
        self, session_id: int
    ) -> tuple[tuple[ResearchTranscriptTurn, ...], str]:
        source_turns = self.turn_repo.get_by_session(session_id)
        canonical = canonicalize_transcript(source_turns)
        if sum(len(turn.text) for turn in canonical) > MAX_TRANSCRIPT_CHARACTERS:
            raise ResearchEvaluationServiceError(
                "invalid_request", "The transcript exceeds the research evaluation size limit."
            )
        if len({turn.turn_number for turn in canonical}) != len(canonical):
            raise ResearchEvaluationServiceError(
                "invalid_request", "The transcript contains duplicate turn numbers."
            )
        turns: list[ResearchTranscriptTurn] = []
        for turn in canonical:
            if turn.role not in {"user", "assistant"}:
                raise ResearchEvaluationServiceError(
                    "invalid_request", "The transcript contains an unsupported role."
                )
            turns.append(
                ResearchTranscriptTurn(
                    turn_number=turn.turn_number,
                    source_role=turn.role,
                    role="clinician" if turn.role == "user" else "patient",
                    text=turn.text,
                )
            )
        return tuple(turns), hash_transcript(canonical)

    async def _evaluate_one(
        self,
        session_id: int,
        registration: ResearchAdapterRegistration,
        request: ResearchEvaluationRequest,
        transcript_turns: tuple[ResearchTranscriptTurn, ...],
        transcript_identity: ResearchTranscriptIdentity,
    ) -> ResearchEvaluationEnvelope:
        provider = request.provider or registration.default_provider
        model_identifier = (
            request.model_identifier
            or (self.configured_models.get(provider) if provider is not None else None)
        )
        if provider is not None and provider not in registration.supported_providers:
            return self._failure_envelope(
                registration,
                transcript_identity,
                category="evaluator_unavailable",
                message="The selected provider is not supported by this evaluator.",
                status="failed",
                provider=provider,
                model_identifier=model_identifier,
            )

        refusal = self._live_refusal(registration, request)
        if refusal is not None:
            return self._failure_envelope(
                registration,
                transcript_identity,
                category="live_execution_refused",
                message=refusal,
                status="refused",
                provider=provider,
                model_identifier=model_identifier,
            )

        runner = self.runner_factory(
            llm_provider=provider,
            model_identifier=model_identifier,
            allow_experimental_override=(
                self.ace_ct_experimental_enabled and request.allow_live
            ),
        )
        run_results = await runner.run_evaluators(
            session_id,
            [registration.evaluator_identifier],
            require_completed=True,
        )
        if len(run_results) != 1:
            return self._failure_envelope(
                registration,
                transcript_identity,
                category="evaluation_failed",
                message="Evaluator execution returned an invalid result count.",
                status="failed",
                provider=provider,
                model_identifier=model_identifier,
            )
        run_result = run_results[0]
        if run_result.status != "success":
            category = (
                run_result.error.category
                if run_result.error is not None
                else "evaluation_failed"
            )
            safe_category = (
                category if category in {"evaluation_failed", "unexpected_error"}
                else "evaluation_failed"
            )
            return self._failure_envelope(
                registration,
                transcript_identity,
                category=safe_category,
                message=(
                    run_result.error.message
                    if run_result.error is not None
                    else "Evaluator execution did not produce a result."
                ),
                status="failed",
                runtime_ms=run_result.runtime_ms,
                provider=run_result.provenance.llm_provider or provider,
                model_identifier=run_result.provenance.model_identifier or model_identifier,
            )

        context = ResearchAdapterContext(
            transcript_hash=transcript_identity.canonical_transcript_hash,
            transcript_turns=transcript_turns,
            evaluator_identifier=registration.evaluator_identifier,
            framework_identifier=registration.framework.identifier,
        )
        try:
            native_result = registration.adapter.build_native_result(run_result, context)
        except Exception:  # noqa: BLE001 - sanitized adapter isolation boundary
            logger.warning(
                "Research native-result adaptation failed evaluator=%s",
                registration.evaluator_identifier,
            )
            return self._failure_envelope(
                registration,
                transcript_identity,
                category="invalid_native_result",
                message="The evaluator output did not satisfy its native research schema.",
                status="failed",
                runtime_ms=run_result.runtime_ms,
                provider=run_result.provenance.llm_provider or provider,
                model_identifier=run_result.provenance.model_identifier or model_identifier,
            )
        try:
            projection = registration.adapter.project(native_result, context)
            validate_projection_against_transcript(projection, transcript_turns)
        except Exception:  # noqa: BLE001 - sanitized adapter isolation boundary
            logger.warning(
                "Research projection validation failed evaluator=%s",
                registration.evaluator_identifier,
            )
            return self._failure_envelope(
                registration,
                transcript_identity,
                category="invalid_projection",
                message="The derived research projection failed validation.",
                status="failed",
                runtime_ms=run_result.runtime_ms,
                provider=run_result.provenance.llm_provider or provider,
                model_identifier=run_result.provenance.model_identifier or model_identifier,
            )

        timestamp = serialize_utc_datetime(utc_now())
        native_digest = canonical_result_digest(native_result)
        run_id = self._run_id(
            registration,
            transcript_identity.canonical_transcript_hash,
            native_digest,
        )
        live = registration.requires_live_execution
        resolved_provider = run_result.provenance.llm_provider or provider
        resolved_model = run_result.provenance.model_identifier or model_identifier
        warnings = list(registration.warnings)
        if hasattr(native_result, "compatibility_projection"):
            warnings.extend(native_result.compatibility_projection.warnings)
        return ResearchEvaluationEnvelope(
            run=ResearchRunMetadata(
                run_id=run_id,
                timestamp=timestamp,
                runtime_ms=run_result.runtime_ms,
                execution_mode="live" if live else "offline",
                completion_status="success",
            ),
            transcript=transcript_identity,
            evaluator=ResearchEvaluatorMetadata(
                identifier=registration.evaluator_identifier,
                display_name=registration.display_name,
                version=registration.evaluator_version,
                evaluator_type=registration.evaluator_type,
                provider=resolved_provider,
                model_identifier=resolved_model,
            ),
            framework=registration.framework,
            adapter=registration.adapter_metadata,
            capabilities=registration.capabilities,
            framework_result=native_result,
            projection=projection,
            warnings=tuple(dict.fromkeys(warnings)),
            status="success",
            provenance=ResearchProvenance(
                generated_at=timestamp,
                runtime_ms=run_result.runtime_ms,
                live_execution=live,
            ),
        )

    def _live_refusal(
        self,
        registration: ResearchAdapterRegistration,
        request: ResearchEvaluationRequest,
    ) -> str | None:
        if not registration.requires_live_execution:
            return None
        if not request.allow_live:
            return "Live evaluator execution requires allow_live=true."
        if not self.live_execution_enabled:
            return "Live research evaluator execution is disabled by server policy."
        if registration.experimental and not self.ace_ct_experimental_enabled:
            return "The experimental rubric is not authorized by server policy."
        return None

    def _failure_envelope(
        self,
        registration: ResearchAdapterRegistration,
        transcript_identity: ResearchTranscriptIdentity,
        *,
        category: str,
        message: str,
        status: Literal["failed", "refused"],
        runtime_ms: float = 0.0,
        provider: str | None = None,
        model_identifier: str | None = None,
    ) -> ResearchEvaluationEnvelope:
        timestamp = serialize_utc_datetime(utc_now())
        failure_digest = canonical_result_digest(
            {
                "category": category,
                "evaluator": registration.evaluator_identifier,
                "status": status,
            }
        )
        return ResearchEvaluationEnvelope(
            run=ResearchRunMetadata(
                run_id=self._run_id(
                    registration,
                    transcript_identity.canonical_transcript_hash,
                    failure_digest,
                ),
                timestamp=timestamp,
                runtime_ms=runtime_ms,
                execution_mode=(
                    "live" if registration.requires_live_execution else "offline"
                ),
                completion_status=status,
                failure_category=category,
            ),
            transcript=transcript_identity,
            evaluator=ResearchEvaluatorMetadata(
                identifier=registration.evaluator_identifier,
                display_name=registration.display_name,
                version=registration.evaluator_version,
                evaluator_type=registration.evaluator_type,
                provider=provider,
                model_identifier=model_identifier,
            ),
            framework=registration.framework,
            adapter=registration.adapter_metadata,
            capabilities=registration.capabilities,
            projection=ResearchProjection(),
            warnings=registration.warnings,
            status=status,
            error=SanitizedResearchError(category=category, message=message),
            provenance=ResearchProvenance(
                generated_at=timestamp,
                runtime_ms=runtime_ms,
                live_execution=registration.requires_live_execution,
            ),
        )

    @staticmethod
    def _run_id(
        registration: ResearchAdapterRegistration,
        transcript_hash: str,
        result_digest: str,
    ) -> str:
        return stable_research_identifier(
            "run",
            transcript_hash=transcript_hash,
            evaluator_identifier=registration.evaluator_identifier,
            framework_identifier=registration.framework.identifier,
            native_identifier=registration.adapter.supported_native_types[0],
            adapter_version=registration.adapter.version,
            projection_type="evaluation_run",
            object_location="run",
            native_result_digest=result_digest,
        )
