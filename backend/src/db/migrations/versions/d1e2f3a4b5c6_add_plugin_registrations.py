"""add unified plugin_registrations table (plugin-registry-refactor phase 1)

Revision ID: d1e2f3a4b5c6
Revises: c8d9e0f1a2b3
Create Date: 2026-09-16

Creates the plugin_registrations table and seeds it with the four evaluators
that are registered today via the static EVALUATOR_DEFINITIONS /
ResearchAdapterRegistry (baseline, hybrid_v1, hybrid_v2, ace_ct_inspired),
marked registration_kind="native" and stage="promoted" -- they are already
shipped, reviewed, and trainee-facing today, so the migration brings that
existing reality into the registry rather than resetting it to "draft".

PatientModel and MetricsPlugin rows are not seeded yet (Phase 2).
"""

import json
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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

_APEX_FRAMEWORK = {
    "identifier": "apex-spikes-afce",
    "display_name": "APEX SPIKES / AFCE-aligned",
    "version": "1.0",
    "rubric_version": "apex-scoring-v1",
    "validation_status": "engineering_baseline_unvalidated",
}
_AFCE_STATEMENT = (
    "AFCE-aligned, rule-based operationalization of selected constructs."
)
_ACE_WARNING = (
    "Experimental, unvalidated, non-official, and not a reproduction of the "
    "confidential manuscript's trained models."
)

_SEED_ROWS = [
    {
        "identifier": "baseline",
        "display_name": "APEX baseline",
        "version": "1.0",
        "module_path": "plugins.evaluators.apex_baseline_evaluator:ApexBaselineEvaluator",
        "metadata": {
            "evaluator_type": "rule_based",
            "requires_live_execution": False,
            "supported_providers": [],
            "default_provider": None,
            "default_selected": True,
            "framework": _APEX_FRAMEWORK,
            "warnings": [_AFCE_STATEMENT],
        },
    },
    {
        "identifier": "hybrid_v1",
        "display_name": "APEX hybrid v1",
        "version": "1.0",
        "module_path": "plugins.evaluators.apex_hybrid_evaluator:ApexHybridEvaluator",
        "metadata": {
            "evaluator_type": "hybrid_llm",
            "requires_live_execution": True,
            "supported_providers": ["openai"],
            "default_provider": "openai",
            "default_selected": False,
            "framework": _APEX_FRAMEWORK,
            "warnings": [_AFCE_STATEMENT],
        },
    },
    {
        "identifier": "hybrid_v2",
        "display_name": "APEX hybrid v2",
        "version": "1.0",
        "module_path": "plugins.evaluators.apex_hybrid_v2_evaluator:ApexHybridV2Evaluator",
        "metadata": {
            "evaluator_type": "hybrid_llm",
            "requires_live_execution": True,
            "supported_providers": ["openai"],
            "default_provider": "openai",
            "default_selected": False,
            "framework": _APEX_FRAMEWORK,
            "warnings": [_AFCE_STATEMENT],
        },
    },
    {
        "identifier": "ace_ct_inspired",
        "display_name": "ACE-CT-inspired (experimental)",
        "version": "0.1.0-experimental",
        "module_path": (
            "plugins.evaluators.ace_ct_inspired_evaluator:ACECTInspiredRubricEvaluator"
        ),
        "metadata": {
            "evaluator_type": "experimental_rubric_llm",
            "requires_live_execution": True,
            "supported_providers": ["openai", "gemini"],
            "default_provider": "openai",
            "default_selected": False,
            "experimental": True,
            "framework": {
                "identifier": "ace-ct-inspired",
                "display_name": "ACE-CT-inspired",
                "version": "0.1.0-experimental",
                "rubric_version": "0.1.0-experimental",
                "validation_status": "experimental_unvalidated",
            },
            "warnings": [_ACE_WARNING],
        },
    },
]


def upgrade() -> None:
    op.create_table(
        "plugin_registrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plugin_kind", sa.String(length=20), nullable=False),
        sa.Column("registration_kind", sa.String(length=20), nullable=False),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("identifier", sa.String(length=150), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("module_path", sa.String(length=300), nullable=True),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("promoted_at", sa.DateTime(), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            f"plugin_kind IN {PLUGIN_KINDS!r}",
            name="ck_plugin_registrations_kind",
        ),
        sa.CheckConstraint(
            f"registration_kind IN {REGISTRATION_KINDS!r}",
            name="ck_plugin_registrations_registration_kind",
        ),
        sa.CheckConstraint(
            f"stage IN {PLUGIN_STAGES!r}",
            name="ck_plugin_registrations_stage",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["core.users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "plugin_kind", "identifier", name="uq_plugin_registrations_kind_identifier"
        ),
        schema="core",
    )
    op.create_index(
        "ix_plugin_registrations_kind_stage",
        "plugin_registrations",
        ["plugin_kind", "stage"],
        schema="core",
    )

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
                "plugin_kind": "evaluator",
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
    op.drop_index(
        "ix_plugin_registrations_kind_stage",
        table_name="plugin_registrations",
        schema="core",
    )
    op.drop_table("plugin_registrations", schema="core")
