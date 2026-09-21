"""EACL demo seed: reviewer account, demo case, and a believable session
history -- SAFE to run against the shared Supabase project.

Unlike seed_local_dev.py (which explicitly must never run against shared
Supabase, because it fabricates core.users rows with made-up UUIDs that have
no real Supabase Auth account behind them), this script never creates a
user. It resolves ONE already-existing, real reviewer account by
supabase_auth_id -- the same account you signed up through the live
frontend and promoted to admin via SQL -- and only ever inserts
Session/Turn/Feedback/Research rows owned by that account's real user id.
If the account isn't found, this script stops (SystemExit), it does not
create one.

It reuses seed_demo_sessions_eacl.seed_one() (a duplicate of
seed_demo_sessions.seed_one with one addition: an optional ended_at
override, so the three quality-tier sessions can be backdated to read as a
believable multi-week improvement arc instead of all landing at the exact
second the script happens to run) plus the evaluator-diversity and Item
2A/2B annotation-workspace seeding logic duplicated from seed_local_dev.py
(those functions never touched user creation to begin with -- they just
take an already-resolved User in).

Before running, set these four env vars (never hardcode auth ids/emails in
this file -- it's committed to a public repo). Get the UUIDs with, in the
Supabase SQL editor:

    SELECT supabase_auth_id, email FROM core.users WHERE email = '<account email>';

  EACL_SEED_REVIEWER_EMAIL
  EACL_SEED_REVIEWER_SUPABASE_AUTH_ID
  EACL_SEED_LEARNER_EMAIL
  EACL_SEED_LEARNER_SUPABASE_AUTH_ID

Usage (from backend/, with backend/.env pointed at the shared Supabase
DATABASE_URL):

    PYTHONPATH=src:. python -m scripts.seed_eacl_demo
    PYTHONPATH=src:. python -m scripts.seed_eacl_demo --force

Never makes a live/paid LLM call: the demo case is pinned to the offline
rule-based baseline evaluator, same pattern as seed_local_dev.py.

What this does NOT seed, on purpose: exhaustive/assessed annotation
coverage, and therefore no validation run. Declaring coverage and clicking
Validate is meant to happen live during the demo video -- see the project
notes on why that's the moment worth showing on camera rather than
pre-baking.
"""

from __future__ import annotations

import os
import argparse
import asyncio
import json
import re
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_SRC_DIR = _SCRIPT_DIR.parent
_BACKEND_ROOT = _SRC_DIR.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy.orm import Session as DBSession

from core.plugin_manager import _load_class_from_path
from core.time import utc_now
from db.base import SessionLocal
from domain.entities.case import Case
from domain.entities.session import Session as SessionEntity
from domain.entities.turn import Turn
from domain.entities.user import User
from domain.models.research_annotation import (
    AnnotationSetCreateRequest,
    CanonicalSpanSelection,
    CoverageDeclarationWriteRequest,
    HumanAnnotationCreateRequest,
    ResearchEvaluationRunSaveRequest,
    ReviewDecisionWriteRequest,
    SpanCorrection,
)
from plugins.load_plugins import load_plugins
from plugins.registry import PluginRegistry
from repositories.user_repo import UserRepository
from services.research_annotation_service import (
    ResearchAnnotationService,
    ResearchAnnotationServiceError,
)
from services.research_evaluation_run_service import (
    ResearchEvaluationRunService,
    ResearchEvaluationRunServiceError,
)

import scripts.seed_demo_sessions_eacl as demo_seed


