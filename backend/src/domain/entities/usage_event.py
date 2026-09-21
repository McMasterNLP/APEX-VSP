"""Usage event entity: a lightweight audit trail of metered, cost-incurring actions.

Backs the daily usage guardrails (see services/usage_service.py) added ahead
of handing the deployment's login to EACL reviewers -- the shared reviewer
account (and now the learner account) sit behind a credential that goes into
a public, indefinitely-archived submission, so every action that triggers a
real paid LLM/ASR/TTS call needs a bounded ceiling rather than an honor
system.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Index, Integer, String

from core.time import utc_now
from db.base import Base
from db.types import UTCDateTimeType

# chat_turn: a trainee turn that triggers a live patient-LLM reply.
# audio: an ASR transcription or a TTS synthesis (either direction of voice).
# live_evaluation: a research evaluation run executed with allow_live=True.
USAGE_CATEGORIES = ("chat_turn", "audio", "live_evaluation")


class UsageEvent(Base):
    """One metered action, written once at the moment it's allowed to proceed.

    Never updated or deleted -- UsageService reads these to enforce the
    per-user/global daily caps and to power the admin usage dashboard's
    trends. Deliberately minimal (no FK to the session/run that caused it):
    the only job here is counting by user + category + day, not duplicating
    the audit trails Turn and ResearchEvaluationRun already provide.
    """

    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("core.users.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(20), nullable=False)  # one of USAGE_CATEGORIES
    created_at = Column(UTCDateTimeType(), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_usage_events_user_category_created", "user_id", "category", "created_at"),
        Index("ix_usage_events_category_created", "category", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<UsageEvent(id={self.id}, user_id={self.user_id}, category={self.category!r})>"
