"""ensure core schema exists

All ORM models default to the "core" schema (see ``db/metadata.py``), but no
migration has ever created that schema: on the shared Supabase project it
already exists with the database's own default ``search_path`` set to
``core, public`` (configured outside of any migration), so every historical
migration's unqualified ``op.create_table(...)`` call has always landed in
``core`` there. A fresh local PostgreSQL database has neither the schema nor
that ``search_path`` default, so replaying this migration history from
scratch fails as soon as an early migration tries to create a table.

This migration does not fix that ordering problem by itself -- the
``search_path`` still has to be set at the database level *before* the
historical chain runs, which can't be done portably from inside a migration
against an arbitrary database name (see ``make db-local-up`` /
``docs/docker.md``). What this migration does provide is an explicit,
idempotent, safe-anywhere step so ``core`` is guaranteed to exist by the time
any migration after this one runs, instead of relying entirely on that
external, undocumented database setting.

Revision ID: 1fc6c6467582
Revises: c380db356077
Create Date: 2026-09-02 20:45:00.495711

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '1fc6c6467582'
down_revision: Union[str, None] = 'c380db356077'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS core")


def downgrade() -> None:
    # Intentionally not reversed: every table from every earlier migration
    # lives in this schema, so dropping it here would be destructive far
    # beyond what this migration added. Downgrading past this revision still
    # leaves the (now pre-existing) schema in place, which is safe.
    pass

