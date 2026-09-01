"""Explicit deterministic adapters for research-evaluation results."""

from services.research_adapters.base import (
    ResearchAdapterContext,
    ResearchResultAdapter,
)
from services.research_adapters.registry import (
    ResearchAdapterRegistration,
    ResearchAdapterRegistry,
)

__all__ = [
    "ResearchAdapterContext",
    "ResearchAdapterRegistration",
    "ResearchAdapterRegistry",
    "ResearchResultAdapter",
]
