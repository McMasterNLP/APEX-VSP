"""Core module for security, errors, dependencies, and events.

FastAPI dependencies live in ``core.deps`` but are *not* imported eagerly here.
That avoids a circular import when ORM entities (e.g. ``domain.entities.case``)
import ``core.time``: loading ``core`` must not pull in ``repositories`` before
``Case`` is fully defined.
"""

from __future__ import annotations

from typing import Any

from core.errors import (
    AppError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
    app_error_handler,
    general_exception_handler,
    http_exception_handler,
)
from core.security import (
    RoleScopes,
    decode_supabase_token,
)

_DEP_NAMES = frozenset(
    {
        "get_current_user",
        "get_db",
        "require_role",
        "require_trainee",
        "require_admin",
        "verify_session_access",
    }
)
_EVENT_NAMES = frozenset({"create_start_app_handler", "create_stop_app_handler"})


def __getattr__(name: str) -> Any:
    if name in _DEP_NAMES:
        import core.deps as _deps

        return getattr(_deps, name)
    if name in _EVENT_NAMES:
        import core.events as _events

        return getattr(_events, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Dependencies (lazy-loaded via __getattr__)
    "get_db",
    "get_current_user",
    "require_trainee",
    "require_admin",
    "require_role",
    "verify_session_access",
    # Errors
    "AppError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
    "ExternalServiceError",
    "app_error_handler",
    "http_exception_handler",
    "general_exception_handler",
    # Security
    "RoleScopes",
    "decode_supabase_token",
    # Events
    "create_start_app_handler",
    "create_stop_app_handler",
]
