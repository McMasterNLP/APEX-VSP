"""Usage controller/router: the user-facing "how much do I have left today" view."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.deps import get_current_user, get_db
from domain.entities.user import User
from domain.models.usage import CategoryUsageResponse, UsageMeResponse
from services.usage_service import UsageService

router = APIRouter(prefix="/usage", tags=["usage"])


def _resets_at_iso() -> str:
    """Next UTC midnight, as an ISO-8601 string -- when today's counters reset."""
    now = datetime.now(timezone.utc)
    tomorrow = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)
    return tomorrow.isoformat().replace("+00:00", "Z")


@router.get("/me", response_model=UsageMeResponse)
async def get_my_usage(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Today's usage for the current user against the per-user/global daily caps."""
    usage_service = UsageService(db)
    summary = usage_service.get_user_summary(current_user.id)
    return UsageMeResponse(
        categories=[
            CategoryUsageResponse(
                category=item.category,
                label=item.label,
                user_count=item.user_count,
                user_limit=item.user_limit,
                user_remaining=item.user_remaining,
                global_count=item.global_count,
                global_limit=item.global_limit,
                global_remaining=item.global_remaining,
            )
            for item in summary
        ],
        resets_at=_resets_at_iso(),
    )
