"""Static and metadata checks for the reversible Item 2B migration."""

from pathlib import Path

from domain.entities.research_annotation import (
    ResearchAuthoredRelationRevision,
    ResearchCoverageDeclarationRevision,
    ResearchHumanAnnotationRevision,
)


def test_authoring_entities_are_append_only_and_use_restrictive_foreign_keys():
    for entity in (
        ResearchHumanAnnotationRevision,
        ResearchAuthoredRelationRevision,
        ResearchCoverageDeclarationRevision,
    ):
        assert all(foreign_key.ondelete == "RESTRICT" for foreign_key in entity.__table__.foreign_keys)


def test_authoring_migration_has_three_revision_tables_and_reverse_order_rollback():
    migration = (
        Path(__file__).parents[2]
        / "src/db/migrations/versions/c3b4d5e6f7a8_add_research_annotation_authoring.py"
    ).read_text(encoding="utf-8")
    names = (
        "research_human_annotation_revisions",
        "research_authored_relation_revisions",
        "research_coverage_declaration_revisions",
    )
    assert 'down_revision: Union[str, None] = "f2a3b4c5d6e7"' in migration
    assert all(migration.count(name) >= 3 for name in names)
    assert migration.count('ondelete="RESTRICT"') >= 7
    downgrade = migration.split("def downgrade()", maxsplit=1)[1]
    assert downgrade.index(names[2]) < downgrade.index(names[1]) < downgrade.index(names[0])
