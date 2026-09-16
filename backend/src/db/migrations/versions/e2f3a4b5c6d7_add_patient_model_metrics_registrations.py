"""seed patient_model and metrics registrations (plugin-registry-refactor phase 2)

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-09-16

Extends the unified plugin_registrations table (created in phase 1, evaluator
only) to the other two plugin kinds. Schema is unchanged -- plugin_kind,
registration_kind, and stage were modeled generically from day one -- this is
purely additive data, registering the two plugins that exist today via the
in-memory PluginRegistry (plugins/registry.py):

  - patient_model: DefaultLLMPatientModel
    (plugins.patient_models.default_llm_patient)
  - metrics:        ApexMetrics (plugins.metrics.apex_metrics)

Unlike the evaluator kind, PatientModel/MetricsPlugin have no existing static
catalog of short identifiers (no PATIENT_MODEL_DEFINITIONS/METRICS_DEFINITIONS
equivalent to EVALUATOR_DEFINITIONS) -- the dotted "module:ClassName" string
IS the identifier the rest of the system already uses (it's exactly what's
frozen onto Session.patient_model_plugin / Session.metrics_plugins and what
PluginRegistry.get_patient_model/get_metrics_plugin key off of, per
session_service.py). So identifier == module_path here, deliberately, rather
than inventing a short name that doesn't exist anywhere else in the codebase.

Both are marked registration_kind="native", stage="promoted": both are
already the sole, shipped, trainee-facing implementation of their kind today.

No sandbox/promotion UI work is included in this migration -- backend
registry data only, per the phase 2 scoping discussion.
"""

import json
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SEED_ROWS = [
    {
        "plugin_kind": "patient_model",
        "identifier": "plugins.patient_models.default_llm_patient:DefaultLLMPatientModel",
        "display_name": "Default LLM patient model",
        "version": "1.0",
        "module_path": "plugins.patient_models.default_llm_patient:DefaultLLMPatientModel",
        "metadata": {
            "requires_live_execution": True,
            "supported_providers": ["openai", "gemini"],
            "default_selected": True,
        },
    },
    {
        "plugin_kind": "metrics",
        "identifier": "plugins.metrics.apex_metrics:ApexMetrics",
        "display_name": "APEX metrics",
        "version": "1.0",
        "module_path": "plugins.metrics.apex_metrics:ApexMetrics",
        "metadata": {
            "requires_live_execution": False,
            "default_selected": True,
        },
    },
]


def upgrade() -> None:
    plugin_registrations = sa.table(
        "plugin_registrations",
        sa.column("plugin_kind", sa.String),
        sa.column("registration_kind", sa.String),
        sa.column("stage", sa.String),
        sa.column("identifier", sa.String),
        sa.column("display_name", sa.String),
        sa.column("version", sa.String),
        sa.column("module_path", sa.String),
        sa.column("metadata_json", sa.Text),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
        sa.column("promoted_at", sa.DateTime),
        schema="core",
    )
    # bulk_insert doesn't evaluate the entity's Python-side defaults
    # (utc_now/onupdate), and created_at/updated_at are NOT NULL with no DB
    # server_default, so the seed rows must supply their own timestamp.
    seeded_at = datetime.utcnow()
    op.bulk_insert(
        plugin_registrations,
        [
            {
                "plugin_kind": row["plugin_kind"],
                "registration_kind": "native",
                "stage": "promoted",
                "identifier": row["identifier"],
                "display_name": row["display_name"],
                "version": row["version"],
                "module_path": row["module_path"],
                "metadata_json": json.dumps(row["metadata"]),
                "created_at": seeded_at,
                "updated_at": seeded_at,
                "promoted_at": seeded_at,
            }
            for row in _SEED_ROWS
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()
    for row in _SEED_ROWS:
        conn.execute(
            sa.text(
                "DELETE FROM core.plugin_registrations "
                "WHERE plugin_kind = :plugin_kind AND identifier = :identifier"
            ),
            {"plugin_kind": row["plugin_kind"], "identifier": row["identifier"]},
        )
