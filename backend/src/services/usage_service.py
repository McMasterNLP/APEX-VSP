"""Usage guardrail service: enforce and track daily per-user/global caps.

Sits ahead of every metered, cost-incurring action (a live patient-LLM chat
turn, an ASR/TTS audio call, or a live research evaluation run) so the
shared credentials handed to EACL reviewers -- sitting behind a password in
a public, indefinitely-archived submission -- can't run up an unbounded
bill. See domain/entities/usage_event.py for the audit-trail table this
reads and writes, and config/settings.py for the six usage_daily_* limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from config.settings import Settings, get_settings
from core.errors import UsageLimitExceededError
from core.time import utc_now
from domain.entities.usage_event import USAGE_CATEGORIES, UsageEvent

Category = Literal["chat_turn", "audio", "live_evaluation"]

# Friendly labels for error messages / dashboard display.
_CATEGORY_LABELS: dict[str, str] = {
    "chat_turn": "chat turns",
    "audio": "voice (audio) requests",
    "live_evaluation": "live evaluator runs",
}


def _utc_day_bounds(at: datetime | None = None) -> tuple[datetime, datetime]:
    """Return the [start, end) UTC-calendar-day window containing `at`."""
    moment = at or utc_now()
    start = datetime(moment.year, moment.month, moment.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


@dataclass
class UsageLimits:
    per_user: int
    global_: int


@dataclass
class CategoryUsage:
    category: str
    label: str
    user_count: int
    user_limit: int
    global_count: int
    global_limit: int

    @property
    def user_remaining(self) -> int:
        return max(0, self.user_limit - self.user_count)

    @property
    def global_remaining(self) -> int:
        return max(0, self.global_limit - self.global_count)


class UsageService:
    """Checks and records usage against the daily caps in Settings."""

    def __init__(self, db: Session, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()

    def _limits_for(self, category: str) -> UsageLimits:
        per_user = getattr(self.settings, f"usage_daily_{category}_limit_per_user")
        global_ = getattr(self.settings, f"usage_daily_{category}_limit_global")
        return UsageLimits(per_user=per_user, global_=global_)

    def _count(self, category: str, user_id: int | None, start: datetime, end: datetime) -> int:
        query = self.db.query(func.count(UsageEvent.id)).filter(
            UsageEvent.category == category,
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
        if user_id is not None:
            query = query.filter(UsageEvent.user_id == user_id)
        return query.scalar() or 0

    def check_and_record(self, category: Category, user_id: int) -> None:
        """Enforce today's per-user and global caps, then record one event.

        Raises UsageLimitExceededError (429) if either cap is already met.
        Call this right before the expensive/paid work happens, not after --
        every one of its 4 call sites does the check before invoking the LLM/
        ASR/TTS/evaluator adapter.
        """
        if category not in USAGE_CATEGORIES:
            raise ValueError(f"Unknown usage category: {category!r}")

        limits = self._limits_for(category)
        start, end = _utc_day_bounds()

        user_count = self._count(category, user_id, start, end)
        if user_count >= limits.per_user:
            raise UsageLimitExceededError(
                f"You've reached today's limit of {limits.per_user} {_CATEGORY_LABELS[category]}. "
                "This resets at midnight UTC.",
                details={
                    "category": category,
                    "scope": "user",
                    "limit": limits.per_user,
                    "used": user_count,
                },
            )

        global_count = self._count(category, None, start, end)
        if global_count >= limits.global_:
            raise UsageLimitExceededError(
                f"This demo deployment has reached today's shared limit of {limits.global_} "
                f"{_CATEGORY_LABELS[category]}. This resets at midnight UTC.",
                details={
                    "category": category,
                    "scope": "global",
                    "limit": limits.global_,
                    "used": global_count,
                },
            )

        # Commit immediately (not just flush): this call is the durable record
        # that the action was authorized to proceed, and several call sites
        # (e.g. transcribe_audio_turn) never write anything else to the DB in
        # the same request -- a flush-only write would be silently discarded
        # on db.close() at the end of that request, making the cap a no-op.
        self.db.add(UsageEvent(user_id=user_id, category=category))
        self.db.commit()

    def get_user_summary(self, user_id: int) -> list[CategoryUsage]:
        """Today's usage + limits for one user, across all categories."""
        start, end = _utc_day_bounds()
        result = []
        for category in USAGE_CATEGORIES:
            limits = self._limits_for(category)
            result.append(
                CategoryUsage(
                    category=category,
                    label=_CATEGORY_LABELS[category],
                    user_count=self._count(category, user_id, start, end),
                    user_limit=limits.per_user,
                    global_count=self._count(category, None, start, end),
                    global_limit=limits.global_,
                )
            )
        return result

    def get_admin_summary(self) -> list[CategoryUsage]:
        """Today's global usage + limits across all categories (no per-user)."""
        start, end = _utc_day_bounds()
        result = []
        for category in USAGE_CATEGORIES:
            limits = self._limits_for(category)
            result.append(
                CategoryUsage(
                    category=category,
                    label=_CATEGORY_LABELS[category],
                    user_count=0,
                    user_limit=limits.per_user,
                    global_count=self._count(category, None, start, end),
                    global_limit=limits.global_,
                )
            )
        return result

    def get_admin_trends(self, days: int = 14) -> list[dict]:
        """Per-day, per-category event counts for the last `days` UTC days.

        Returns oldest-first: [{"date": "2026-09-08", "chat_turn": 12,
        "audio": 3, "live_evaluation": 0}, ...] -- one dict per day with a
        key per category, always present (0 when no events), so the frontend
        can hand this straight to a chart without gap-filling itself.
        """
        today_start, _ = _utc_day_bounds()
        range_start = today_start - timedelta(days=days - 1)

        rows = (
            self.db.query(
                UsageEvent.category,
                func.date_trunc("day", UsageEvent.created_at).label("day"),
                func.count(UsageEvent.id).label("count"),
            )
            .filter(UsageEvent.created_at >= range_start)
            .group_by(UsageEvent.category, "day")
            .all()
        )

        by_day: dict[date, dict[str, int]] = {}
        for category, day, count in rows:
            day_date = day.date() if hasattr(day, "date") else day
            by_day.setdefault(day_date, {c: 0 for c in USAGE_CATEGORIES})[category] = count

        out = []
        for offset in range(days):
            day_date = (range_start + timedelta(days=offset)).date()
            counts = by_day.get(day_date, {c: 0 for c in USAGE_CATEGORIES})
            out.append({"date": day_date.isoformat(), **counts})
        return out
