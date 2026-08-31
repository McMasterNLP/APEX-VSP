"""Experimental, non-default ACE-CT-inspired evaluator plugin."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from config.settings import get_settings
from domain.models.sessions import FeedbackResponse
from plugins.registry import PluginRegistry
from repositories.session_repo import SessionRepository
from services.ace_ct_computation_service import (
    ACE_CT_PLUGIN_IDENTIFIER,
    ACE_CT_PLUGIN_VERSION,
    ACECTComputationError,
    ACECTComputationResult,
    compute_ace_ct_evaluation,
)
from services.scoring_service import ScoringService


class ACECTInspiredRubricEvaluator:
    """Explicitly selected experimental transcript-rubric evaluator."""

    name = ACE_CT_PLUGIN_IDENTIFIER
    version = ACE_CT_PLUGIN_VERSION
    framework = "ACE-CT-inspired"
    validation_status = "experimental_unvalidated"
    publication_reproduction = False
    implementation_type = "experimental_transcript_rubric"

    def __init__(
        self,
        *,
        llm_adapter: Any | None = None,
        llm_provider: str | None = None,
        model_identifier: str | None = None,
        allow_experimental_override: bool | None = None,
    ):
        self._llm_adapter = llm_adapter
        self._llm_provider = llm_provider
        self._model_identifier = model_identifier
        self._allow_experimental_override = allow_experimental_override

    async def compute(self, db: Session, session_id: int) -> ACECTComputationResult:
        """Run the shared non-persisting computation core."""

        settings = None
        if self._llm_provider is None or self._allow_experimental_override is None:
            settings = get_settings()
        provider = self._llm_provider or settings.default_llm_provider
        allow_override = (
            self._allow_experimental_override
            if self._allow_experimental_override is not None
            else settings.ace_ct_allow_experimental_rubric
        )
        return await compute_ace_ct_evaluation(
            db,
            session_id,
            llm_provider=provider,
            model_identifier=self._model_identifier,
            llm_adapter=self._llm_adapter,
            allow_experimental_override=allow_override,
        )

    async def evaluate(self, db: Session, session_id: int) -> FeedbackResponse:
        """Compute and persist only for a session explicitly frozen to this plugin."""

        session = SessionRepository(db).get_by_id(session_id)
        if session is None:
            raise ACECTComputationError("session_not_found")
        if getattr(session, "evaluator_plugin", None) != self.name:
            raise ACECTComputationError("plugin_not_explicitly_selected")

        result = await self.compute(db, session_id)
        if result.computed_feedback is None:
            raise ACECTComputationError("insufficient_compatibility_scores_for_persistence")
        return await ScoringService(db).persist_computed_feedback(result.computed_feedback)


PluginRegistry.register_evaluator(
    ACECTInspiredRubricEvaluator.name,
    ACECTInspiredRubricEvaluator,
)
