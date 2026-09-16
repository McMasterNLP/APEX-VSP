"""Plugin promotion request entity: the request/review workflow for stage changes.

Phase 4 of the plugin-registry refactor. ``RegistryService.promote()``/
``deprecate()`` (phase 1) flip a registration's stage directly with no audit
trail -- this table adds a formal request/review layer on top of that: a
request records who asked for a stage change and why, a reviewer's decision
records who approved/rejected it and why, and only an approved request
actually changes ``PluginRegistration.stage`` (still via the same
``RegistryService`` methods, so the promoted_at/deprecated_at bookkeeping
stays in exactly one place).
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, String, Text, text

from core.time import utc_now
from db.base import Base
from db.types import UTCDateTimeType
from domain.entities.plugin_registration import PLUGIN_STAGES

PROMOTION_REQUEST_STATUSES = ("pending", "approved", "rejected", "withdrawn")


class PluginPromotionRequest(Base):
    """A single request to move a plugin registration to a new lifecycle stage."""

    __tablename__ = "plugin_promotion_requests"

    id = Column(Integer, primary_key=True, index=True)

    registration_id = Column(
        Integer,
        ForeignKey("core.plugin_registrations.id", ondelete="CASCADE"),
        nullable=False,
    )
    requested_stage = Column(String(20), nullable=False)  # PLUGIN_STAGES
    status = Column(String(20), nullable=False, default="pending")  # PROMOTION_REQUEST_STATUSES

    requested_by_user_id = Column(Integer, ForeignKey("core.users.id"), nullable=True)
    request_notes = Column(Text, nullable=True)

    reviewed_by_user_id = Column(Integer, ForeignKey("core.users.id"), nullable=True)
    review_notes = Column(Text, nullable=True)

    created_at = Column(UTCDateTimeType(), default=utc_now, nullable=False)
    updated_at = Column(UTCDateTimeType(), default=utc_now, onupdate=utc_now, nullable=False)
    reviewed_at = Column(UTCDateTimeType(), nullable=True)

    # Mirrors the constraints created by the
    # f3a4b5c6d7e8_add_plugin_promotion_requests migration exactly -- see the
    # comment on PluginRegistration.__table_args__ for why this duplication
    # matters (Base.metadata.create_all() vs. the raw migration DDL).
    __table_args__ = (
        CheckConstraint(
            f"requested_stage IN {PLUGIN_STAGES!r}",
            name="ck_plugin_promotion_requests_requested_stage",
        ),
        CheckConstraint(
            f"status IN {PROMOTION_REQUEST_STATUSES!r}",
            name="ck_plugin_promotion_requests_status",
        ),
        # At most one pending request per registration at a time.
        Index(
            "uq_plugin_promotion_requests_one_pending",
            "registration_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_plugin_promotion_requests_registration_id", "registration_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<PluginPromotionRequest(id={self.id}, registration_id={self.registration_id}, "
            f"requested_stage={self.requested_stage}, status={self.status})>"
        )
