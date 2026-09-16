"""RegistryService: the unified plugin lifecycle registry (Phase 1: Evaluator only).

This is the DB-backed replacement, for the Evaluator plugin kind, of:
  - the in-memory ``PluginRegistry`` dict (``plugins/registry.py``) used by
    ``ScoringService`` to instantiate the frozen evaluator for a session, and
  - the static ``ResearchAdapterRegistry`` (``services/research_adapters``)
    used by ``ResearchEvaluationService`` to list/execute research evaluators.

Phase 1 does not remove either of those -- ``ScoringService``'s trainee-facing
scoring path and the adapter/framework execution machinery in
``services/research_adapters`` are untouched, per the agreed plan. What this
service adds is a single source of truth for *identity + lifecycle stage*
that both of those can be cross-referenced against, and that Phase 2
(PatientModel, MetricsPlugin) and Phase 4 (promotion workflow) build on.

Note on trainee vs. research evaluators specifically: these remain two
separate systems by design (different protocols, different identity
guarantees -- see the Plugin Developer Guide's "Why this is kept separate"
callout). ``link()`` below is a later addition that lets two same-kind
registrations be marked, symmetrically, as the same underlying model shown
on two surfaces (e.g. a trainee Evaluator wrapper and its Research Evaluator
adapter). It is purely informational and never changes which code path a
session or a research run actually executes.
"""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from core.errors import NotFoundError
from core.time import serialize_utc_datetime, utc_now
from domain.entities.plugin_registration import PluginRegistration
from domain.models.plugin_registration import (
    PluginKind,
    PluginRegistrationCreate,
    PluginRegistrationListResponse,
    PluginRegistrationResponse,
    PluginStage,
)
from repositories.plugin_registration_repo import PluginRegistrationRepository


