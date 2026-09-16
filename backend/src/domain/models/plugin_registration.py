"""Pydantic contracts for the unified plugin registry (Phase 1: Evaluator only)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

PluginKind = Literal["evaluator", "patient_model", "metrics"]
RegistrationKind = Literal["variant", "native"]
PluginStage = Literal[
    "draft",
    "experimental",
    "under_review",
    "promoted",
    "deprecated",
    "retired",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PluginRegistrationCreate(StrictModel):
    """Request payload to register a new plugin (native or variant)."""

    plugin_kind: PluginKind
    registration_kind: RegistrationKind
    identifier: str = Field(min_length=1, max_length=150, pattern=r"^[a-z][a-z0-9_.:-]{0,149}$")
    display_name: str = Field(min_length=1, max_length=150)
    version: str = Field(min_length=1, max_length=50)
    module_path: str | None = Field(default=None, max_length=300)
    config: JsonValue | None = None
    metadata: JsonValue | None = None
    stage: PluginStage = "experimental"


class PluginRegistrationResponse(StrictModel):
    id: int
    plugin_kind: PluginKind
    registration_kind: RegistrationKind
    stage: PluginStage
    identifier: str
    display_name: str
    version: str
    module_path: str | None = None
    config: JsonValue | None = None
    metadata: JsonValue | None = None
    linked_registration_id: int | None = None
    created_at: str
    updated_at: str
    promoted_at: str | None = None
    deprecated_at: str | None = None


class PluginRegistrationListResponse(StrictModel):
    registrations: tuple[PluginRegistrationResponse, ...]


class PluginRegistrationLinkRequest(StrictModel):
    """Set or clear the informational link to another same-kind registration.

    Pass ``linked_registration_id=None`` to unlink. Linking is symmetric --
    the other registration's ``linked_registration_id`` is updated to point
    back at this one in the same operation.
    """

    linked_registration_id: int | None = None
