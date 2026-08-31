"""SQLAlchemy declarative metadata without application runtime configuration."""

from sqlalchemy import MetaData
from sqlalchemy.orm import declarative_base

# All tables default to the "core" schema.
metadata = MetaData(schema="core")
Base = declarative_base(metadata=metadata)

__all__ = ["Base", "metadata"]
