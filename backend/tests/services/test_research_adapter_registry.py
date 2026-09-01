"""Tests for deterministic identifiers and explicit adapter registration."""

from dataclasses import dataclass

import pytest

from domain.models.research_evaluation import (
    OutputCapabilities,
    ResearchCapabilities,
    ResearchFrameworkMetadata,
)
from services.research_adapters.identifiers import (
    canonical_result_digest,
    stable_research_identifier,
)
from services.research_adapters.registry import (
    ResearchAdapterRegistration,
    ResearchAdapterRegistry,
)


@dataclass(frozen=True)
class FakeAdapter:
    identifier: str = "fake.adapter"
    version: str = "1.0"
    supported_native_types: tuple[str, ...] = ("apex_feedback",)
    capabilities: ResearchCapabilities = ResearchCapabilities(
        outputs=OutputCapabilities(
            character_spans=True,
            turn_labels=True,
            relations=True,
            dimension_ratings=False,
            global_metrics=True,
            narrative_findings=True,
            evidence_turns=True,
            framework_native_view=True,
            live_execution=False,
        )
    )


def _registration() -> ResearchAdapterRegistration:
    return ResearchAdapterRegistration(
        evaluator_identifier="baseline",
        display_name="APEX baseline",
        evaluator_version="1.0",
        evaluator_type="rule_based",
        framework=ResearchFrameworkMetadata(
            identifier="apex-spikes-afce",
            display_name="APEX SPIKES / AFCE-aligned",
            version="1.0",
            validation_status="engineering_baseline",
            framework_statement=(
                "AFCE-aligned, rule-based operationalization of selected constructs."
            ),
        ),
        adapter=FakeAdapter(),
        requires_live_execution=False,
        default_selected=True,
    )


def test_stable_identifier_is_deterministic_and_sensitive_to_adapter_version():
    result_digest = canonical_result_digest({"native_type": "apex_feedback", "score": 80})
    values = {
        "transcript_hash": "a" * 64,
        "evaluator_identifier": "baseline",
        "framework_identifier": "apex-spikes-afce",
        "native_identifier": "eo.turn-2.4-10.feeling",
        "adapter_version": "1.0",
        "projection_type": "span_annotation",
        "object_location": "eo_spans[0].turn-2.4-10.feeling",
        "native_result_digest": result_digest,
    }
    first = stable_research_identifier("span", **values)
    second = stable_research_identifier("span", **values)
    changed = stable_research_identifier(
        "span", **{**values, "adapter_version": "1.1"}
    )
    assert first == second
    assert first != changed
    assert first.startswith("span_") and len(first) == 45
    assert "feeling" not in first


def test_stable_identifier_rejects_sensitive_plaintext_component():
    with pytest.raises(ValueError, match="safe characters"):
        stable_research_identifier(
            "span",
            transcript_hash="a" * 64,
            evaluator_identifier="baseline",
            framework_identifier="apex-spikes-afce",
            native_identifier="patient said secret words",
            adapter_version="1.0",
            projection_type="span_annotation",
            object_location="eo_spans[0]",
            native_result_digest="b" * 64,
        )


def test_registry_preserves_explicit_order_and_rejects_duplicates():
    registry = ResearchAdapterRegistry()
    registration = _registration()
    registry.register(registration)
    assert registry.identifiers() == ("baseline",)
    assert registry.get("baseline") is registration
    with pytest.raises(ValueError, match="already registered"):
        registry.register(registration)


def test_registry_rejects_live_metadata_capability_mismatch():
    registration = _registration()
    with pytest.raises(ValueError, match="live metadata"):
        ResearchAdapterRegistry().register(
            ResearchAdapterRegistration(
                **{
                    **registration.__dict__,
                    "requires_live_execution": True,
                    "supported_providers": ("openai",),
                }
            )
        )


def test_registry_unknown_identifier_is_allowlisted_error():
    registry = ResearchAdapterRegistry()
    registry.register(_registration())
    with pytest.raises(ValueError, match="Expected one of: baseline"):
        registry.get("uploaded-evaluator")
