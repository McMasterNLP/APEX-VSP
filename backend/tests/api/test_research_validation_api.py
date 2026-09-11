"""API coverage for Item 3A validation-run creation, retrieval, and export.

@remarks
Reuses the `test_research_annotation_api.py` fixture conventions (in-memory
SQLite, dependency overrides, `_save_and_create`) rather than inventing new
scaffolding. The hand-computed precision/recall/F1 fixture lives in
`tests/services/test_research_validation_metrics.py`, which isolates the
matching/metric engine itself; this file instead exercises the full
create -> complete -> validate -> read -> export flow and its rejection paths
(transcript mismatch, incomplete annotation set, ineligible metrics never
carrying a number).
"""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import app
from core.deps import get_current_user, get_db, require_admin, require_admin_or_researcher
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
def admin(db_session):
    suffix = uuid.uuid4().hex[:10]
    user = User(email=f"validation-admin-{suffix}@test.local", role="admin")
    db_session.add(user)
    db_session.commit()
    return user


def _as_admin(user):
    async def override():
        return user

    app.dependency_overrides[get_current_user] = override


def _make_completed_session(db_session, admin, *, feeling_word: str = "worried"):
    patient_text = f"I feel {feeling_word}."
    case = Case(title="Validation API", script="Synthetic", difficulty_level="test")
    db_session.add(case)
    db_session.commit()
    session = SessionEntity(
        user_id=admin.id,
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
                text=patient_text,
                spans_json=json.dumps(
                    [
                        {
                            "span_type": "eo",
                            "dimension": "Feeling",
                            "explicit_or_implicit": "explicit",
                            "start_char": 7,
                            "end_char": 7 + len(feeling_word),
                            "text": feeling_word,
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


async def _confirm_all_and_complete(client, annotation_set_json, *, coverage: str = "exhaustive"):
    current = annotation_set_json
    set_uuid = current["annotation_set_uuid"]
    for item in current["eligible_predictions"]:
        response = await client.put(
            f"/v1/research/annotation-sets/{set_uuid}/decisions/{item['prediction_id']}",
            json={"expected_set_revision": current["revision"], "decision": "confirmed"},
        )
        assert response.status_code == 200, response.text
        current = response.json()
    covered = await client.post(
        f"/v1/research/annotation-sets/{set_uuid}/coverage",
        json={"expected_set_revision": current["revision"], "coverage": coverage},
    )
    assert covered.status_code == 200, covered.text
    current = covered.json()
    complete = await client.post(
        f"/v1/research/annotation-sets/{set_uuid}/complete",
        json={"expected_set_revision": current["revision"]},
    )
    assert complete.status_code == 200, complete.text
    return complete.json()


@pytest.mark.anyio
async def test_create_read_and_reexport_validation_run_with_exhaustive_coverage(
    admin, db_session
):
    _as_admin(admin)
    session = _make_completed_session(db_session, admin)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run, created = await _save_and_create(client, session.id)
        completed = await _confirm_all_and_complete(client, created.json())

        create_response = await client.post(
            "/v1/research/validation-runs",
            json={
                "evaluation_run_uuid": run.json()["run_uuid"],
                "annotation_set_uuid": completed["annotation_set_uuid"],
            },
        )
        assert create_response.status_code == 200, create_response.text
        validation_run = create_response.json()
        assert validation_run["coverage_level"] == "exhaustive"
        assert validation_run["matching_policy_identifier"] == "exact_span_match"
        assert (
            validation_run["evaluation_run_uuid"] == run.json()["run_uuid"]
        )
        assert (
            validation_run["annotation_set_revision_at_validation"] == completed["revision"]
        )

        # Every eligible prediction was confirmed unmodified, so the evaluator's own
        # projection is identical to the resolved reference: every scored label is a
        # perfect match (no FP/FN) under exact-span-match.
        span_classification = validation_run["results"]["span_classification"]
        assert span_classification["matching_policy_identifier"] == "exact_span_match"
        for label_metric in span_classification["per_label"]:
            assert label_metric["false_positives"] == 0
            assert label_metric["false_negatives"] == 0
            if label_metric["support"] > 0:
                assert label_metric["precision"]["value"] == "1"
                assert label_metric["recall"]["value"] == "1"
                assert label_metric["f1"]["value"] == "1"
        assert span_classification["micro"]["false_positives"] == 0
        assert span_classification["micro"]["false_negatives"] == 0
        assert span_classification["micro"]["precision"]["value"] == "1"

        get_response = await client.get(
            f"/v1/research/validation-runs/{validation_run['validation_run_uuid']}"
        )
        assert get_response.status_code == 200
        assert get_response.json() == validation_run

        # Re-running validation-run creation with identical inputs must produce a
        # byte-identical *result payload* (a fresh row/id is fine and expected).
        second_response = await client.post(
            "/v1/research/validation-runs",
            json={
                "evaluation_run_uuid": run.json()["run_uuid"],
                "annotation_set_uuid": completed["annotation_set_uuid"],
            },
        )
        assert second_response.status_code == 200
        second = second_response.json()
        assert second["validation_run_uuid"] != validation_run["validation_run_uuid"]
        assert second["results"] == validation_run["results"]
        assert second["warnings"] == validation_run["warnings"]

        exported = await client.post(
            f"/v1/research/validation-runs/{validation_run['validation_run_uuid']}/exports",
            json={"profile": "full", "include_transcript_content": False},
        )
        assert exported.status_code == 200, exported.text
        assert exported.headers["content-type"].startswith("application/json")
        assert admin.email not in exported.text


@pytest.mark.anyio
async def test_ineligible_metric_never_carries_a_number_under_prediction_review_only(
    admin, db_session
):
    _as_admin(admin)
    session = _make_completed_session(db_session, admin)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run, created = await _save_and_create(client, session.id)
        completed = await _confirm_all_and_complete(
            client, created.json(), coverage="prediction_review_only"
        )

        response = await client.post(
            "/v1/research/validation-runs",
            json={
                "evaluation_run_uuid": run.json()["run_uuid"],
                "annotation_set_uuid": completed["annotation_set_uuid"],
            },
        )
        assert response.status_code == 200, response.text
        results = response.json()["results"]
        assert "span_recall" in results["eligibility"]["ineligible_metric_identifiers"]
        assert "span_f1" in results["eligibility"]["ineligible_metric_identifiers"]
        assert "span_precision" in results["eligibility"]["eligible_metric_identifiers"]

        span_classification = results["span_classification"]
        for label_metric in span_classification["per_label"]:
            assert label_metric["recall"]["status"] == "ineligible"
            assert label_metric["recall"]["value"] is None
            assert label_metric["f1"]["status"] == "ineligible"
            assert label_metric["f1"]["value"] is None
        assert span_classification["micro"]["recall"]["value"] is None
        assert span_classification["macro"]["f1"]["value"] is None
        # Precision remains eligible under prediction_review_only.
        assert span_classification["micro"]["precision"]["status"] == "computed"


@pytest.mark.anyio
async def test_validation_rejects_incomplete_annotation_set(admin, db_session):
    _as_admin(admin)
    session = _make_completed_session(db_session, admin)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run, created = await _save_and_create(client, session.id)

        response = await client.post(
            "/v1/research/validation-runs",
            json={
                "evaluation_run_uuid": run.json()["run_uuid"],
                "annotation_set_uuid": created.json()["annotation_set_uuid"],
            },
        )
        assert response.status_code == 409
        assert response.json()["message"]["category"] == "annotation_set_not_complete"


@pytest.mark.anyio
async def test_validation_rejects_transcript_hash_mismatch(admin, db_session):
    _as_admin(admin)
    session_a = _make_completed_session(db_session, admin, feeling_word="worried")
    session_b = _make_completed_session(db_session, admin, feeling_word="anxious")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_a, created_a = await _save_and_create(client, session_a.id)
        await _confirm_all_and_complete(client, created_a.json())
        run_b, created_b = await _save_and_create(client, session_b.id)
        completed_b = await _confirm_all_and_complete(client, created_b.json())

        assert (
            run_a.json()["envelope"]["transcript"]["canonical_transcript_hash"]
            != run_b.json()["envelope"]["transcript"]["canonical_transcript_hash"]
        )

        response = await client.post(
            "/v1/research/validation-runs",
            json={
                "evaluation_run_uuid": run_a.json()["run_uuid"],
                "annotation_set_uuid": completed_b["annotation_set_uuid"],
            },
        )
        assert response.status_code == 409
        assert response.json()["message"]["category"] == "transcript_mismatch"


@pytest.mark.anyio
async def test_validation_run_not_found_and_unknown_policy(admin, db_session):
    _as_admin(admin)
    session = _make_completed_session(db_session, admin)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run, created = await _save_and_create(client, session.id)
        completed = await _confirm_all_and_complete(client, created.json())

        missing = await client.get(
            "/v1/research/validation-runs/00000000-0000-0000-0000-000000000000"
        )
        assert missing.status_code == 404

        unknown_policy = await client.post(
            "/v1/research/validation-runs",
            json={
                "evaluation_run_uuid": run.json()["run_uuid"],
                "annotation_set_uuid": completed["annotation_set_uuid"],
                "matching_policy_identifier": "fuzzy_overlap_match",
            },
        )
        assert unknown_policy.status_code == 422
        assert unknown_policy.json()["message"]["category"] == "unknown_matching_policy"
