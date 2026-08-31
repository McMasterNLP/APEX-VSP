"""Load plugin modules at startup so they register with PluginRegistry."""

from __future__ import annotations

import importlib
import logging

from plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)

PLUGIN_MODULES = [
    "plugins.patient_models.default_llm_patient",
    "plugins.evaluators.apex_baseline_evaluator",
    "plugins.evaluators.apex_hybrid_evaluator",
    "plugins.evaluators.apex_hybrid_v2_evaluator",
    "plugins.evaluators.ace_ct_inspired_evaluator",
    "plugins.metrics.apex_metrics",
]


def load_plugins() -> None:
    """Import each plugin module so its top-level registration code runs."""
    for module in PLUGIN_MODULES:
        try:
            importlib.import_module(module)
            logger.info("Loaded plugin module: %s", module)
        except Exception as e:
            logger.exception("Failed to load plugin module %s: %s", module, e)
            raise

    # Verification: log what is registered
    logger.info(
        "Plugin registry after load: patient_models=%s, evaluators=%s, metrics_plugins=%s",
        list(PluginRegistry.list_patient_models().keys()),
        list(PluginRegistry.list_evaluators().keys()),
        list(PluginRegistry.list_metrics_plugins().keys()),
    )
