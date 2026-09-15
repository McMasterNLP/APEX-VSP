"""Tests covering the researcher-role widening of admin session routes,
and the new admin-only user role-update endpoint.

Verification of:
  GET /v1/admin/sessions            -- researcher allowed, matches admin behavior
  GET /v1/admin/sessions/{id}       -- researcher allowed
  GET /v1/admin/plugin-registry     -- researcher forbidden (admin-only)
  GET /v1/admin/users/overview      -- researcher forbidden (admin-only)
  PATCH /v1/admin/users/{id}/role   -- admin can promote a user to researcher; non-admin forbidden
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import app
from core.deps import get_current_user, get_db
from domain.entities.case import Case
from domain.entities.session import Session as SessionEntity
from domain.entities.user import User
from tests.utils.transcript_runner import create_all_for_test_engine

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
create_all_for_test_engine(_engine)

import itertools

_multi_session_fixture_counter = itertools.count()


def _get_test_db():
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _override_db():
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def db_session():
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_user(db_session):
    user = User(email=f"admin_{uuid.uuid4().hex[:12]}@test.com", role="admin")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def researcher_user(db_session):
    user = User(email=f"researcher_{uuid.uuid4().hex[:12]}@test.com", role="researcher")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def trainee_user(db_session):
    user = User(email=f"trainee_{uuid.uuid4().hex[:12]}@test.com", role="trainee")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def seeded_session(db_session, admin_user):
    case = Case(title="Admin Sessions Case", script="Script", difficulty_level="intermediate")
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    session = SessionEntity(
        user_id=admin_user.id, case_id=case.id, state="completed", duration_seconds=100
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def _override_user(user: User):
    async def _fake_user():
        return user

    app.dependency_overrides[get_current_user] = _fake_user


@pytest.mark.anyio
async def test_admin_sessions_list_allows_researcher(researcher_user, seeded_session):
    _override_user(researcher_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/admin/sessions")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_admin_session_detail_allows_researcher(researcher_user, seeded_session):
    _override_user(researcher_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/v1/admin/sessions/{seeded_session.id}")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_admin_sessions_list_allows_admin(admin_user, seeded_session):
    _override_user(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/admin/sessions")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_admin_sessions_list_rejects_trainee(trainee_user):
    _override_user(trainee_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/admin/sessions")
    assert response.status_code == 403


@pytest.mark.anyio
async def test_plugin_registry_rejects_researcher(researcher_user):
    _override_user(researcher_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/admin/plugin-registry")
    assert response.status_code == 403


@pytest.mark.anyio
async def test_users_overview_rejects_researcher(researcher_user):
    _override_user(researcher_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/admin/users/overview")
    assert response.status_code == 403


@pytest.mark.anyio
async def test_admin_can_promote_user_to_researcher(admin_user, trainee_user):
    _override_user(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.patch(
            f"/v1/admin/users/{trainee_user.id}/role", json={"role": "researcher"}
        )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "researcher"


@pytest.mark.anyio
async def test_role_update_rejects_invalid_role(admin_user, trainee_user):
    _override_user(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.patch(
            f"/v1/admin/users/{trainee_user.id}/role", json={"role": "superuser"}
        )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_role_update_rejects_researcher(researcher_user, trainee_user):
    _override_user(researcher_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.patch(
            f"/v1/admin/users/{trainee_user.id}/role", json={"role": "researcher"}
        )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_role_update_404_for_unknown_user(admin_user):
    _override_user(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.patch("/v1/admin/users/999999/role", json={"role": "researcher"})
    assert response.status_code == 404


@pytest.fixture
def multi_session_fixture(db_session, admin_user):
    """Two cases, two users, sessions spread across two days -- enough to exercise
    every admin sessions filter (user, case, date range) plus real pagination.

    @remarks
    `day1`/`day2` are offset by a counter that advances on every call, spaced far
    enough apart (1000 days) that no two invocations' date windows can ever overlap.
    This fixture is function-scoped and re-invoked once per test that uses it, and
    this module's DB is shared across the whole run with no per-test rollback (see
    the module-level `_engine`/`db_session` fixture above) -- a fixed absolute date
    would let different tests' sessions collide under the same date-range filter.
    """
    from datetime import datetime, timedelta, timezone

    offset = next(_multi_session_fixture_counter) * 1000
    day1 = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=offset)
    day2 = day1 + timedelta(days=4)

    other_user = User(email=f"other_{uuid.uuid4().hex[:12]}@test.com", role="trainee")
    db_session.add(other_user)
    case_a = Case(title="Filter Case A", script="Script", difficulty_level="intermediate")
    case_b = Case(title="Filter Case B", script="Script", difficulty_level="intermediate")
    db_session.add_all([case_a, case_b])
    db_session.commit()
    db_session.refresh(other_user)
    db_session.refresh(case_a)
    db_session.refresh(case_b)
    sessions = [
        SessionEntity(
            user_id=admin_user.id, case_id=case_a.id, state="completed",
            duration_seconds=100, started_at=day1,
        ),
        SessionEntity(
            user_id=admin_user.id, case_id=case_b.id, state="completed",
            duration_seconds=100, started_at=day2,
        ),
        SessionEntity(
            user_id=other_user.id, case_id=case_a.id, state="completed",
            duration_seconds=100, started_at=day2,
        ),
    ]
    db_session.add_all(sessions)
    db_session.commit()
    for session in sessions:
        db_session.refresh(session)
    return {
        "admin_user": admin_user,
        "other_user": other_user,
        "case_a": case_a,
        "case_b": case_b,
        "sessions": sessions,
        "day1": day1,
        "day2": day2,
    }


@pytest.mark.anyio
async def test_admin_sessions_total_reflects_the_true_matching_count_not_just_the_page(
    admin_user, multi_session_fixture
):
    """Regression test: `total` used to be `len(sessions)` (the current page's size,
    capped at `limit`), so a filter or a small page size silently under-reported how
    many matching sessions actually existed. It must reflect the full filtered count.

    Scoped by `user_id` to this fixture's own admin_user (unique per test call) so the
    assertion is exact regardless of other sessions left behind by earlier tests in this
    module -- this file shares one in-memory DB across the whole run with no per-test
    rollback (see the module-level `_engine`/`db_session` fixture above).
    """
    _override_user(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/v1/admin/sessions", params={"user_id": admin_user.id, "limit": 1}
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body["sessions"]) == 1
    assert body["total"] == 2
    assert body["skip"] == 0
    assert body["limit"] == 1


@pytest.mark.anyio
async def test_admin_sessions_filters_by_user_and_case_together(
    admin_user, multi_session_fixture
):
    _override_user(admin_user)
    case_a = multi_session_fixture["case_a"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/v1/admin/sessions",
            params={"user_id": admin_user.id, "case_id": case_a.id},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [s["case_id"] for s in body["sessions"]] == [case_a.id]
    assert [s["user_id"] for s in body["sessions"]] == [admin_user.id]


@pytest.mark.anyio
async def test_admin_sessions_filters_by_date_range(admin_user, multi_session_fixture):
    """Bounds both ends of the range around day2 (rather than only `start_date`) so the
    assertion isn't polluted by other tests' sessions, which default to `started_at=now()`
    -- comfortably after this fixture's 2026-01-01/2026-01-05 dates -- in this module's
    shared, non-rolled-back DB (see the module-level `_engine`/`db_session` fixture above).
    """
    from datetime import timedelta

    _override_user(admin_user)
    day2 = multi_session_fixture["day2"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/v1/admin/sessions",
            params={
                "start_date": day2.isoformat(),
                "end_date": (day2 + timedelta(days=1)).isoformat(),
            },
        )
    assert response.status_code == 200
    body = response.json()
    # Only the two sessions started on day2 (across both users) match.
    assert body["total"] == 2
    assert all(s["id"] != multi_session_fixture["sessions"][0].id for s in body["sessions"])


@pytest.mark.anyio
async def test_admin_sessions_pagination_pages_through_all_matching_rows(
    admin_user, multi_session_fixture
):
    """Bounds the query to this fixture's own day1/day2 range so the count of matching
    rows is exact, regardless of other sessions left behind by earlier tests in this
    module's shared, non-rolled-back DB (see the module-level `_engine`/`db_session`
    fixture above).
    """
    from datetime import timedelta

    _override_user(admin_user)
    day1 = multi_session_fixture["day1"]
    day2 = multi_session_fixture["day2"]
    date_params = {
        "start_date": day1.isoformat(),
        "end_date": (day2 + timedelta(days=1)).isoformat(),
    }
    transport = ASGITransport(app=app)
    seen_ids: list[int] = []
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for skip in (0, 2):
            response = await ac.get(
                "/v1/admin/sessions",
                params={"skip": skip, "limit": 2, **date_params},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["total"] == 3
            seen_ids.extend(s["id"] for s in body["sessions"])
    assert len(seen_ids) == len(set(seen_ids)) == 3


@pytest.fixture
def session_with_identified_owner(db_session):
    """A session owned by a trainee with a real name/email on file, for exercising the
    admin-vs-researcher identity redaction rule independent of who's making the request.
    """
    owner = User(
        email=f"trainee_owner_{uuid.uuid4().hex[:10]}@test.com",
        full_name="Pat Trainee",
        role="trainee",
    )
    db_session.add(owner)
    case = Case(title="Identity Redaction Case", script="Script", difficulty_level="intermediate")
    db_session.add(case)
    db_session.commit()
    db_session.refresh(owner)
    db_session.refresh(case)
    session = SessionEntity(
        user_id=owner.id, case_id=case.id, state="completed", duration_seconds=90
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return {"owner": owner, "session": session}


@pytest.mark.anyio
async def test_admin_sees_real_trainee_identity_in_sessions_list_and_detail(
    admin_user, session_with_identified_owner
):
    _override_user(admin_user)
    owner = session_with_identified_owner["owner"]
    session = session_with_identified_owner["session"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        listing = await ac.get("/v1/admin/sessions")
        detail = await ac.get(f"/v1/admin/sessions/{session.id}")
    assert listing.status_code == 200
    assert detail.status_code == 200
    row = next(s for s in listing.json()["sessions"] if s["id"] == session.id)
    assert row["user_full_name"] == "Pat Trainee"
    assert row["user_email"] == owner.email
    assert detail.json()["session"]["user_full_name"] == "Pat Trainee"
    assert detail.json()["session"]["user_email"] == owner.email


@pytest.mark.anyio
async def test_researcher_sees_pseudonymous_identity_but_real_transcript(
    researcher_user, session_with_identified_owner
):
    """Researchers need the real transcript to annotate/evaluate against, but never
    the trainee's real name or email -- this is the access-control fix itself.
    """
    _override_user(researcher_user)
    owner = session_with_identified_owner["owner"]
    session = session_with_identified_owner["session"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        listing = await ac.get("/v1/admin/sessions")
        detail = await ac.get(f"/v1/admin/sessions/{session.id}")
    assert listing.status_code == 200
    assert detail.status_code == 200

    row = next(s for s in listing.json()["sessions"] if s["id"] == session.id)
    assert row["user_full_name"] != "Pat Trainee"
    assert row["user_full_name"].startswith("participant_")
    assert row["user_email"] is None
    assert owner.email not in listing.text
    assert "Pat Trainee" not in listing.text

    detail_session = detail.json()["session"]
    assert detail_session["user_full_name"] == row["user_full_name"]
    assert detail_session["user_email"] is None
    assert owner.email not in detail.text
    assert "Pat Trainee" not in detail.text

    # The real transcript/session content is still fully present -- redaction is
    # identity-only, since the evaluation pipeline needs the real transcript.
    assert detail_session["id"] == session.id
    assert detail_session["case_id"] == session.case_id


@pytest.fixture
def evaluation_filter_fixture(db_session, admin_user):
    """Sessions covering every value the new Sessions-list filters exercise: two
    distinct (fixture-unique) patient/evaluator plugins, two states, and every
    evaluation-status bucket (no runs, needs review, in review, locked) driven by real
    `ResearchEvaluationRun`/`ResearchAnnotationSet` rows reviewed by two different
    reviewers.

    @remarks
    Plugin names are uuid-suffixed and reviewers are fixture-unique users so filter
    assertions on them are exact regardless of other sessions left behind by earlier
    tests in this module's shared, non-rolled-back DB (see the module-level
    `_engine`/`db_session` fixture above). `state` and bare `evaluation_status` values
    are NOT fixture-unique (only a few valid values exist), so tests exercising those
    combine them with this fixture's own `case_id` to stay exact.
    """
    from domain.entities.research_annotation import ResearchAnnotationSet, ResearchEvaluationRun

    suffix = uuid.uuid4().hex[:8]
    patient_plugin_a = f"alex_{suffix}"
    patient_plugin_b = f"jordan_{suffix}"
    evaluator_plugin_a = f"rubric_v1_{suffix}"
    evaluator_plugin_b = f"rubric_v2_{suffix}"

    reviewer_a = User(email=f"reviewer_a_{uuid.uuid4().hex[:10]}@test.com", role="researcher")
    reviewer_b = User(
        email=f"reviewer_b_{uuid.uuid4().hex[:10]}@test.com",
        role="researcher",
        full_name="Reviewer B",
    )
    db_session.add_all([reviewer_a, reviewer_b])
    case = Case(title="Filter Fixture Case", script="Script", difficulty_level="intermediate")
    db_session.add(case)
    db_session.commit()
    db_session.refresh(reviewer_a)
    db_session.refresh(reviewer_b)
    db_session.refresh(case)

    def make_session(*, patient_plugin, evaluator_plugin, state):
        s = SessionEntity(
            user_id=admin_user.id,
            case_id=case.id,
            state=state,
            duration_seconds=60,
            patient_model_plugin=patient_plugin,
            evaluator_plugin=evaluator_plugin,
        )
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)
        return s

    session_no_runs = make_session(
        patient_plugin=patient_plugin_a, evaluator_plugin=evaluator_plugin_a, state="completed"
    )
    session_needs_review = make_session(
        patient_plugin=patient_plugin_a, evaluator_plugin=evaluator_plugin_a, state="completed"
    )
    session_in_review = make_session(
        patient_plugin=patient_plugin_b, evaluator_plugin=evaluator_plugin_b, state="active"
    )
    session_locked = make_session(
        patient_plugin=patient_plugin_b, evaluator_plugin=evaluator_plugin_b, state="completed"
    )

    def make_run(session):
        run = ResearchEvaluationRun(
            source_session_id=session.id,
            item1_run_id=f"run_{uuid.uuid4().hex[:8]}",
            transcript_hash=uuid.uuid4().hex,
            transcript_projection_version="1.0",
            transcript_snapshot_json="[]",
            turn_count=1,
            envelope_schema_version="1.0",
            envelope_json="{}",
            evaluator_identifier="rubric",
            evaluator_version="1.0",
            framework_identifier="framework",
            framework_version="1.0",
            adapter_identifier="adapter",
            adapter_version="1.0",
            execution_mode="sync",
            execution_timestamp=datetime.now(timezone.utc),
            runtime_ms=10.0,
            status="success",
            created_by_user_id=admin_user.id,
        )
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)
        return run

    def make_annotation_set(run, *, reviewer, status):
        aset = ResearchAnnotationSet(
            evaluation_run_id=run.id,
            transcript_hash=run.transcript_hash,
            framework_identifier="framework",
            framework_version="1.0",
            annotation_policy_identifier="policy",
            annotation_policy_version="1.0",
            guideline_identifier="guideline",
            guideline_version="1.0",
            reviewer_user_id=reviewer.id,
            status=status,
            eligible_predictions_json="[]",
        )
        db_session.add(aset)
        db_session.commit()
        db_session.refresh(aset)
        return aset

    make_run(session_needs_review)  # saved run, no annotation set yet -> needs_review
    run_in_review = make_run(session_in_review)
    make_annotation_set(run_in_review, reviewer=reviewer_a, status="draft")
    run_locked = make_run(session_locked)
    make_annotation_set(run_locked, reviewer=reviewer_b, status="complete")

    return {
        "case": case,
        "reviewer_a": reviewer_a,
        "reviewer_b": reviewer_b,
        "patient_plugin_a": patient_plugin_a,
        "patient_plugin_b": patient_plugin_b,
        "evaluator_plugin_a": evaluator_plugin_a,
        "evaluator_plugin_b": evaluator_plugin_b,
        "session_no_runs": session_no_runs,
        "session_needs_review": session_needs_review,
        "session_in_review": session_in_review,
        "session_locked": session_locked,
    }


@pytest.mark.anyio
async def test_admin_sessions_filters_by_patient_plugin(admin_user, evaluation_filter_fixture):
    _override_user(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/v1/admin/sessions",
            params={"patient_plugin": evaluation_filter_fixture["patient_plugin_a"]},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert all(s["patient_model_plugin"] == evaluation_filter_fixture["patient_plugin_a"] for s in body["sessions"])


@pytest.mark.anyio
async def test_admin_sessions_filters_by_evaluator_plugin(admin_user, evaluation_filter_fixture):
    _override_user(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/v1/admin/sessions",
            params={"evaluator_plugin": evaluation_filter_fixture["evaluator_plugin_b"]},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert all(s["evaluator_plugin"] == evaluation_filter_fixture["evaluator_plugin_b"] for s in body["sessions"])


@pytest.mark.anyio
async def test_admin_sessions_filters_by_state(admin_user, evaluation_filter_fixture):
    """Combined with `case_id` since `state` values (active/completed) aren't
    fixture-unique -- plenty of other tests' sessions share them.
    """
    _override_user(admin_user)
    case_id = evaluation_filter_fixture["case"].id
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/v1/admin/sessions", params={"case_id": case_id, "state": "active"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["sessions"][0]["id"] == evaluation_filter_fixture["session_in_review"].id


@pytest.mark.anyio
async def test_admin_sessions_filters_by_evaluator_user_id(admin_user, evaluation_filter_fixture):
    _override_user(admin_user)
    reviewer_b = evaluation_filter_fixture["reviewer_b"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/v1/admin/sessions", params={"evaluator_user_id": reviewer_b.id}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["sessions"][0]["id"] == evaluation_filter_fixture["session_locked"].id


@pytest.mark.anyio
@pytest.mark.parametrize(
    "bucket, expected_fixture_key",
    [
        ("no_runs", "session_no_runs"),
        ("needs_review", "session_needs_review"),
        ("in_review", "session_in_review"),
        ("locked", "session_locked"),
    ],
)
async def test_admin_sessions_filters_by_evaluation_status(
    admin_user, evaluation_filter_fixture, bucket, expected_fixture_key
):
    """Combined with `case_id` since `no_runs` in particular is the default bucket for
    every session anywhere that never got an evaluation run -- not fixture-unique.
    """
    _override_user(admin_user)
    case_id = evaluation_filter_fixture["case"].id
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/v1/admin/sessions",
            params={"case_id": case_id, "evaluation_status": bucket},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["sessions"][0]["id"] == evaluation_filter_fixture[expected_fixture_key].id


@pytest.mark.anyio
async def test_admin_sessions_rejects_invalid_evaluation_status(admin_user):
    _override_user(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/v1/admin/sessions", params={"evaluation_status": "not_a_real_bucket"}
        )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_session_filter_options_includes_this_fixtures_cases_plugins_and_evaluators(
    admin_user, evaluation_filter_fixture
):
    """Asserts containment, not exact list equality -- this module's shared DB means
    other tests contribute their own cases/plugins/evaluators to the same response.
    """
    _override_user(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/admin/sessions/filter-options")
    assert response.status_code == 200
    body = response.json()

    case = evaluation_filter_fixture["case"]
    assert {"id": case.id, "title": case.title} in body["cases"]
    assert evaluation_filter_fixture["patient_plugin_a"] in body["patient_plugins"]
    assert evaluation_filter_fixture["patient_plugin_b"] in body["patient_plugins"]
    assert evaluation_filter_fixture["evaluator_plugin_a"] in body["evaluator_plugins"]
    assert evaluation_filter_fixture["evaluator_plugin_b"] in body["evaluator_plugins"]

    evaluator_ids = {row["id"] for row in body["evaluators"]}
    assert evaluation_filter_fixture["reviewer_a"].id in evaluator_ids
    reviewer_b_row = next(
        row for row in body["evaluators"] if row["id"] == evaluation_filter_fixture["reviewer_b"].id
    )
    assert reviewer_b_row["label"] == "Reviewer B"


@pytest.mark.anyio
async def test_admin_sessions_researcher_can_also_use_filter_options(
    researcher_user, evaluation_filter_fixture
):
    """The filter bar is shared with the researcher-facing Evaluate Sessions tab, so
    filter-options must be readable by researchers too, not just admins.
    """
    _override_user(researcher_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/admin/sessions/filter-options")
    assert response.status_code == 200
