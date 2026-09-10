"""Admin-only API coverage for saved research runs and human review."""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import app
from core.deps import get_current_user, get_db, require_admin
from domain.entities.case import Case
from domain.entities.feedback import Feedback
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
    admin = User(email=f"annotation-admin-{suffix}@test.local", role="admin")
    trainee = User(email=f"annotation-trainee-{suffix}@test.local", role="trainee")
    db_session.add_all([admin, trainee])
    db_session.commit()
    return admin, trainee


@pytest.fixture
def completed_session(db_session, users):
    case = Case(title="Annotation API", script="Synthetic", difficulty_level="test")
    db_session.add(case)
    db_session.commit()
    session = SessionEntity(
        user_id=users[1].id,
        case_id=case.id,
        state="completed",
        duration_seconds=120,
        evaluator_plugin="unchanged-evaluator",
        metrics_json='{"unchanged":true}',
    )
    db_session.add(session)
    db_session.commit()
    db_session.add_all(
        [
            Turn(
                session_id=session.id,
                turn_number=1,
                role="user",
                text="How are you feeling?",
                spikes_stage="perception",
            ),
            Turn(
                session_id=session.id,
                turn_number=2,
                role="assistant",
                text="I feel worried.",
                spans_json=json.dumps(
                    [
                        {
                            "span_type": "eo",
                            "dimension": "Feeling",
                            "explicit_or_implicit": "explicit",
                            "start_char": 7,
                            "end_char": 14,
                            "text": "worried",
                            "confidence": 0.9,
                            "provenance": "rule",
                        }
                    ]
                ),
            ),
            Turn(
                session_id=session.id,
                turn_number=3,
                role="user",
                text="I understand.",
                spans_json=json.dumps(
                    [
                        {
                            "span_type": "response",
                            "type": "understanding",
                            "start_char": 2,
                            "end_char": 12,
                            "text": "understand",
                            "confidence": 0.8,
                            "provenance": "rule",
                        }
                    ]
                ),
            ),
        ]
    )
    db_session.add(
        Feedback(
            session_id=session.id,
            empathy_score=60,
            communication_score=60,
            spikes_completion_score=20,
            overall_score=50,
            strengths="Unchanged learner feedback",
        )
    )
    db_session.commit()
    return session


def _as_admin(user):
    async def override():
        return user

    app.dependency_overrides[require_admin] = override


