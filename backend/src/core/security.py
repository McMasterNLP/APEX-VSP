"""Security utilities for JWT verification."""

from typing import Any, Optional

from jose import ExpiredSignatureError, JWTError, jwt

from config.logging import get_logger
from config.settings import get_settings

logger = get_logger(__name__)


def decode_supabase_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and verify a Supabase-issued JWT using the project's JWT secret."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload
    except ExpiredSignatureError:
        logger.warning("Supabase JWT expired")
        return None
    except JWTError as e:
        logger.warning("Supabase JWT decode error: %s", e)
        return None


# Role-based access control scopes
class RoleScopes:
    """Define role-based access scopes."""

    TRAINEE = "trainee"
    ADMIN = "admin"
    RESEARCHER = "researcher"

    @classmethod
    def get_all_scopes(cls) -> list[str]:
        """Get all available role scopes."""
        return [cls.TRAINEE, cls.ADMIN, cls.RESEARCHER]

    @classmethod
    def has_permission(cls, user_role: str, required_role: str) -> bool:
        """Check if user role has permission for required role."""
        role_hierarchy = {
            cls.ADMIN: [cls.ADMIN, cls.TRAINEE],
            cls.TRAINEE: [cls.TRAINEE],
            # Researcher gets everything trainee-gated (dashboard, cases,
            # sessions, feedback, analytics) plus researcher-only routes --
            # everything except true admin-only endpoints (require_admin).
            cls.RESEARCHER: [cls.RESEARCHER, cls.TRAINEE],
        }
        return required_role in role_hierarchy.get(user_role, [])
