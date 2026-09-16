"""Pydantic contracts for the plugin promotion request/review workflow (Phase 4)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from domain.models.plugin_registration import PluginStage, StrictModel

PromotionRequestStatus = Literal["pending", "approved", "rejected", "withdrawn"]


class PromotionRequestCreate(StrictModel):
    """Request payload to ask that a registration be moved to a new stage."""

    requested_stage: PluginStage
    notes: str | None = Field(default=None, max_length=2000)


class PromotionRequestDecision(StrictModel):
    """Request payload for an approve/reject/withdraw decision."""

    notes: str | None = Field(default=None, max_length=2000)


class PromotionRequestResponse(StrictModel):
    id: int
    registration_id: int
    requested_stage: PluginStage
    status: PromotionRequestStatus
    requested_by_user_id: int | None = None
    request_notes: str | None = None
    reviewed_by_user_id: int | None = None
    review_notes: str | None = None
    created_at: str
    updated_at: str
    reviewed_at: str | None = None


class PromotionRequestListResponse(StrictModel):
    requests: tuple[PromotionRequestResponse, ...]
