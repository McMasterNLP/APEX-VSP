"""add linked_registration_id and seed research-adapter counterpart rows

Revision ID: b5c6d7e8f9a0
Revises: f3a4b5c6d7e8
Create Date: 2026-09-16

Two things, kept in one migration since the second depends on the first:

1. Adds a nullable, self-referential ``linked_registration_id`` column to
   ``plugin_registrations``. Purely informational/display metadata --
   RegistryService.link() sets it symmetrically on both rows of a pair and it
   never affects stage, promotion, or which code path actually executes.

2. Seeds four new registrations representing the Research Evaluator adapter
   side of the four evaluators already seeded (as their trainee-facing
   Evaluator wrapper) by d1e2f3a4b5c6 -- baseline / hybrid_v1 / hybrid_v2 /
   ace_ct_inspired. Those existing rows point at the trainee-facing
   ``plugins.evaluators.*`` classes; the new rows point at the separate
   ``services.research_adapters.*`` adapter classes actually registered in
   ``research_adapters/defaults.py``. Both sides use the same conceptual
   evaluator identity (they share a name in ``defaults.py`` and
   ``EVALUATOR_DEFINITIONS``), but are two different plugin protocols per the
   deliberate trainee/research separation -- see the Plugin Developer Guide.
   Linking them here makes that "same underlying model, two surfaces"
   relationship visible in the registry UI instead of only being implicit in
   shared naming convention.

   New rows use a distinct ``identifier`` (prefixed ``research_``) since the
   table's unique constraint is on (plugin_kind, identifier) and the trainee
   identifier is already taken. Both are ``plugin_kind="evaluator"``, per the
   existing convention that the registry's "evaluator" kind spans both
   surfaces. Seeded as ``stage="promoted"`` since these adapters are already
   shipped and in active use today (Evaluate Sessions Run & Compare / Saved
   Runs), matching how d1e2f3a4b5c6 treated the trainee-side rows.
"""

import json
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RESEARCH_ADAPTER_ROWS = [
    {
        "identifier": "research_baseline",
        "counterpart_identifier": "baseline",
        "display_name": "APEX baseline (research adapter)",
        "version": "1.0",
        "module_path": "services.research_adapters.apex:ApexResearchAdapter",
        "metadata": {
            "research_adapter": True,
            "counterpart_identifier": "baseline",
            "evaluator_type": "rule_based",
            "requires_live_execution": False,
            "supported_providers": [],
            "default_provider": None,
        },
    },
    {
        "identifier": "research_hybrid_v1",
        "counterpart_identifier": "hybrid_v1",
        "display_name": "APEX hybrid v1 (research adapter)",
        "version": "1.0",
        "module_path": "services.research_adapters.apex:ApexResearchAdapter",
        "metadata": {
            "research_adapter": True,
            "counterpart_identifier": "hybrid_v1",
            "evaluator_type": "hybrid_llm",
            "requires_live_execution": True,
            "supported_providers": ["openai"],
            "default_provider": "openai",
        },
    },
    {
        "identifier": "research_hybrid_v2",
        "counterpart_identifier": "hybrid_v2",
        "display_name": "APEX hybrid v2 (research adapter)",
        "version": "1.0",
        "module_path": "services.research_adapters.apex:ApexResearchAdapter",
        "metadata": {
            "research_adapter": True,
            "counterpart_identifier": "hybrid_v2",
            "evaluator_type": "hybrid_llm",
            "requires_live_execution": True,
            "supported_providers": ["openai"],
            "default_provider": "openai",
        },
    },
    {
        "identifier": "research_ace_ct_inspired",
        "counterpart_identifier": "ace_ct_inspired",
        "display_name": "ACE-CT-inspired (research adapter, experimental)",
        "version": "0.1.0-experimental",
        "module_path": "services.research_adapters.ace_ct:ACECTResearchAdapter",
        "metadata": {
            "research_adapter": True,
            "counterpart_identifier": "ace_ct_inspired",
            "evaluator_type": "experimental_rubric_llm",
            "requires_live_execution": True,
            "supported_providers": ["openai", "gemini"],
            "default_provider": "openai",
            "experimental": True,
        },
    },
]


def upgrade() -> None:
    op.add_column(
        "plugin_registrations",
        sa.Column("linked_registration_id", sa.Integer(), nullable=True),
        schema="core",
    )
    op.create_foreign_key(
        "fk_plugin_registrations_linked_registration_id",
        "plugin_registrations",
        "plugin_registrations",
        ["linked_registration_id"],
        ["id"],
        source_schema="core",
        referent_schema="core",
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_plugin_registrations_linked_registration_id",
        "plugin_registrations",
        ["linked_registration_id"],
        schema="core",
    )

    bind = op.get_bind()
    seeded_at = datetime.utcnow()

    for row in _RESEARCH_ADAPTER_ROWS:
        counterpart_id = bind.execute(
            sa.text(
                "SELECT id FROM core.plugin_registrations "
                "WHERE plugin_kind = 'evaluator' AND identifier = :identifier"
            ),
            {"identifier": row["counterpart_identifier"]},
        ).scalar()

        insert_params = {
            "identifier": row["identifier"],
            "display_name": row["display_name"],
            "version": row["version"],
            "module_path": row["module_path"],
            "metadata_json": json.dumps(row["metadata"]),
            "counterpart_id": counterpart_id,
            "seeded_at": seeded_at,
        }

        if counterpart_id is None:
            # Counterpart missing (e.g. a fresh/partial DB) -- seed the
            # research row unlinked rather than failing the migration.
            bind.execute(
                sa.text(
                    "INSERT INTO core.plugin_registrations "
                    "(plugin_kind, registration_kind, stage, identifier, "
                    "display_name, version, module_path, metadata_json, "
                    "created_at, updated_at, promoted_at) "
                    "VALUES ('evaluator', 'native', 'promoted', :identifier, "
                    ":display_name, :version, :module_path, :metadata_json, "
                    ":seeded_at, :seeded_at, :seeded_at)"
                ),
                insert_params,
            )
            continue

        new_id = bind.execute(
            sa.text(
                "INSERT INTO core.plugin_registrations "
                "(plugin_kind, registration_kind, stage, identifier, "
                "display_name, version, module_path, metadata_json, "
                "linked_registration_id, created_at, updated_at, promoted_at) "
                "VALUES ('evaluator', 'native', 'promoted', :identifier, "
                ":display_name, :version, :module_path, :metadata_json, "
                ":counterpart_id, :seeded_at, :seeded_at, :seeded_at) "
                "RETURNING id"
            ),
            insert_params,
        ).scalar()

        bind.execute(
            sa.text(
                "UPDATE core.plugin_registrations "
                "SET linked_registration_id = :new_id "
                "WHERE id = :counterpart_id"
            ),
            {"new_id": new_id, "counterpart_id": counterpart_id},
        )


def downgrade() -> None:
    for row in _RESEARCH_ADAPTER_ROWS:
        op.get_bind().execute(
            sa.text(
                "DELETE FROM core.plugin_registrations "
                "WHERE plugin_kind = 'evaluator' AND identifier = :identifier"
            ),
            {"identifier": row["identifier"]},
        )
    op.drop_index(
        "ix_plugin_registrations_linked_registration_id",
        table_name="plugin_registrations",
        schema="core",
    )
    op.drop_constraint(
        "fk_plugin_registrations_linked_registration_id",
        "plugin_registrations",
        schema="core",
        type_="foreignkey",
    )
    op.drop_column("plugin_registrations", "linked_registration_id", schema="core")
