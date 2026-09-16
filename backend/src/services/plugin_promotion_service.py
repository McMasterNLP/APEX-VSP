"""PromotionWorkflowService: request/review workflow for plugin lifecycle stage changes.

Phase 4 of the plugin-registry refactor. ``RegistryService.promote()``/
``deprecate()`` (phase 1) change a registration's stage immediately, with no
record of who asked or who signed off -- appropriate for the migration-time
seeding phases 1/2 did, but not for an ongoing workflow where a researcher
proposes a stage change and someone else reviews it.

This service adds that request/review layer on top of the existing
registry: a ``PluginPromotionRequest`` row records the ask (who, target
stage, notes) and, once reviewed, the decision (who, approved/rejected,
notes). Only an *approved* request actually mutates
``PluginRegistration.stage`` -- and it does so by calling back into
``RegistryService`` for the "promoted"/"deprecated" cases specifically, so
the ``promoted_at``/``deprecated_at`` timestamp bookkeeping stays defined in
exactly one place rather than being duplicated here.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from core.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from core.time import serialize_utc_datetime, utc_now
from domain.entities.plugin_promotion_request import PluginPromotionRequest
from domain.models.plugin_promotion_request import (
    PromotionRequestListResponse,
    PromotionRequestResponse,
)
from domain.models.plugin_registration import PluginStage
from repositories.plugin_promotion_request_repo import PluginPromotionRequestRepository
from repositories.plugin_registration_repo import PluginRegistrationRepository
from services.plugin_registry_service import RegistryService


class PromotionWorkflowService:
    """Request, list, approve, reject, and withdraw plugin promotion requests."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = PluginPromotionRequestRepository(db)
        self.registration_repo = PluginRegistrationRepository(db)
        self.registry = RegistryService(db)

    def request_promotion(
        self,
        registration_id: int,
        requested_stage: PluginStage,
        *,
        requested_by_user_id: Optional[int],
        notes: Optional[str] = None,
    ) -> PromotionRequestResponse:
        registration = self.registration_repo.get_by_id(registration_id)
        if registration is None:
            raise NotFoundError(f"Plugin registration {registration_id} not found.")
        if requested_stage == registration.stage:
            raise ValidationError(
                f"Registration {registration_id} is already at stage '{requested_stage}'."
            )
        existing_pending = self.repo.get_pending_for_registration(registration_id)
        if existing_pending is not None:
            raise ConflictError(
                f"Registration {registration_id} already has a pending promotion "
                f"request (id={existing_pending.id})."
            )
        entity = PluginPromotionRequest(
            registration_id=registration_id,
            requested_stage=requested_stage,
            status="pending",
            requested_by_user_id=requested_by_user_id,
            request_notes=notes,
        )
        created = self.repo.create(entity)
        return self._to_response(created)

    def get(self, request_id: int) -> PromotionRequestResponse:
        entity = self.repo.get_by_id(request_id)
        if entity is None:
            raise NotFoundError(f"Promotion request {request_id} not found.")
        return self._to_response(entity)

    def list(
        self,
        registration_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> PromotionRequestListResponse:
        entities = self.repo.list(registration_id=registration_id, status=status)
        return PromotionRequestListResponse(
            requests=tuple(self._to_response(entity) for entity in entities)
        )

    def approve(
        self,
        request_id: int,
        *,
        reviewed_by_user_id: Optional[int],
        notes: Optional[str] = None,
    ) -> PromotionRequestResponse:
        entity = self._get_pending_or_raise(request_id)

        if entity.requested_stage == "promoted":
            self.registry.promote(entity.registration_id)
        elif entity.requested_stage == "deprecated":
            self.registry.deprecate(entity.registration_id)
        else:
            registration = self.registration_repo.get_by_id(entity.registration_id)
            if registration is None:
                raise NotFoundError(
                    f"Plugin registration {entity.registration_id} not found."
                )
            registration.stage = entity.requested_stage
            self.registration_repo.update(registration)

        entity.status = "approved"
        entity.reviewed_by_user_id = reviewed_by_user_id
        entity.review_notes = notes
        entity.reviewed_at = utc_now()
        updated = self.repo.update(entity)
        return self._to_response(updated)

    def reject(
        self,
        request_id: int,
        *,
        reviewed_by_user_id: Optional[int],
        notes: Optional[str] = None,
    ) -> PromotionRequestResponse:
        entity = self._get_pending_or_raise(request_id)
        entity.status = "rejected"
        entity.reviewed_by_user_id = reviewed_by_user_id
        entity.review_notes = notes
        entity.reviewed_at = utc_now()
        updated = self.repo.update(entity)
        return self._to_response(updated)

    def withdraw(
        self,
        request_id: int,
        *,
        requesting_user_id: Optional[int],
    ) -> PromotionRequestResponse:
        entity = self._get_pending_or_raise(request_id)
        if (
            entity.requested_by_user_id is not None
            and entity.requested_by_user_id != requesting_user_id
        ):
            raise AuthorizationError(
                "Only the user who requested this promotion can withdraw it."
            )
        entity.status = "withdrawn"
        entity.reviewed_at = utc_now()
        updated = self.repo.update(entity)
        return self._to_response(updated)

    def _get_pending_or_raise(self, request_id: int) -> PluginPromotionRequest:
        entity = self.repo.get_by_id(request_id)
        if entity is None:
            raise NotFoundError(f"Promotion request {request_id} not found.")
        if entity.status != "pending":
            raise ConflictError(
                f"Promotion request {request_id} is already '{entity.status}'."
            )
        return entity

    @staticmethod
    def _to_response(entity: PluginPromotionRequest) -> PromotionRequestResponse:
        return PromotionRequestResponse(
            id=entity.id,
            registration_id=entity.registration_id,
            requested_stage=entity.requested_stage,
            status=entity.status,
            requested_by_user_id=entity.requested_by_user_id,
            request_notes=entity.request_notes,
            reviewed_by_user_id=entity.reviewed_by_user_id,
            review_notes=entity.review_notes,
            created_at=serialize_utc_datetime(entity.created_at),
            updated_at=serialize_utc_datetime(entity.updated_at),
            reviewed_at=(
                serialize_utc_datetime(entity.reviewed_at) if entity.reviewed_at else None
            ),
        )
