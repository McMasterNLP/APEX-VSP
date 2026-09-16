"""Repository for the plugin_promotion_requests table."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from domain.entities.plugin_promotion_request import PluginPromotionRequest


class PluginPromotionRequestRepository:
    """Repository for PluginPromotionRequest entity operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, request_id: int) -> Optional[PluginPromotionRequest]:
        return (
            self.db.query(PluginPromotionRequest)
            .filter(PluginPromotionRequest.id == request_id)
            .first()
        )

    def get_pending_for_registration(
        self, registration_id: int
    ) -> Optional[PluginPromotionRequest]:
        return (
            self.db.query(PluginPromotionRequest)
            .filter(
                PluginPromotionRequest.registration_id == registration_id,
                PluginPromotionRequest.status == "pending",
            )
            .first()
        )

    def list(
        self,
        registration_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> list[PluginPromotionRequest]:
        query = self.db.query(PluginPromotionRequest)
        if registration_id is not None:
            query = query.filter(PluginPromotionRequest.registration_id == registration_id)
        if status:
            query = query.filter(PluginPromotionRequest.status == status)
        return query.order_by(PluginPromotionRequest.created_at.desc()).all()

    def create(self, request: PluginPromotionRequest) -> PluginPromotionRequest:
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    def update(self, request: PluginPromotionRequest) -> PluginPromotionRequest:
        self.db.commit()
        self.db.refresh(request)
        return request