def _as_trainee(user):
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
async def test_admin_run_save_create_review_conflict_complete_reopen_and_exports(
    users, completed_session, db_session
):
    _as_admin(users[0])
    before = {
        "state": completed_session.state,
        "evaluator_plugin": completed_session.evaluator_plugin,
        "metrics_json": completed_session.metrics_json,
        "turns": [(turn.turn_number, turn.text) for turn in completed_session.turns],
        "feedback": completed_session.feedback.strengths,
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run, created = await _save_and_create(client, completed_session.id)
        run_uuid = run.json()["run_uuid"]
        set_body = created.json()
        set_uuid = set_body["annotation_set_uuid"]
        assert set_body["status"] == "draft"
        assert run.json()["envelope"]["status"] == "success"
        duplicate = await client.post(
            f"/v1/research/evaluation-runs/{run_uuid}/annotation-sets",
            json={
                "guideline_identifier": run.json()["annotation_policy"][
                    "guideline_identifier"
                ],
                "guideline_version": run.json()["annotation_policy"][
                    "guideline_version"
                ],
            },
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["annotation_set_uuid"] == set_uuid

        listed = await client.get(
            f"/v1/research/sessions/{completed_session.id}/evaluation-runs"
        )
        retrieved = await client.get(f"/v1/research/evaluation-runs/{run_uuid}")
        assert listed.status_code == retrieved.status_code == 200
        assert listed.json()[0]["run_uuid"] == run_uuid

        prediction = set_body["eligible_predictions"][0]
        decision_url = (
            f"/v1/research/annotation-sets/{set_uuid}/decisions/"
            f"{prediction['prediction_id']}"
        )
        invalid_correction = await client.put(
            decision_url,
            json={
                "expected_set_revision": 0,
                "decision": "corrected",
                "correction": {
                    "correction_type": "span_annotation",
                    "corrected_label": "unregistered_label",
                    "corrected_dimension": None,
                },
            },
        )
        assert invalid_correction.status_code == 422
        assert invalid_correction.json()["message"]["category"] == "invalid_correction"
        saved = await client.put(
            decision_url,
            json={"expected_set_revision": 0, "decision": "confirmed"},
        )
        assert saved.status_code == 200
        conflict = await client.put(
            decision_url,
            json={"expected_set_revision": 0, "decision": "rejected"},
        )
        assert conflict.status_code == 409
        detail = conflict.json()["message"]
        assert detail["category"] == "revision_conflict"
        assert detail["current_set_revision"] == 1

        blocked = await client.post(
            f"/v1/research/annotation-sets/{set_uuid}/complete",
            json={"expected_set_revision": 1},
        )
        assert blocked.status_code == 409
        assert blocked.json()["message"]["category"] == "completion_blocked"

        current = saved.json()
        for item in set_body["eligible_predictions"][1:]:
            response = await client.put(
                f"/v1/research/annotation-sets/{set_uuid}/decisions/{item['prediction_id']}",
                json={
                    "expected_set_revision": current["revision"],
                    "decision": "confirmed",
                },
            )
            assert response.status_code == 200, response.text
            current = response.json()
        complete = await client.post(
            f"/v1/research/annotation-sets/{set_uuid}/complete",
            json={"expected_set_revision": current["revision"]},
        )
        assert complete.status_code == 200, complete.text
        assert complete.json()["locked"] is True
        locked = await client.put(
            decision_url,
            json={
                "expected_set_revision": complete.json()["revision"],
                "expected_decision_revision": 1,
                "decision": "rejected",
            },
        )
        assert locked.status_code == 409

        reopened = await client.post(
            f"/v1/research/annotation-sets/{set_uuid}/reopen",
            json={
                "expected_set_revision": complete.json()["revision"],
                "reason": "Documented expert second pass.",
            },
        )
        assert reopened.status_code == 200
        assert reopened.json()["status"] == "in_review"
        assert reopened.json()["transitions"][-1]["reason"].startswith("Documented")

        for profile in ("full_review", "resolved_projection", "audit_history"):
            exported = await client.post(
                f"/v1/research/annotation-sets/{set_uuid}/exports",
                json={"profile": profile, "include_transcript_content": False},
            )
            assert exported.status_code == 200, exported.text
            assert exported.headers["content-type"].startswith("application/json")
            assert users[0].email not in exported.text
            assert "I feel worried." not in exported.text
            assert "complete gold-standard" in exported.text

    db_session.expire_all()
    after_session = db_session.get(SessionEntity, completed_session.id)
    after = {
        "state": after_session.state,
        "evaluator_plugin": after_session.evaluator_plugin,
        "metrics_json": after_session.metrics_json,
        "turns": [(turn.turn_number, turn.text) for turn in after_session.turns],
        "feedback": after_session.feedback.strengths,
    }
    assert after == before


@pytest.mark.anyio
async def test_annotation_routes_reject_trainee_and_unauthenticated(users, completed_session):
    transport = ASGITransport(app=app)
    _as_admin(users[0])
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run, annotation_set = await _save_and_create(client, completed_session.id)
        app.dependency_overrides.pop(require_admin, None)
        _as_trainee(users[1])
        trainee = await client.post(
            f"/v1/research/sessions/{completed_session.id}/evaluation-runs",
            json={"evaluator_identifier": "baseline"},
        )
        trainee_run_read = await client.get(
            f"/v1/research/evaluation-runs/{run.json()['run_uuid']}"
        )
        trainee_set_read = await client.get(
            f"/v1/research/annotation-sets/{annotation_set.json()['annotation_set_uuid']}"
        )
    assert trainee.status_code == 403
    assert trainee_run_read.status_code == 403
    assert trainee_set_read.status_code == 403

    app.dependency_overrides.pop(get_current_user, None)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unauthenticated = await client.get(
            f"/v1/research/sessions/{completed_session.id}/evaluation-runs"
        )
    assert unauthenticated.status_code == 403


@pytest.mark.anyio
async def test_save_rejects_incomplete_and_live_refusal(users, completed_session, db_session):
    _as_admin(users[0])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        completed_session.state = "active"
        db_session.commit()
        incomplete = await client.post(
            f"/v1/research/sessions/{completed_session.id}/evaluation-runs",
            json={"evaluator_identifier": "baseline"},
        )
        completed_session.state = "completed"
        db_session.commit()
        refused = await client.post(
            f"/v1/research/sessions/{completed_session.id}/evaluation-runs",
            json={"evaluator_identifier": "hybrid_v1", "allow_live": False},
        )
    assert incomplete.status_code == 409
    assert refused.status_code == 409
    assert refused.json()["message"]["category"] == "live_execution_refused"
