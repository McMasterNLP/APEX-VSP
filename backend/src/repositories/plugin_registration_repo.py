"""Repository for the unified plugin_registrations table."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from domain.entities.plugin_registration import PluginRegistration


class PluginRegistrationRepository:
    """Repository for PluginRegistration entity operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, registration_id: int) -> Optional[PluginRegistration]:
        return (
            self.db.query(PluginRegistration)
            .filter(PluginRegistration.id == registration_id)
            .first()
        )

    def get_by_identifier(
        self, plugin_kind: str, identifier: str
    ) -> Optional[PluginRegistration]:
        return (
            self.db.query(PluginRegistration)
            .filter(
                PluginRegistration.plugin_kind == plugin_kind,
                PluginRegistration.identifier == identifier,
            )
            .first()
        )

    def list(
        self,
        plugin_kind: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> list[PluginRegistration]:
        query = self.db.query(PluginRegistration)
        if plugin_kind:
            query = query.filter(PluginRegistration.plugin_kind == plugin_kind)
        if stage:
            query = query.filter(PluginRegistration.stage == stage)
        return query.order_by(
            PluginRegistration.plugin_kind, PluginRegistration.identifier
        ).all()

    def create(self, registration: PluginRegistration) -> PluginRegistration:
        self.db.add(registration)
        self.db.commit()
        self.db.refresh(registration)
        return registration

    def update(self, registration: PluginRegistration) -> PluginRegistration:
        self.db.commit()
        self.db.refresh(registration)
        return registration
