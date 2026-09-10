"""Explicit typed registration for research evaluators and adapters."""

from __future__ import annotations

from dataclasses import dataclass

from domain.models.research_evaluation import (
    ResearchAdapterMetadata,
    ResearchCapabilities,
    ResearchFrameworkMetadata,
)
from services.research_adapters.base import ResearchResultAdapter


@dataclass(frozen=True)
class ResearchAdapterRegistration:
    """Reviewed static evaluator metadata and its deterministic adapter."""

    evaluator_identifier: str
    display_name: str
    evaluator_version: str
    evaluator_type: str
    framework: ResearchFrameworkMetadata
    adapter: ResearchResultAdapter
    requires_live_execution: bool
    supported_providers: tuple[str, ...] = ()
    default_provider: str | None = None
    default_selected: bool = False
    experimental: bool = False
    warnings: tuple[str, ...] = ()

    @property
    def capabilities(self) -> ResearchCapabilities:
        return self.adapter.capabilities

    @property
    def adapter_metadata(self) -> ResearchAdapterMetadata:
        supported_types = self.adapter.supported_native_types
        if len(supported_types) != 1:
            raise ValueError(
                "Item 1 registrations require exactly one adapter native-result type."
            )
        return ResearchAdapterMetadata(
            identifier=self.adapter.identifier,
            version=self.adapter.version,
            supported_native_type=supported_types[0],
        )


class ResearchAdapterRegistry:
    """Ordered explicit registry; dynamic discovery is deliberately unsupported."""

    def __init__(self) -> None:
        self._registrations: dict[str, ResearchAdapterRegistration] = {}

    def register(self, registration: ResearchAdapterRegistration) -> None:
        identifier = registration.evaluator_identifier
        if identifier in self._registrations:
            raise ValueError(f"Research evaluator '{identifier}' is already registered.")
        if registration.requires_live_execution != (
            registration.capabilities.outputs.live_execution
        ):
            raise ValueError("Registration live metadata must match adapter capabilities.")
        if registration.requires_live_execution and not registration.supported_providers:
            raise ValueError("Live research evaluators must declare supported providers.")
        if (
            registration.requires_live_execution
            and registration.default_provider not in registration.supported_providers
        ):
            raise ValueError("A live evaluator default provider must be supported.")
        if not registration.requires_live_execution and registration.supported_providers:
            raise ValueError("Offline research evaluators cannot declare providers.")
        if not registration.requires_live_execution and registration.default_provider is not None:
            raise ValueError("Offline research evaluators cannot declare a default provider.")
        self._registrations[identifier] = registration

    def get(self, evaluator_identifier: str) -> ResearchAdapterRegistration:
        try:
            return self._registrations[evaluator_identifier]
        except KeyError as exc:
            allowed = ", ".join(self._registrations)
            raise ValueError(
                f"Unknown research evaluator '{evaluator_identifier}'. Expected one of: "
                f"{allowed}."
            ) from exc

    def list(self) -> tuple[ResearchAdapterRegistration, ...]:
        return tuple(self._registrations.values())

    def identifiers(self) -> tuple[str, ...]:
        return tuple(self._registrations)
