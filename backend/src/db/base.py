"""Declarative base plus lazy compatibility exports for database runtime objects.

ORM entities import :data:`Base` from this module. Keeping that import free of
application settings allows domain models to be used by offline tooling. Existing
runtime imports remain supported and initialize the configured engine on demand.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from db.metadata import Base, metadata

if TYPE_CHECKING:
    from db.runtime import SessionLocal, engine, get_db, init_db

_RUNTIME_NAMES = frozenset({"SessionLocal", "engine", "get_db", "init_db"})


def __getattr__(name: str) -> Any:
    if name in _RUNTIME_NAMES:
        import db.runtime as _runtime

        return getattr(_runtime, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["Base", "metadata", "SessionLocal", "engine", "get_db", "init_db"]
