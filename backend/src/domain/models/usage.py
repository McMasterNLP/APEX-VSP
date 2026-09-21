"""Usage guardrail schemas: per-user limits view and admin trends dashboard."""

from pydantic import BaseModel, Field


class CategoryUsageResponse(BaseModel):
    """Today's usage + limit for one category."""

    category: str
    label: str
    user_count: int
    user_limit: int
    user_remaining: int
    global_count: int
    global_limit: int
    global_remaining: int


class UsageMeResponse(BaseModel):
    """User-facing view: today's usage against the per-user and global caps."""

    categories: list[CategoryUsageResponse]
    resets_at: str = Field(description="ISO-8601 UTC instant when today's counters reset")


class UsageTrendDay(BaseModel):
    """One day's event counts by category."""

    date: str
    chat_turn: int
    audio: int
    live_evaluation: int


class UsageAdminResponse(BaseModel):
    """Admin-facing view: today's global usage + a recent daily trend."""

    categories: list[CategoryUsageResponse]
    trend: list[UsageTrendDay]
    resets_at: str
