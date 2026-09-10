"""Reviewed deterministic registration of built-in research evaluators."""

from __future__ import annotations

from domain.models.research_evaluation import (
    AFCE_IMPLEMENTATION_STATEMENT,
    ResearchFrameworkMetadata,
)
from services.evaluator_comparison_service import EVALUATOR_DEFINITIONS
from services.research_adapters.ace_ct import ACECTResearchAdapter
from services.research_adapters.apex import ApexResearchAdapter
from services.research_adapters.registry import (
    ResearchAdapterRegistration,
    ResearchAdapterRegistry,
)

ACE_WARNING = (
    "Experimental, unvalidated, non-official, and not a reproduction of the "
    "confidential manuscript's trained models."
)


def build_default_research_adapter_registry() -> ResearchAdapterRegistry:
    """Build the fixed built-in registry; no dynamic imports or uploads are used."""

    registry = ResearchAdapterRegistry()
    apex_framework = ResearchFrameworkMetadata(
        identifier="apex-spikes-afce",
        display_name="APEX SPIKES / AFCE-aligned",
        version="1.0",
        rubric_version="apex-scoring-v1",
        validation_status="engineering_baseline_unvalidated",
        framework_statement=AFCE_IMPLEMENTATION_STATEMENT,
    )
    for evaluator_identifier, display_name, default_selected in (
        ("baseline", "APEX baseline", True),
        ("hybrid_v1", "APEX hybrid v1", False),
        ("hybrid_v2", "APEX hybrid v2", False),
    ):
        definition = EVALUATOR_DEFINITIONS[evaluator_identifier]
        registry.register(
            ResearchAdapterRegistration(
                evaluator_identifier=evaluator_identifier,
                display_name=display_name,
                evaluator_version=definition.version,
                evaluator_type=definition.evaluator_type,
                framework=apex_framework,
                adapter=ApexResearchAdapter(live_execution=definition.requires_llm),
                requires_live_execution=definition.requires_llm,
                supported_providers=definition.supported_providers,
                default_provider=definition.default_llm_provider,
                default_selected=default_selected,
                warnings=(AFCE_IMPLEMENTATION_STATEMENT,),
            )
        )

    ace_definition = EVALUATOR_DEFINITIONS["ace_ct_inspired"]
    registry.register(
        ResearchAdapterRegistration(
            evaluator_identifier="ace_ct_inspired",
            display_name="ACE-CT-inspired (experimental)",
            evaluator_version=ace_definition.version,
            evaluator_type=ace_definition.evaluator_type,
            framework=ResearchFrameworkMetadata(
                identifier="ace-ct-inspired",
                display_name="ACE-CT-inspired",
                version="0.1.0-experimental",
                rubric_version="0.1.0-experimental",
                validation_status="experimental_unvalidated",
                framework_statement=ACE_WARNING,
            ),
            adapter=ACECTResearchAdapter(),
            requires_live_execution=True,
            supported_providers=ace_definition.supported_providers,
            default_provider=ace_definition.default_llm_provider,
            experimental=True,
            warnings=(ACE_WARNING,),
        )
    )
    return registry
