"""Plugin registration entity: the unified, DB-backed plugin lifecycle registry.

Phase 1 of the plugin-registry refactor. Replaces, for the Evaluator kind only,
the in-memory ``PluginRegistry`` dict (``plugins/registry.py``) and the static
``ResearchAdapterRegistry`` (``services/research_adapters/registry.py``) as the
source of truth for *which plugins exist and what lifecycle stage they're in*.

``PatientModel`` and ``MetricsPlugin`` rows are not created yet (Phase 2); the
``plugin_kind``/``stage``/``registration_kind`` columns are modeled for all
three kinds from day one so Phase 2 is an additive change, not a schema churn.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Text

from core.time import utc_now
from db.base import Base
from db.types import UTCDateTimeType

PLUGIN_KINDS = ("evaluator", "patient_model", "metrics")
REGISTRATION_KINDS = ("variant", "native")
PLUGIN_STAGES = (
    "draft",
    "experimental",
    "under_review",
    "promoted",
    "deprecated",
    "retired",
)


class PluginRegistration(Base):
    """A single registered plugin (any kind) and its current lifecycle stage."""

    __tablename__ = "plugin_registrations"

    id = Column(Integer, primary_key=True, index=True)

    plugin_kind = Column(String(20), nullable=False)  # PLUGIN_KINDS
    registration_kind = Column(String(20), nullable=False)  # REGISTRATION_KINDS
    stage = Column(String(20), nullable=False, default="experimental")  # PLUGIN_STAGES

    # Stable key used to look up/execute the plugin (matches the identifier
    # used elsewhere today, e.g. PluginRegistry/ResearchAdapterRegistry keys).
    identifier = Column(String(150), nullable=False)
    display_name = Column(String(150), nullable=False)
    version = Column(String(50), nullable=False)

    # Native: dotted module path (optionally "module:ClassName") that owns the
    # code. Variant: null -- a variant has no code of its own, only config.
    module_path = Column(String(300), nullable=True)

    # Variant: the config payload (e.g. a new prompt/rubric) layered on top of
    # an existing reviewed adapter. Null for native registrations.
    config_json = Column(Text, nullable=True)

    # Kind-specific descriptor metadata that doesn't warrant its own column yet
    # (e.g. evaluator_type, requires_live_execution, supported_providers,
    # framework info, warnings). Consumers parse this per plugin_kind.
    metadata_json = Column(Text, nullable=True)

    # No back-reference on User -- this is a one-directional FK (unlike
    # Session.user/User.sessions) since nothing needs "all registrations a
    # user created" today.
    created_by_user_id = Column(Integer, ForeignKey("core.users.id"), nullable=True)

    # Optional pointer to another registration of the same plugin_kind that
    # represents the same underlying model on a different surface (e.g. a
    # trainee-facing Evaluator wrapper and its Research Evaluator adapter
    # counterpart). Purely informational -- set/cleared symmetrically by
    # RegistryService.link(); never affects stage, promotion, or which code
    # path actually executes.
    linked_registration_id = Column(
        Integer,
        ForeignKey("core.plugin_registrations.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(UTCDateTimeType(), default=utc_now, nullable=False)
    updated_at = Column(UTCDateTimeType(), default=utc_now, onupdate=utc_now, nullable=False)
    promoted_at = Column(UTCDateTimeType(), nullable=True)
    deprecated_at = Column(UTCDateTimeType(), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<PluginRegistration(id={self.id}, kind={self.plugin_kind}, "
            f"identifier={self.identifier}, stage={self.stage})>"
        )
