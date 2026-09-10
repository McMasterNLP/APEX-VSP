"""FastAPI dependencies for database sessions and authentication."""

from typing import Annotated, Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from config.logging import get_logger
from core.errors import AuthenticationError, AuthorizationError
from core.security import RoleScopes, decode_supabase_token
from db.base import SessionLocal
from domain.entities.user import User
from repositories.user_repo import UserRepository

logger = get_logger(__name__)
security = HTTPBearer()


# Database dependency
def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Authentication dependency
async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Get current authenticated user from a Supabase-issued JWT."""
    token = credentials.credentials
    payload = decode_supabase_token(token)
    
    if not payload:
        raise AuthenticationError("Invalid or expired token")
    
    supabase_user_id: str = payload.get("sub")
    if not supabase_user_id:
        raise AuthenticationError("Invalid token payload")
    
    user_repo = UserRepository(db)
    user = user_repo.get_by_supabase_id(supabase_user_id)
    
    if not user:
        raise AuthenticationError("User not found")
    
    return user


# Role-based dependencies
def require_role(required_role: str):
    """Dependency factory for role-based access control."""
    
    async def role_checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        """Check if user has required role."""
        if not RoleScopes.has_permission(current_user.role, required_role):
            raise AuthorizationError(
                f"Access denied. Required role: {required_role}",
                details={"user_role": current_user.role, "required_role": required_role}
            )
        return current_user
    
    return role_checker


# Convenience role dependencies
def require_trainee(
    current_user: Annotated[User, Depends(require_role(RoleScopes.TRAINEE))]
) -> User:
    """Ensure current user has at least trainee permissions."""
    return current_user


def require_admin(
    current_user: Annotated[User, Depends(require_role(RoleScopes.ADMIN))]
) -> User:
    """Ensure current user is an admin."""
    return current_user


def require_researcher(
    current_user: Annotated[User, Depends(require_role(RoleScopes.RESEARCHER))]
) -> User:
    """Ensure current user is a researcher."""
    return current_user


async def require_admin_or_researcher(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Ensure current user is either an admin or a researcher.

    `require_role`/`RoleScopes.has_permission` only check a single role's
    hierarchy, and admin/researcher are not hierarchically related, so this
    checks membership directly instead of composing two `require_role` deps.
    """
    if current_user.role not in (RoleScopes.ADMIN, RoleScopes.RESEARCHER):
        raise AuthorizationError(
            f"Access denied. Required role: {RoleScopes.ADMIN} or {RoleScopes.RESEARCHER}",
            details={
                "user_role": current_user.role,
                "required_role": f"{RoleScopes.ADMIN} or {RoleScopes.RESEARCHER}",
            },
        )
    return current_user


def verify_session_access(session, current_user: User) -> None:
    """
    Verify the current user has access to the session.
    - Admin: allow access to any session.
    - Researcher: allow read access to any session (needed for the evaluation
      workflow, which operates on real transcripts). This bypass is scoped to
      this helper only -- researcher is NOT treated as admin elsewhere.
    - Trainee: only allow if session.user_id == current_user.id.
    - Otherwise: raise AuthorizationError (403).
    """
    if current_user.role in ("admin", "researcher"):
        return
    if current_user.role == "trainee" and getattr(session, "user_id", None) == current_user.id:
        return
    raise AuthorizationError("Not authorized to access this session")