class RegistryService:
    """Register, list, look up, promote, and deprecate plugin registrations."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = PluginRegistrationRepository(db)

    def register(
        self,
        payload: PluginRegistrationCreate,
        *,
        created_by_user_id: int | None = None,
    ) -> PluginRegistrationResponse:
        """Register a new plugin. Raises ValueError if the identifier is taken."""

        existing = self.repo.get_by_identifier(payload.plugin_kind, payload.identifier)
        if existing is not None:
            raise ValueError(
                f"{payload.plugin_kind} '{payload.identifier}' is already registered."
            )
        entity = PluginRegistration(
            plugin_kind=payload.plugin_kind,
            registration_kind=payload.registration_kind,
            stage=payload.stage,
            identifier=payload.identifier,
            display_name=payload.display_name,
            version=payload.version,
            module_path=payload.module_path,
            config_json=json.dumps(payload.config) if payload.config is not None else None,
            metadata_json=(
                json.dumps(payload.metadata) if payload.metadata is not None else None
            ),
            created_by_user_id=created_by_user_id,
            promoted_at=utc_now() if payload.stage == "promoted" else None,
        )
        created = self.repo.create(entity)
        return self._to_response(created)

    def register_if_absent(
        self,
        payload: PluginRegistrationCreate,
        *,
        created_by_user_id: int | None = None,
    ) -> PluginRegistrationResponse:
        """Idempotent variant of ``register`` -- returns the existing row if present.

        Intended for the native code-merge pipeline: merging a PR should insert
        an experimental registry row, but re-running the app's startup import
        of the same module must not fail or duplicate the row.
        """

        existing = self.repo.get_by_identifier(payload.plugin_kind, payload.identifier)
        if existing is not None:
            return self._to_response(existing)
        return self.register(payload, created_by_user_id=created_by_user_id)

    def get(self, plugin_kind: PluginKind, identifier: str) -> PluginRegistrationResponse:
        entity = self.repo.get_by_identifier(plugin_kind, identifier)
        if entity is None:
            raise NotFoundError(f"{plugin_kind} '{identifier}' is not registered.")
        return self._to_response(entity)

    def list(
        self,
        plugin_kind: Optional[PluginKind] = None,
        stage: Optional[PluginStage] = None,
    ) -> PluginRegistrationListResponse:
        entities = self.repo.list(plugin_kind=plugin_kind, stage=stage)
        return PluginRegistrationListResponse(
            registrations=tuple(self._to_response(entity) for entity in entities)
        )

    def promote(self, registration_id: int) -> PluginRegistrationResponse:
        entity = self.repo.get_by_id(registration_id)
        if entity is None:
            raise NotFoundError(f"Plugin registration {registration_id} not found.")
        entity.stage = "promoted"
        entity.promoted_at = utc_now()
        updated = self.repo.update(entity)
        return self._to_response(updated)

    def deprecate(self, registration_id: int) -> PluginRegistrationResponse:
        entity = self.repo.get_by_id(registration_id)
        if entity is None:
            raise NotFoundError(f"Plugin registration {registration_id} not found.")
        entity.stage = "deprecated"
        entity.deprecated_at = utc_now()
        updated = self.repo.update(entity)
        return self._to_response(updated)

    def link(
        self, registration_id: int, linked_registration_id: int | None
    ) -> PluginRegistrationResponse:
        """Set or clear the symmetric, informational link on a registration.

        Used to mark two registrations (e.g. a trainee-facing Evaluator
        wrapper and its Research Evaluator adapter counterpart) as the same
        underlying model shown on two surfaces. This never changes stage,
        promotion history, or which code path executes -- it is display-only
        metadata for the registry UI.
        """

        entity = self.repo.get_by_id(registration_id)
        if entity is None:
            raise NotFoundError(f"Plugin registration {registration_id} not found.")

        # Clearing: unset this row's link, and the old partner's back-link if
        # it still points here.
        if linked_registration_id is None:
            old_partner = (
                self.repo.get_by_id(entity.linked_registration_id)
                if entity.linked_registration_id
                else None
            )
            entity.linked_registration_id = None
            if old_partner is not None and old_partner.linked_registration_id == entity.id:
                old_partner.linked_registration_id = None
            self.db.commit()
            self.db.refresh(entity)
            return self._to_response(entity)

        if linked_registration_id == registration_id:
            raise ValueError("A registration cannot be linked to itself.")

        target = self.repo.get_by_id(linked_registration_id)
        if target is None:
            raise NotFoundError(f"Plugin registration {linked_registration_id} not found.")
        if target.plugin_kind != entity.plugin_kind:
            raise ValueError(
                "Linked registrations must share the same plugin_kind "
                f"(got {entity.plugin_kind!r} and {target.plugin_kind!r})."
            )

        # Break any stale prior links on either side before forming the new
        # pair, so a registration is never linked to more than one partner.
        if entity.linked_registration_id and entity.linked_registration_id != target.id:
            old_partner = self.repo.get_by_id(entity.linked_registration_id)
            if old_partner is not None and old_partner.linked_registration_id == entity.id:
                old_partner.linked_registration_id = None
        if target.linked_registration_id and target.linked_registration_id != entity.id:
            old_partner = self.repo.get_by_id(target.linked_registration_id)
            if old_partner is not None and old_partner.linked_registration_id == target.id:
                old_partner.linked_registration_id = None

        entity.linked_registration_id = target.id
        target.linked_registration_id = entity.id
        self.db.commit()
        self.db.refresh(entity)
        return self._to_response(entity)

    @staticmethod
    def _to_response(entity: PluginRegistration) -> PluginRegistrationResponse:
        return PluginRegistrationResponse(
            id=entity.id,
            plugin_kind=entity.plugin_kind,
            registration_kind=entity.registration_kind,
            stage=entity.stage,
            identifier=entity.identifier,
            display_name=entity.display_name,
            version=entity.version,
            module_path=entity.module_path,
            config=json.loads(entity.config_json) if entity.config_json else None,
            metadata=json.loads(entity.metadata_json) if entity.metadata_json else None,
            linked_registration_id=entity.linked_registration_id,
            created_at=serialize_utc_datetime(entity.created_at),
            updated_at=serialize_utc_datetime(entity.updated_at),
            promoted_at=(
                serialize_utc_datetime(entity.promoted_at) if entity.promoted_at else None
            ),
            deprecated_at=(
                serialize_utc_datetime(entity.deprecated_at) if entity.deprecated_at else None
            ),
        )
