"""API coverage for the bulk Sessions-list evaluation-status endpoint.

@remarks
Backs the Research Sessions-list status chip (Needs review / In review / Locked / No
runs yet). Verifies gating (admin + researcher allowed, trainee forbidden) and the
per-session summary for a few fixture scenarios: no runs, a saved run with no
annotation set yet, a draft annotation set, and a completed (locked) annotation set.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import app
from core.deps import get_current_user, get_db, require_admin, require_admin_or_researcher
from domain.entities.case import Case
from domain.entities.session import Session as SessionEntity
from domain.entities.turn import Turn
from domain.entities.user import User
from tests.utils.transcript_runner import create_all_for_test_engine

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
create_all_for_test_engine(_engine)


def _get_test_db():
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides.pop(require_admin_or_researcher, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def db_session():
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def users(db_session):
    suffix = uuid.uuid4().hex[:10]
    admin = User(email=f"status-admin-{suffix}@test.local", role="admin")
    trainee = User(email=f"status-trainee-{suffix}@test.local", role="trainee")
    researcher = User(email=f"status-researcher-{suffix}@test.local", role="researcher")
    db_session.add_all([admin, trainee, researcher])
    db_session.commit()
    return admin, trainee, researcher


def _make_completed_session(db_session, users, title):
    case = Case(title=title, script="Synthetic", difficulty_level="test")
    db_session.add(case)
    db_session.commit()
    session = SessionEntity(
        user_id=users[1].id,
        case_id=case.id,
        state="completed",
        duration_seconds=60,
        evaluator_plugin="unchanged-evaluator",
        metrics_json='{"unchanged":true}',
    )
    db_session.add(session)
    db_session.commit()
    db_session.add_all(
        [
            Turn(session_id=session.id, turn_number=1, role="user", text="How are you feeling?"),
            Turn(
                session_id=session.id,
                turn_number=2,
                role="assistant",
                text="I feel worried.",
                spans_json="[]",
            ),
        ]
    )
    db_session.commit()
    return session


@pytest.fixture
def sessions(db_session, users):
    return {
        "no_runs": _make_completed_session(db_session, users, "Status: no runs"),
        "run_no_set": _make_completed_session(db_session, users, "Status: run, no set"),
        "draft_set": _make_completed_session(db_session, users, "Status: draft set"),
        "locked_set": _make_completed_session(db_session, users, "Status: locked set"),
    }


def _as(user):
    async def override():
        return user

    app.dependency_overrides[get_current_user] = override


async def _save_and_create(client, session_id):
    run = await client.post(
        f"/v1/research/sessions/{session_id}/evaluation-runs",
        json={"evaluator_identifier": "baseline", "allow_live": False},
    )
    assert run.status_code == 200, run.text
    policy = run.json()["annotation_policy"]
    annotation_set = await client.post(
        f"/v1/research/evaluation-runs/{run.json()['run_uuid']}/annotation-sets",
        json={
            "guideline_identifier": policy["guideline_identifier"],
            "guideline_version": policy["guideline_version"],
        },
    )
    assert annotation_set.status_code == 200, annotation_set.text
    return run, annotation_set


@pytest.mark.anyio
async def test_evaluation_status_reflects_each_session_scenario(users, sessions):
    _as(users[0])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # run_no_set: save a run but never create an annotation set.
        run = await client.post(
            f"/v1/research/sessions/{sessions['run_no_set'].id}/evaluation-runs",
            json={"evaluator_identifier": "baseline", "allow_live": False},
        )
        assert run.status_code == 200, run.text

        # draft_set: save a run and create (but do not complete) an annotation set.
        _run, created = await _save_and_create(client, sessions["draft_set"].id)

        # locked_set: save a run, create an annotation set, confirm every prediction,
        # and complete it so it is locked.
        run2, created2 = await _save_and_create(client, sessions["locked_set"].id)
        set_body = created2.json()
        set_uuid = set_body["annotation_set_uuid"]
        current_revision = set_body["revision"]
        for prediction in set_body["eligible_predictions"]:
            response = await client.put(
                f"/v1/research/annotation-sets/{set_uuid}/decisions/{prediction['prediction_id']}",
                json={"expected_set_revision": current_revision, "decision": "confirmed"},
            )
            assert response.status_code == 200, response.text
            current_revision = response.json()["revision"]
        complete = await client.post(
            f"/v1/research/annotation-sets/{set_uuid}/complete",
            json={"expected_set_revision": current_revision},
        )
        assert complete.status_code == 200, complete.text
        assert complete.json()["locked"] is True

        ids = ",".join(str(sessions[key].id) for key in sessions)
        result = await client.get(f"/v1/research/sessions/evaluation-status?session_ids={ids}")
        assert result.status_code == 200, result.text
        by_id = {row["session_id"]: row for row in result.json()["statuses"]}

        no_runs = by_id[sessions["no_runs"].id]
        assert no_runs["has_saved_runs"] is False
        assert no_runs["latest_annotation_set_status"] is None
        assert no_runs["latest_annotation_set_locked"] is None

        run_no_set = by_id[sessions["run_no_set"].id]
        assert run_no_set["has_saved_runs"] is True
        assert run_no_set["latest_annotation_set_status"] is None

        draft = by_id[sessions["draft_set"].id]
        assert draft["has_saved_runs"] is True
        assert draft["latest_annotation_set_status"] == "draft"
        assert draft["latest_annotation_set_locked"] is False

        locked = by_id[sessions["locked_set"].id]
        assert locked["has_saved_runs"] is True
        assert locked["latest_annotation_set_status"] == "complete"
        assert locked["latest_annotation_set_locked"] is True


@pytest.mark.anyio
async def test_evaluation_status_allows_researcher_and_forbids_trainee(users, sessions):
    transport = ASGITransport(app=app)
    session_id = sessions["no_runs"].id

    _as(users[2])  # researcher
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        allowed = await client.get(
            f"/v1/research/sessions/evaluation-status?session_ids={session_id}"
        )
    assert allowed.status_code == 200, allowed.text

    _as(users[1])  # trainee
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        forbidden = await client.get(
            f"/v1/research/sessions/evaluation-status?session_ids={session_id}"
        )
    assert forbidden.status_code == 403


@pytest.mark.anyio
async def test_evaluation_status_rejects_oversized_batch(users, sessions):
    _as(users[0])
    transport = ASGITransport(app=app)
    too_many = ",".join(str(n) for n in range(1, 202))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/v1/research/sessions/evaluation-status?session_ids={too_many}"
        )
    assert response.status_code == 422