def _require_env(name: str) -> str:
    """Read a required env var or stop with a clear message.

    These four identify real, already-existing Supabase Auth accounts (see
    module docstring). They used to be hardcoded constants here, but this
    script is committed to a public repo, so they're read from the
    environment instead -- set them in backend/.env (gitignored) or export
    them in your shell before running.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(
            f"Missing required env var {name}. See this script's module docstring "
            "for the SQL to look up the value, then set it in backend/.env or export it."
        )
    return value


# REVIEWER_* identifies the account used both for the live OpenReview/demo
# credentials handed to reviewers and for the reviewer-facing seeded
# sessions. LEARNER_* owns the research-support sessions only
# (evaluator-diversity + the annotation-workspace demo session) -- nobody
# ever logs into that account and its credentials are never published
# anywhere; it exists solely so those sessions have a real owner other than
# the reviewer account, keeping the reviewer's own My Sessions list clean
# (no completed-but-unscored sessions to stumble into). Both must be real,
# verified Supabase Auth signups -- this script never fabricates a user.
REVIEWER_EMAIL = _require_env("EACL_SEED_REVIEWER_EMAIL")
REVIEWER_SUPABASE_AUTH_ID = _require_env("EACL_SEED_REVIEWER_SUPABASE_AUTH_ID")
LEARNER_EMAIL = _require_env("EACL_SEED_LEARNER_EMAIL")
LEARNER_SUPABASE_AUTH_ID = _require_env("EACL_SEED_LEARNER_SUPABASE_AUTH_ID")

DEMO_CASE_TITLE = "Breaking a Difficult Diagnosis: Newly Found Malignancy"

BASELINE_PLUGIN_PATH = "plugins.evaluators.apex_baseline_evaluator:ApexBaselineEvaluator"
DIVERSITY_EVALUATOR_PLUGIN_PATHS = {
    "hybrid_v1": "plugins.evaluators.apex_hybrid_evaluator:ApexHybridEvaluator",
    "hybrid_v2": "plugins.evaluators.apex_hybrid_v2_evaluator:ApexHybridV2Evaluator",
    "ace_ct_inspired": "plugins.evaluators.ace_ct_inspired_evaluator:ACECTInspiredRubricEvaluator",
}

EXTRA_SESSION_SEED_SOURCE = "eacl_demo_extra"

GOOD_FIXTURE_NAME = "good_strong_empathy_complete_spikes"
GOOD_FIXTURE_SEED_KEY = "eacl_good_v1"

# The trainee-facing improvement arc: (fixture_name, seed_key, days_ago, hour, minute).
# Backdated on purpose -- a session list where "bad", "medium", and "good"
# all land within the same minute reads as obviously synthetic. This spread
# reads as a trainee genuinely improving over three-ish weeks, ending a few
# days before you record rather than at the literal moment you run this.
SESSION_SCHEDULE: list[tuple[str, str, int, int, int]] = [
    ("bad_missed_empathy_sparse_spikes", "eacl_bad_v1", 21, 10, 20),
    ("medium_partial_empathy_partial_spikes", "eacl_medium_v1", 10, 15, 5),
    (GOOD_FIXTURE_NAME, GOOD_FIXTURE_SEED_KEY, 3, 11, 40),
]


def _scheduled_dt(days_ago: int, hour: int, minute: int) -> datetime:
    target_date = utc_now() - timedelta(days=days_ago)
    return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=timezone.utc)


def _resolve_plugin(dotted_path: str):
    try:
        cls = PluginRegistry.get_evaluator(dotted_path)
    except ValueError:
        cls = _load_class_from_path(dotted_path)
        PluginRegistry.register_evaluator(dotted_path, cls)
    return getattr(cls, "name", dotted_path), getattr(cls, "version", None)


def _ensure_baseline_evaluator(db: DBSession, case: Case) -> None:
    # Pin to the offline rule-based baseline so seeding (and the "good"
    # fixture's ScoringService.generate_feedback call) never attempts a
    # real, paid OpenAI/Gemini call.
    if case.evaluator_plugin != BASELINE_PLUGIN_PATH:
        case.evaluator_plugin = BASELINE_PLUGIN_PATH
        db.commit()
        db.refresh(case)


def ensure_demo_case(db: DBSession) -> Case:
    case = db.query(Case).filter(Case.title == DEMO_CASE_TITLE).first()
    if case is not None:
        print(f"case: reusing id={case.id} ({case.title!r})")
        _ensure_baseline_evaluator(db, case)
        return case
    case = Case(
        title=DEMO_CASE_TITLE,
        description="A follow-up visit where the clinician must disclose a difficult diagnosis, guided by the SPIKES protocol for delivering serious news.",
        script="Fixture-owned transcript; the seeded turns below are used as-is.",
        difficulty_level="intermediate",
        category="demo",
        patient_background=(
            "Patient returning for results after recent testing, visibly apprehensive about what the follow-up visit might reveal. Simulated case for communication-skills training."
        ),
        expected_spikes_flow=json.dumps(
            ["setting", "perception", "invitation", "knowledge", "empathy", "strategy_summary"]
        ),
        evaluator_plugin=BASELINE_PLUGIN_PATH,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    print(f"case: created id={case.id} ({case.title!r})")
    return case


def ensure_reviewer_user(db: DBSession) -> User:
    if REVIEWER_SUPABASE_AUTH_ID.startswith("TODO"):
        raise SystemExit(
            "REVIEWER_SUPABASE_AUTH_ID is still a placeholder -- fill it in at the top of this "
            "script (see the module docstring for the SQL query to look it up) before running."
        )
    user_repo = UserRepository(db)
    user = user_repo.get_by_supabase_id(REVIEWER_SUPABASE_AUTH_ID)
    if user is None:
        raise SystemExit(
            f"No core.users row for supabase_auth_id={REVIEWER_SUPABASE_AUTH_ID!r}. "
            "This script never creates users -- sign up through the live frontend first, "
            "then promote the row to admin via SQL, before running this."
        )
    if str(user.email).lower() != REVIEWER_EMAIL.lower():
        raise SystemExit(
            f"Email mismatch for user id={user.id}: expected {REVIEWER_EMAIL!r}, DB has {user.email!r}"
        )
    print(f"reviewer: using id={user.id} email={user.email!r} role={user.role!r}")
    return user


def ensure_learner_user(db: DBSession) -> User:
    if LEARNER_SUPABASE_AUTH_ID.startswith("TODO"):
        raise SystemExit(
            "LEARNER_SUPABASE_AUTH_ID is still a placeholder -- fill it in at the top of this "
            "script before running."
        )
    user_repo = UserRepository(db)
    user = user_repo.get_by_supabase_id(LEARNER_SUPABASE_AUTH_ID)
    if user is None:
        raise SystemExit(
            f"No core.users row for supabase_auth_id={LEARNER_SUPABASE_AUTH_ID!r}. "
            "This script never creates users -- sign up through the live frontend first "
            "before running this."
        )
    if str(user.email).lower() != LEARNER_EMAIL.lower():
        raise SystemExit(
            f"Email mismatch for user id={user.id}: expected {LEARNER_EMAIL!r}, DB has {user.email!r}"
        )
    print(f"learner: using id={user.id} email={user.email!r} role={user.role!r}")
    return user


def cleanup_stray_reviewer_owned_extra_sessions(db: DBSession, case: Case, reviewer: User, learner: User) -> None:
    """One-time auto-fix: earlier runs of this script (before the owner/actor
    split) created the evaluator-diversity and annotation-workspace sessions
    under the reviewer account instead of the learner account.

    This reassigns ownership (UPDATE) rather than deleting and recreating --
    research_evaluation_runs and everything chained under it (decisions,
    human annotations, coverage declarations) are wired as immutable at the
    ORM level, matching the paper's own reproducibility guarantee, so they
    can never be deleted, even here. Session and Turn are not part of that
    guarded set, so reassigning their owner is the correct fix. Safe to
    re-run: once nothing is left owned by the reviewer with this seed
    source, it's a no-op.
    """
    stray = [
        s
        for s in demo_seed._sessions_for_user_case(db, user_id=reviewer.id, case_id=case.id)
        if demo_seed._parse_session_metadata(s.session_metadata).get("seed_source") == EXTRA_SESSION_SEED_SOURCE
    ]
    if not stray:
        return
    print(f"\n=== auto-cleanup: reassigning {len(stray)} stray extra-session(s) to the learner account ===")
    for session in stray:
        print(f"    reassigning session_id={session.id}: reviewer -> learner")
        session.user_id = learner.id
        for turn in session.turns:
            if turn.user_id == reviewer.id:
                turn.user_id = learner.id
    db.commit()


async def seed_trainee_history(db: DBSession, case: Case, reviewer: User, *, force: bool) -> None:
    print("\n=== trainee session history (backdated bad -> medium -> good arc) ===")
    for fixture_name, seed_key, days_ago, hour, minute in SESSION_SCHEDULE:
        fixture = demo_seed.FIXTURES_BY_NAME.get(fixture_name)
        if fixture is None:
            raise SystemExit(f"Unknown fixture_name={fixture_name!r}")
        ended_at = _scheduled_dt(days_ago, hour, minute)
        await demo_seed.seed_one(
            db,
            fixture=fixture,
            user=reviewer,
            case=case,
            case_id=case.id,
            seed_key=seed_key,
            email_optional=REVIEWER_EMAIL,
            dry_run=False,
            force=force,
            ended_at_override=ended_at,
        )


def _find_extra_session(db: DBSession, *, user_id: int, case_id: int, seed_key: str) -> SessionEntity | None:
    for session in demo_seed._sessions_for_user_case(db, user_id=user_id, case_id=case_id):
        meta = demo_seed._parse_session_metadata(session.session_metadata)
        if meta.get("seed_key") == seed_key and meta.get("seed_source") == EXTRA_SESSION_SEED_SOURCE:
            return session
    return None


def seed_evaluator_diversity_sessions(db: DBSession, case: Case, owner: User) -> None:
    """One extra session per non-baseline evaluator, same transcript as the
    'good' fixture, so the Research evaluator-comparison view has a real
    transcript to run all four evaluators against (Use Case 1). Left at
    utc_now() (not backdated) since these are meant to be actively worked
    with live during the demo, not part of the trainee's session-history
    narrative.
    """
    print("\n=== evaluator-diversity sessions (Use Case 1: compare evaluators) ===")
    fixture = demo_seed.FIXTURES_BY_NAME[GOOD_FIXTURE_NAME]

    for evaluator_key, dotted_path in DIVERSITY_EVALUATOR_PLUGIN_PATHS.items():
        seed_key = f"{GOOD_FIXTURE_SEED_KEY}_{evaluator_key}"
        existing = _find_extra_session(db, user_id=owner.id, case_id=case.id, seed_key=seed_key)
        if existing is not None:
            print(f"    SKIP: {evaluator_key} session already exists (session_id={existing.id})")
            continue

        plugin_name, plugin_version = _resolve_plugin(dotted_path)
        ended = utc_now()
        session = SessionEntity(
            user_id=owner.id,
            case_id=case.id,
            state="completed",
            ended_at=ended,
            duration_seconds=600,
            session_metadata=json.dumps(
                {"seed_key": seed_key, "seed_source": EXTRA_SESSION_SEED_SOURCE, "fixture_name": GOOD_FIXTURE_NAME}
            ),
            evaluator_plugin=plugin_name,
            evaluator_version=plugin_version,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        for row in fixture["transcript"]:
            db.add(demo_seed._turn_from_fixture_row(row, session_id=session.id, owner_user_id=owner.id))
        db.commit()
        print(
            f"    created session_id={session.id} evaluator_plugin={plugin_name!r} "
            "(no persisted feedback -- would require a live provider call)"
        )


def _pick_short_selection(transcript_hash: str, turns: tuple[Any, ...]) -> CanonicalSpanSelection | None:
    for turn in turns:
        match = re.search(r"\w{3,}", turn.text)
        if not match:
            continue
        start, end = match.start(), match.end()
        return CanonicalSpanSelection(
            transcript_hash=transcript_hash,
            start_turn_number=turn.turn_number,
            end_turn_number=turn.turn_number,
            speaker=turn.role,
            start_offset=start,
            end_offset=end,
            selected_text=turn.text[start:end],
        )
    return None


def _extend_span_selection(transcript_hash: str, turns: tuple[Any, ...], span) -> CanonicalSpanSelection | None:
    turn = next((t for t in turns if t.turn_number == span.turn_number), None)
    if turn is None:
        return None
    start, end = span.start_offset, span.end_offset
    if end < len(turn.text):
        end += 1
    elif start > 0:
        start -= 1
    else:
        return None
    return CanonicalSpanSelection(
        transcript_hash=transcript_hash,
        start_turn_number=turn.turn_number,
        end_turn_number=turn.turn_number,
        speaker=turn.role,
        start_offset=start,
        end_offset=end,
        selected_text=turn.text[start:end],
    )


ITEM2_DEMO_SEED_KEY = "eacl_item2_demo_v1"
ITEM2_DEMO_TURNS = (
    ("user", "How are you feeling today?"),
    ("assistant", "I'm very worried about the test results — I haven't slept."),
    ("user", "That sounds really hard. Tell me more about what's on your mind."),
    ("assistant", "It's the waiting that's the worst part, honestly."),
    ("user", "I understand. We'll go through the results together."),
)


def _spans_json_for(role: str, text: str, span_detector) -> str | None:
    if role != "assistant":
        return None
    spans = span_detector.detect_eo_spans(text)
    for span in spans:
        span["span_type"] = "eo"
    return json.dumps(spans) if spans else None


def ensure_item2_demo_session(db: DBSession, case: Case, owner: User) -> SessionEntity:
    existing = _find_extra_session(db, user_id=owner.id, case_id=case.id, seed_key=ITEM2_DEMO_SEED_KEY)
    if existing is not None:
        print(f"    reusing annotation-workspace demo session_id={existing.id}")
        return existing

    from adapters.nlu.span_detector import SpanDetector

    span_detector = SpanDetector()
    ended = utc_now()
    session = SessionEntity(
        user_id=owner.id,
        case_id=case.id,
        state="completed",
        ended_at=ended,
        duration_seconds=300,
        session_metadata=json.dumps({"seed_key": ITEM2_DEMO_SEED_KEY, "seed_source": EXTRA_SESSION_SEED_SOURCE}),
        evaluator_plugin=BASELINE_PLUGIN_PATH,
        evaluator_version=_resolve_plugin(BASELINE_PLUGIN_PATH)[1],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    for index, (role, text) in enumerate(ITEM2_DEMO_TURNS, start=1):
        db.add(
            Turn(
                session_id=session.id,
                user_id=owner.id if role == "user" else None,
                turn_number=index,
                role=role,
                text=text,
                spans_json=_spans_json_for(role, text, span_detector),
            )
        )
    db.commit()
    print(f"    created annotation-workspace demo session_id={session.id}")
    return session


async def seed_annotation_workspace_state(db: DBSession, case: Case, owner: User, actor: User) -> None:
    """Saved baseline evaluation run + Item 2A annotation set with one
    confirmed, one rejected, one corrected prediction, and one human-added
    span (Use Case 3 / Figure 6). Coverage is left as not_assessed on
    purpose -- declaring exhaustive coverage and running Validate is meant
    to happen live in the demo video, not be pre-seeded.
    """
    print("\n=== annotation-workspace demo state (Use Case 3) ===")
    run_service = ResearchEvaluationRunService(db)
    annotation_service = ResearchAnnotationService(db)

    session = ensure_item2_demo_session(db, case, owner)

    existing_runs = [r for r in run_service.list_for_session(session.id) if r.evaluator_identifier == "baseline"]
    if existing_runs:
        run_uuid = existing_runs[0].run_uuid
        print(f"    reusing saved baseline run {run_uuid}")
    else:
        try:
            record = await run_service.run_and_save(
                session.id,
                ResearchEvaluationRunSaveRequest(evaluator_identifier="baseline", allow_live=False),
                actor,
            )
        except ResearchEvaluationRunServiceError as error:
            print(f"    SKIP: could not save baseline run ({error.category}: {error})")
            return
        run_uuid = record.run_uuid
        print(f"    saved baseline run {run_uuid}")

    run = run_service.get_run(run_uuid)
    try:
        annotation_set = annotation_service.create_annotation_set(
            run_uuid,
            AnnotationSetCreateRequest(
                guideline_identifier=run.annotation_policy.guideline_identifier,
                guideline_version=run.annotation_policy.guideline_version,
            ),
            actor,
        )
    except ResearchAnnotationServiceError as error:
        print(f"    SKIP: could not open annotation set ({error.category}: {error})")
        return
    print(
        f"    annotation set {annotation_set.annotation_set_uuid} "
        f"({len(annotation_set.eligible_predictions)} eligible predictions)"
    )
    _seed_sample_review_state(annotation_service, run, annotation_set, actor)


def _seed_sample_decisions(annotation_service, run, annotation_set, reviewer: User):
    current = annotation_set
    reviewed_ids = {d.prediction_id for d in current.effective_decisions}
    span_candidate = next(
        (
            p
            for p in current.eligible_predictions
            if p.prediction_id not in reviewed_ids and p.projection_type == "span_annotation"
        ),
        None,
    )
    if span_candidate is not None:
        original = span_candidate.original_prediction
        selection = _extend_span_selection(current.transcript_hash, run.transcript_snapshot, original)
        if selection is not None:
            try:
                current = annotation_service.record_decision(
                    current.annotation_set_uuid,
                    span_candidate.prediction_id,
                    ReviewDecisionWriteRequest(
                        expected_set_revision=current.revision,
                        expected_decision_revision=None,
                        decision="corrected",
                        correction=SpanCorrection(
                            corrected_label=original.label,
                            corrected_dimension=original.dimension,
                            corrected_start_char=selection.start_offset,
                            corrected_end_char=selection.end_offset,
                            corrected_text=selection.selected_text,
                            transcript_hash=selection.transcript_hash,
                            corrected_turn_number=selection.start_turn_number,
                            corrected_speaker=selection.speaker,
                        ),
                    ),
                    reviewer,
                )
                print(f"        corrected {span_candidate.prediction_id} -> {selection.selected_text!r}")
            except ResearchAnnotationServiceError as error:
                print(f"        SKIP correct: {error}")
        else:
            print("        SKIP correct: no room to extend the boundary by one code point")
    else:
        print("        SKIP correct: no unreviewed span_annotation prediction")

    reviewed_ids = {d.prediction_id for d in current.effective_decisions}
    unreviewed = [p for p in current.eligible_predictions if p.prediction_id not in reviewed_ids]
    if unreviewed:
        target = unreviewed[0]
        try:
            current = annotation_service.record_decision(
                current.annotation_set_uuid,
                target.prediction_id,
                ReviewDecisionWriteRequest(
                    expected_set_revision=current.revision, expected_decision_revision=None, decision="confirmed"
                ),
                reviewer,
            )
            print(f"        confirmed {target.prediction_id}")
        except ResearchAnnotationServiceError as error:
            print(f"        SKIP confirm: {error}")

    reviewed_ids = {d.prediction_id for d in current.effective_decisions}
    unreviewed = [p for p in current.eligible_predictions if p.prediction_id not in reviewed_ids]
    if unreviewed:
        target = unreviewed[0]
        try:
            current = annotation_service.record_decision(
                current.annotation_set_uuid,
                target.prediction_id,
                ReviewDecisionWriteRequest(
                    expected_set_revision=current.revision, expected_decision_revision=None, decision="rejected"
                ),
                reviewer,
            )
            print(f"        rejected {target.prediction_id}")
        except ResearchAnnotationServiceError as error:
            print(f"        SKIP reject: {error}")
    return current


def _seed_sample_review_state(annotation_service, run, annotation_set, reviewer: User) -> None:
    current = annotation_set

    if current.effective_decisions:
        print(f"        SKIP correct/confirm/reject: {len(current.effective_decisions)} decision(s) already recorded")
    else:
        current = _seed_sample_decisions(annotation_service, run, current, reviewer)

    if not (current.human_annotation_revisions or ()):
        selection = _pick_short_selection(current.transcript_hash, run.transcript_snapshot)
        if selection is not None:
            try:
                current = annotation_service.create_human_annotation(
                    current.annotation_set_uuid,
                    HumanAnnotationCreateRequest(
                        expected_set_revision=current.revision, selection=selection, label="elicitation"
                    ),
                    reviewer,
                )
                print(f"        added human span {selection.selected_text!r} (elicitation)")
            except ResearchAnnotationServiceError as error:
                print(f"        SKIP human span: {error}")
    else:
        print("        SKIP human span: one already exists")

    if current.coverage is None:
        try:
            current = annotation_service.declare_coverage(
                current.annotation_set_uuid,
                CoverageDeclarationWriteRequest(expected_set_revision=current.revision, coverage="not_assessed"),
                reviewer,
            )
            print("        declared coverage: not_assessed (declare exhaustive + Validate live in the demo)")
        except ResearchAnnotationServiceError as error:
            print(f"        SKIP coverage: {error}")
    else:
        print("        SKIP coverage: already declared")


async def async_main(force: bool) -> None:
    load_plugins()
    db = SessionLocal()
    try:
        case = ensure_demo_case(db)
        reviewer = ensure_reviewer_user(db)
        learner = ensure_learner_user(db)

        cleanup_stray_reviewer_owned_extra_sessions(db, case, reviewer, learner)

        await seed_trainee_history(db, case, reviewer, force=force)
        seed_evaluator_diversity_sessions(db, case, learner)
        await seed_annotation_workspace_state(db, case, learner, reviewer)
    finally:
        db.close()

    print("\nDone. Remaining live step for the demo: Review & Annotate -> declare exhaustive coverage -> Validate.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="Delete+re-seed the three trainee-history sessions if they exist."
    )
    args = parser.parse_args()
    try:
        asyncio.run(async_main(force=args.force))
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
