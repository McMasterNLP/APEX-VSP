"""One-shot local-dev seed: demo case/users, multi-evaluator sessions, and a
sample Item 2A/2B reviewed state -- safe to re-run against a disposable local
PostgreSQL database (every step here looks up existing rows before writing).

This never makes a live/paid model-provider call. It extends (does not
replace) ``seed_demo_sessions.py``: that script still owns the 15 core
demo sessions (5 users x 3 empathy-quality fixtures); this script ensures
its prerequisites exist, then adds:

  1. the demo case (looked up by title, created if missing -- on an empty
     local database this naturally becomes id=1, matching
     ``demo_seed_mapping.json``'s hardcoded ``case_id``);
  2. the 5 demo/review users (upserted by ``supabase_auth_id``, matching
     ``demo_seed_mapping.json`` -- these do not need real Supabase Auth
     accounts locally, since nothing here logs in as them, they are only
     referenced by foreign key from seeded sessions);
  3. the original 15 sessions (delegated to ``seed_demo_sessions.seed_one``);
  4. three additional sessions -- same transcript as the "good" fixture,
     same reviewer account -- explicitly frozen to the three evaluator
     plugins seed_demo_sessions never exercises (hybrid_v1, hybrid_v2,
     ace_ct_inspired), so the Admin Session Logs list and the Research
     Evaluation panel have a real transcript to select for each of the four
     evaluators. These three sessions intentionally have NO persisted
     learner-facing feedback: computing it for real would require a live
     OpenAI/Gemini call, which this script must never make. An administrator
     can compute it later through the Research Evaluation panel by
     explicitly opting into live execution, exactly like the existing
     safety-gated flow already tested elsewhere in this repository.
  5. one dedicated, synthetic session (not one of the 15: see
     ``ITEM2_DEMO_TURNS``) with a saved Item 1 "baseline" evaluation run
     (offline, rule-based, always safe), an Item 2A annotation set on it, and
     a sample reviewed state: one confirmed prediction, one rejected
     prediction, one typed span correction (best-effort, skipped if the run
     has no span_annotation prediction to correct), one human-added span,
     and a ``not_assessed`` coverage declaration. This uses a dedicated
     transcript rather than the original 15 sessions because
     ``seed_demo_sessions.py``'s fixtures ship pre-baked ``spans_json`` that
     does not satisfy the stricter Research/Item 1 native-result schema (at
     least one span's offsets are not integers) -- a pre-existing
     incompatibility between those fixtures and the Research adapter,
     unrelated to this script, and out of scope to fix here. This step also
     deliberately does not seed a relation or an "assessed" coverage level:
     both require framework/policy-specific label/type knowledge (and, for
     assessed coverage, a fully reviewed set) that would be brittle to
     hardcode safely across arbitrary future fixture changes. Author those
     by hand through the workspace UI.

Usage (from ``backend/``, against a LOCAL ``DATABASE_URL`` -- see
``make db-local-seed`` / ``docs/docker.md``):

  PYTHONPATH=src:. python -m scripts.seed_local_dev
  PYTHONPATH=src:. python -m scripts.seed_local_dev --force

``--force`` is passed through to the underlying per-fixture session seeding
(see ``seed_demo_sessions.py``); it does not affect the Item 2A/2B step,
which is always additive/idempotent on its own.

Never run this against the shared Supabase project.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import traceback
from pathlib import Path
from typing import Any
from uuid import UUID

# --- path setup: backend/src + backend (for tests.fixtures) ---
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

import scripts.seed_demo_sessions as demo_seed

DEMO_CASE_TITLE = "SPIKES difficult diagnosis discussion (seeded local demo case)"
MAPPING_PATH = _SCRIPT_DIR / "demo_seed_mapping.json"

# Evaluator identifiers used by Item 1's research-evaluation comparison, in
# the dotted-path form PluginRegistry/session.evaluator_plugin expects.
BASELINE_PLUGIN_PATH = "plugins.evaluators.apex_baseline_evaluator:ApexBaselineEvaluator"
DIVERSITY_EVALUATOR_PLUGIN_PATHS = {
    "hybrid_v1": "plugins.evaluators.apex_hybrid_evaluator:ApexHybridEvaluator",
    "hybrid_v2": "plugins.evaluators.apex_hybrid_v2_evaluator:ApexHybridV2Evaluator",
    "ace_ct_inspired": "plugins.evaluators.ace_ct_inspired_evaluator:ACECTInspiredRubricEvaluator",
}

# Shared session_metadata.seed_source tag for every extra session this script
# adds beyond seed_demo_sessions's original 15 (evaluator-diversity sessions
# and the dedicated Item 2A/2B demo session), so they're all found the same
# idempotent way and never collide with seed_demo_sessions's own bookkeeping.
EXTRA_SESSION_SEED_SOURCE = "seed_local_dev_extra"

# Item 2A/2B sample state is seeded for this reviewer account, matching the
# admin persona used throughout demo_seed_mapping.json.
ITEM2_REVIEWER_EMAIL = "admin.review@apex.com"

# The evaluator-diversity sessions reuse the "good" fixture's transcript (and
# the reviewer's matching seed_key, for a human-readable link between the
# two) purely as plain, unscored session rows -- they are never run through
# ScoringService or the Research adapter, so the fixture-vs-adapter
# incompatibility noted above does not apply to them.
GOOD_FIXTURE_NAME = "good_strong_empathy_complete_spikes"
GOOD_FIXTURE_SEED_KEY = "admin_review_good_v1"


def _resolve_plugin(dotted_path: str):
    """Load/register a plugin class by dotted path, returning (name, version)."""
    try:
        cls = PluginRegistry.get_evaluator(dotted_path)
    except ValueError:
        cls = _load_class_from_path(dotted_path)
        PluginRegistry.register_evaluator(dotted_path, cls)
    return getattr(cls, "name", dotted_path), getattr(cls, "version", None)


def _ensure_baseline_evaluator(db: DBSession, case: Case) -> None:
    # settings.evaluator_plugin -- the fallback _resolve_frozen_plugins uses
    # for any case that doesn't set its own override -- defaults to a
    # live-LLM-requiring evaluator (apex_hybrid_evaluator). Without an
    # explicit case-level override, seeding sessions for this case would
    # silently attempt real OpenAI calls the moment ScoringService.
    # generate_feedback runs (degrading to a rule-only fallback on failure,
    # exactly as it does with the placeholder test-key in this script's own
    # local testing -- but a real configured key would make a real, paid
    # call). Pin this case to the offline, rule-based baseline evaluator,
    # mirroring the same safe pattern already used by
    # scripts/run_seeded_evaluator_case_study.py.
    if case.evaluator_plugin != BASELINE_PLUGIN_PATH:
        case.evaluator_plugin = BASELINE_PLUGIN_PATH
        db.commit()
        db.refresh(case)


def ensure_local_case(db: DBSession) -> Case:
    case = db.query(Case).filter(Case.id == 1).first()
    if case is not None and case.title == DEMO_CASE_TITLE:
        print(f"case: reusing id=1 ({case.title!r})")
        _ensure_baseline_evaluator(db, case)
        return case
    case = db.query(Case).filter(Case.title == DEMO_CASE_TITLE).first()
    if case is not None:
        print(f"case: reusing id={case.id} ({case.title!r})")
        if case.id != 1:
            print(
                f"    NOTE: resolved case id={case.id}, not 1 -- "
                "demo_seed_mapping.json's case_id will be ignored in favor of this id."
            )
        _ensure_baseline_evaluator(db, case)
        return case
    case = Case(
        title=DEMO_CASE_TITLE,
        description="Seeded local-dev case covering a difficult-diagnosis SPIKES conversation.",
        script="Fixture-owned transcript; the seeded turns below are used as-is.",
        difficulty_level="intermediate",
        category="demo",
        patient_background="Synthetic local-dev fixture; no real patient data.",
        expected_spikes_flow=json.dumps(
            ["setting", "perception", "invitation", "knowledge", "empathy", "strategy_summary"]
        ),
        evaluator_plugin=BASELINE_PLUGIN_PATH,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    print(f"case: created id={case.id} ({case.title!r})")
    if case.id != 1:
        print(
            f"    NOTE: created case id={case.id}, not 1 -- "
            "demo_seed_mapping.json's case_id will be ignored in favor of this id."
        )
    return case


def ensure_local_users(db: DBSession, mapping_rows: list[dict[str, Any]]) -> dict[str, User]:
    """Upsert the demo/review users referenced by mapping_rows, keyed by email."""
    user_repo = UserRepository(db)
    seen: dict[str, tuple[str, str]] = {}
    for row in mapping_rows:
        supa = str(row["supabase_auth_id"])
        email = str(row["email"])
        seen.setdefault(supa, (supa, email))

    users_by_email: dict[str, User] = {}
    for supa, email in seen.values():
        user = user_repo.get_by_supabase_id(supa)
        if user is not None:
            print(f"user: reusing id={user.id} email={user.email!r} supabase_auth_id={supa}")
            users_by_email[user.email] = user
            continue
        role = "admin" if email.startswith("admin") else "trainee"
        full_name = email.split("@", 1)[0].replace(".", " ").title()
        user = User(
            supabase_auth_id=UUID(supa),
            email=email,
            role=role,
            full_name=full_name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"user: created id={user.id} email={email!r} role={role!r} supabase_auth_id={supa}")
        users_by_email[user.email] = user
    return users_by_email


async def seed_original_demo_sessions(
    db: DBSession, case: Case, mapping_rows: list[dict[str, Any]], *, force: bool
) -> None:
    print("\n=== original 15 demo sessions (seed_demo_sessions.seed_one) ===")
    for row in mapping_rows:
        seed_key = row["seed_key"]
        fixture_name = row["fixture_name"]
        fixture = demo_seed.FIXTURES_BY_NAME.get(fixture_name)
        if fixture is None:
            raise SystemExit(f"Unknown fixture_name={fixture_name!r} in {MAPPING_PATH}")
        user_repo = UserRepository(db)
        user = user_repo.get_by_supabase_id(str(row["supabase_auth_id"]))
        if user is None:
            raise SystemExit(f"No core.users row for supabase_auth_id={row['supabase_auth_id']!r}")
        await demo_seed.seed_one(
            db,
            fixture=fixture,
            user=user,
            case=case,
            case_id=case.id,
            seed_key=seed_key,
            email_optional=row.get("email"),
            dry_run=False,
            force=force,
        )


def _find_diversity_session(db: DBSession, *, user_id: int, case_id: int, seed_key: str) -> SessionEntity | None:
    for session in demo_seed._sessions_for_user_case(db, user_id=user_id, case_id=case_id):
        meta = demo_seed._parse_session_metadata(session.session_metadata)
        if meta.get("seed_key") == seed_key and meta.get("seed_source") == EXTRA_SESSION_SEED_SOURCE:
            return session
    return None


def seed_evaluator_diversity_sessions(db: DBSession, case: Case, users_by_email: dict[str, User]) -> None:
    """Add one extra session per non-baseline evaluator, all sharing the "good"
    fixture's transcript with the reviewer's original baseline session, so the
    Research Evaluation panel has a real, identical transcript to compare all
    four evaluators against -- without ever running the three live-provider
    evaluators automatically during seeding.
    """
    print("\n=== evaluator-diversity demo sessions (same transcript, different frozen evaluator) ===")
    fixture = demo_seed.FIXTURES_BY_NAME[GOOD_FIXTURE_NAME]
    user = users_by_email[ITEM2_REVIEWER_EMAIL]

    for evaluator_key, dotted_path in DIVERSITY_EVALUATOR_PLUGIN_PATHS.items():
        seed_key = f"{GOOD_FIXTURE_SEED_KEY}_{evaluator_key}"
        existing = _find_diversity_session(db, user_id=user.id, case_id=case.id, seed_key=seed_key)
        if existing is not None:
            print(f"    SKIP: {evaluator_key} demo session already exists (session_id={existing.id})")
            continue

        plugin_name, plugin_version = _resolve_plugin(dotted_path)
        ended = utc_now()
        session = SessionEntity(
            user_id=user.id,
            case_id=case.id,
            state="completed",
            ended_at=ended,
            duration_seconds=600,
            session_metadata=json.dumps(
                {
                    "seed_key": seed_key,
                    "seed_source": EXTRA_SESSION_SEED_SOURCE,
                    "fixture_name": GOOD_FIXTURE_NAME,
                }
            ),
            evaluator_plugin=plugin_name,
            evaluator_version=plugin_version,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        for row in fixture["transcript"]:
            db.add(demo_seed._turn_from_fixture_row(row, session_id=session.id, owner_user_id=user.id))
        db.commit()
        print(
            f"    created session_id={session.id} evaluator_plugin={plugin_name!r} "
            "(no persisted feedback -- would require a live provider call)"
        )


def _pick_short_selection(transcript_hash: str, turns: tuple[Any, ...]) -> CanonicalSpanSelection | None:
    """First clean word (>=3 code points, no surrounding whitespace) in any turn."""
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
    """Extend a model-predicted span by one code point (right, else left) to
    build a valid, exact boundary correction -- never fabricated text."""
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


# A dedicated, synthetic transcript for the Item 2A/2B demo state, distinct
# from seed_demo_sessions's fixtures. Those fixtures ship pre-baked
# spans_json that (independently of this script) does not satisfy the
# stricter Research/Item 1 native-result schema -- e.g. some spans carry a
# non-integer start_char -- so saving a research evaluation run against them
# fails with `invalid_native_result` even outside of this seed script. That
# is a pre-existing incompatibility between those fixtures and the Research
# adapter, not something introduced or fixable here; this dedicated
# transcript sidesteps it by computing its own spans_json the same way a
# live session turn would (see ``_spans_json_for``), which the adapter does
# accept.
ITEM2_DEMO_SEED_KEY = "admin_review_item2_demo_v1"
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


def ensure_item2_demo_session(db: DBSession, case: Case, reviewer: User) -> SessionEntity:
    existing = _find_diversity_session(db, user_id=reviewer.id, case_id=case.id, seed_key=ITEM2_DEMO_SEED_KEY)
    if existing is not None:
        print(f"    reusing Item 2A/2B demo session_id={existing.id}")
        return existing

    from adapters.nlu.span_detector import SpanDetector

    span_detector = SpanDetector()
    ended = utc_now()
    session = SessionEntity(
        user_id=reviewer.id,
        case_id=case.id,
        state="completed",
        ended_at=ended,
        duration_seconds=300,
        session_metadata=json.dumps(
            {"seed_key": ITEM2_DEMO_SEED_KEY, "seed_source": EXTRA_SESSION_SEED_SOURCE}
        ),
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
                user_id=reviewer.id if role == "user" else None,
                turn_number=index,
                role=role,
                text=text,
                spans_json=_spans_json_for(role, text, span_detector),
            )
        )
    db.commit()
    print(f"    created Item 2A/2B demo session_id={session.id}")
    return session


async def seed_item2_demo_state(db: DBSession, case: Case, users_by_email: dict[str, User]) -> None:
    """Save one baseline evaluation run + Item 2A annotation set for a
    dedicated synthetic session, and populate one sample reviewed state on
    it. Every step checks for existing state first.
    """
    print("\n=== Item 2A/2B demo state (saved baseline run, annotation set, sample review) ===")
    reviewer = users_by_email[ITEM2_REVIEWER_EMAIL]
    run_service = ResearchEvaluationRunService(db)
    annotation_service = ResearchAnnotationService(db)

    session = ensure_item2_demo_session(db, case, reviewer)

    existing_runs = [r for r in run_service.list_for_session(session.id) if r.evaluator_identifier == "baseline"]
    if existing_runs:
        run_uuid = existing_runs[0].run_uuid
        print(f"    reusing saved baseline run {run_uuid}")
    else:
        try:
            record = await run_service.run_and_save(
                session.id,
                ResearchEvaluationRunSaveRequest(evaluator_identifier="baseline", allow_live=False),
                reviewer,
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
            reviewer,
        )
    except ResearchAnnotationServiceError as error:
        print(f"    SKIP: could not open annotation set ({error.category}: {error})")
        return
    print(
        f"    annotation set {annotation_set.annotation_set_uuid} "
        f"({len(annotation_set.eligible_predictions)} eligible predictions)"
    )
    seed_sample_review_state(annotation_service, run, annotation_set, reviewer)


def _seed_sample_decisions(annotation_service, run, annotation_set, reviewer: User):
    """One-time only (guarded by the caller): correct a span_annotation
    prediction, then confirm one other prediction, then reject a third.
    Correction goes first so confirm/reject (which don't need a specific
    projection type) don't consume the one span_annotation prediction the
    correction step needs.
    """
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
                    expected_set_revision=current.revision,
                    expected_decision_revision=None,
                    decision="confirmed",
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
                    expected_set_revision=current.revision,
                    expected_decision_revision=None,
                    decision="rejected",
                ),
                reviewer,
            )
            print(f"        rejected {target.prediction_id}")
        except ResearchAnnotationServiceError as error:
            print(f"        SKIP reject: {error}")
    return current


def seed_sample_review_state(annotation_service, run, annotation_set, reviewer: User) -> None:
    current = annotation_set

    if current.effective_decisions:
        print(
            f"        SKIP correct/confirm/reject: {len(current.effective_decisions)} "
            "decision(s) already recorded"
        )
    else:
        current = _seed_sample_decisions(annotation_service, run, current, reviewer)

    if not (current.human_annotation_revisions or ()):
        selection = _pick_short_selection(current.transcript_hash, run.transcript_snapshot)
        if selection is not None:
            try:
                current = annotation_service.create_human_annotation(
                    current.annotation_set_uuid,
                    HumanAnnotationCreateRequest(
                        expected_set_revision=current.revision,
                        selection=selection,
                        label="elicitation",
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
            print("        declared coverage: not_assessed")
        except ResearchAnnotationServiceError as error:
            print(f"        SKIP coverage: {error}")
    else:
        print("        SKIP coverage: already declared")


async def async_main(force: bool) -> None:
    load_plugins()
    _, mapping_rows = demo_seed.load_mapping(MAPPING_PATH)

    db = SessionLocal()
    try:
        case = ensure_local_case(db)
        users_by_email = ensure_local_users(db, mapping_rows)

        await seed_original_demo_sessions(db, case, mapping_rows, force=force)
        seed_evaluator_diversity_sessions(db, case, users_by_email)
        await seed_item2_demo_state(db, case, users_by_email)
    finally:
        db.close()

    print("\nDone.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Passed through to seed_demo_sessions: delete+re-seed the 15 original demo sessions.",
    )
    args = parser.parse_args()
    try:
        asyncio.run(async_main(force=args.force))
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
