"""Integration tests for research API endpoints (admin-only).

Verification of:
  GET /v1/research/sessions          -- pagination, response envelope shape
  GET /v1/research/sessions/{id}     -- 200 valid, 404 unknown
  GET /v1/research/export            -- JSON attachment download
  GET /v1/research/export.csv        -- CSV text/csv content-type
  GET /v1/research/export/metrics.csv       -- streaming CSV
  GET /v1/research/export/transcripts.csv   -- streaming CSV
  GET /v1/research/export/session/{id}.csv  -- 200 valid, 404 unknown
  Admin enforcement: all endpoints return 403 for trainee users
  Research evaluation descriptors, non-persisting POST runs, and POST exports
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
from core.deps import get_current_user, get_db, require_admin
from domain.entities.case import Case
from domain.entities.feedback import Feedback
from domain.entities.session import Session as SessionEntity
from domain.entities.turn import Turn
from domain.entities.user import User
from services.research_service import generate_anon_session_id
from tests.utils.transcript_runner import create_all_for_test_engine

TEST_SALT = "research-anon-salt-change-in-production"

# ---------------------------------------------------------------------------
# Module-level shared in-memory database
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _override_db():
    """Wire the FastAPI app to the in-memory SQLite DB for all tests."""
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
def admin_user(db_session):
    user = User(
        email=f"research_admin_{uuid.uuid4().hex[:12]}@test.com",
        role="admin",
        full_name="Research Admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def trainee_user(db_session):
    user = User(
        email=f"research_trainee_{uuid.uuid4().hex[:12]}@test.com",
        role="trainee",
        full_name="Test Trainee",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_case(db_session):
    case = Case(title="Research API Case", script="Script", difficulty_level="intermediate")
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


@pytest.fixture
def seeded_session(db_session, admin_user, test_case):
    """A completed session with feedback and 3 turns."""
    session = SessionEntity(
        user_id=admin_user.id,
        case_id=test_case.id,
        state="completed",
        duration_seconds=200,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    db_session.add(
        Feedback(
            session_id=session.id,
            empathy_score=70.0,
            communication_score=65.0,
            spikes_completion_score=50.0,
            overall_score=63.0,
        )
    )
    for i, (role, text) in enumerate(
        [("user", "Hello doctor."), ("assistant", "Hello patient."), ("user", "Thank you.")],
        start=1,
    ):
        db_session.add(Turn(session_id=session.id, turn_number=i, role=role, text=text))
    db_session.commit()
    return session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _override_admin(user: User):
    async def _fake_admin():
        return user

    app.dependency_overrides[require_admin] = _fake_admin


def _override_trainee(user: User):
    """Override get_current_user so require_role('admin') can reject the user."""

    async def _fake_user():
        return user

    app.dependency_overrides[get_current_user] = _fake_user


# ---------------------------------------------------------------------------
# Capability-driven research evaluations
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_research_evaluator_descriptors_are_admin_only_and_typed(admin_user):
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/evaluators")
    assert response.status_code == 200
    body = response.json()
    by_id = {item["identifier"]: item for item in body["evaluators"]}
    assert set(by_id) == {"baseline", "hybrid_v1", "hybrid_v2", "ace_ct_inspired"}
    assert by_id["baseline"]["capabilities"]["outputs"]["character_spans"] is True
    assert by_id["ace_ct_inspired"]["capabilities"]["outputs"]["dimension_ratings"] is True
    baseline_operations = by_id["baseline"]["capabilities"]["annotation_operations"]
    assert baseline_operations["confirm"] is True
    assert baseline_operations["reject"] is True
    assert baseline_operations["adjust_span"] is False
    assert baseline_operations["add_annotation"] is False
    rating_operations = by_id["ace_ct_inspired"]["capabilities"][
        "annotation_by_projection"
    ]["dimension_rating"]
    assert rating_operations["change_rating"] is True
    assert rating_operations["mark_insufficient_evidence"] is True


@pytest.mark.anyio
async def test_research_evaluator_descriptors_reject_trainee(trainee_user):
    _override_trainee(trainee_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/evaluators")
    assert response.status_code == 403


@pytest.mark.anyio
async def test_research_evaluator_descriptors_reject_unauthenticated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/evaluators")
    assert response.status_code == 403


@pytest.mark.anyio
async def test_research_baseline_evaluation_succeeds_without_persistence(
    admin_user, seeded_session, db_session
):
    _override_admin(admin_user)
    before_feedback = dict(
        db_session.execute(
            Feedback.__table__.select().where(Feedback.session_id == seeded_session.id)
        )
        .mappings()
        .one()
    )
    before_turn_count = (
        db_session.query(Turn).filter(Turn.session_id == seeded_session.id).count()
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/v1/research/sessions/{seeded_session.id}/evaluations",
            json={"evaluator_identifiers": ["baseline"], "allow_live": False},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["results"][0]["status"] == "success"
    assert body["results"][0]["framework_result"]["native_type"] == "apex_feedback"
    assert body["transcript"]["raw_transcript_included"] is True
    assert body["results"][0]["transcript"]["raw_transcript_included"] is False

    db_session.expire_all()
    after_feedback = dict(
        db_session.execute(
            Feedback.__table__.select().where(Feedback.session_id == seeded_session.id)
        )
        .mappings()
        .one()
    )
    assert after_feedback == before_feedback
    assert db_session.query(Turn).filter(Turn.session_id == seeded_session.id).count() == before_turn_count


@pytest.mark.anyio
async def test_research_evaluation_allows_admin_cross_session_access(
    admin_user, trainee_user, test_case, db_session
):
    session = SessionEntity(
        user_id=trainee_user.id,
        case_id=test_case.id,
        state="completed",
        duration_seconds=1,
    )
    db_session.add(session)
    db_session.commit()
    db_session.add(
        Turn(session_id=session.id, turn_number=1, role="user", text="Hello.")
    )
    db_session.commit()
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/v1/research/sessions/{session.id}/evaluations",
            json={"evaluator_identifiers": ["baseline"]},
        )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_research_evaluation_rejects_trainee(trainee_user, seeded_session):
    _override_trainee(trainee_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/v1/research/sessions/{seeded_session.id}/evaluations",
            json={"evaluator_identifiers": ["baseline"]},
        )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_research_evaluation_rejects_unauthenticated(seeded_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/v1/research/sessions/{seeded_session.id}/evaluations",
            json={"evaluator_identifiers": ["baseline"]},
        )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_research_evaluation_missing_incomplete_and_invalid_evaluator(
    admin_user, test_case, db_session
):
    incomplete = SessionEntity(
        user_id=admin_user.id,
        case_id=test_case.id,
        state="active",
        duration_seconds=0,
    )
    db_session.add(incomplete)
    db_session.commit()
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        missing = await ac.post(
            "/v1/research/sessions/999999/evaluations",
            json={"evaluator_identifiers": ["baseline"]},
        )
        not_complete = await ac.post(
            f"/v1/research/sessions/{incomplete.id}/evaluations",
            json={"evaluator_identifiers": ["baseline"]},
        )
        invalid = await ac.post(
            f"/v1/research/sessions/{incomplete.id}/evaluations",
            json={"evaluator_identifiers": ["uploaded-evaluator"]},
        )
    assert missing.status_code == 404
    assert not_complete.status_code == 409
    # Session-state checks intentionally precede evaluator execution/lookup.
    assert invalid.status_code == 409


@pytest.mark.anyio
async def test_research_evaluation_invalid_evaluator_on_completed_session(
    admin_user, seeded_session
):
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/v1/research/sessions/{seeded_session.id}/evaluations",
            json={"evaluator_identifiers": ["uploaded-evaluator"]},
        )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_research_evaluation_live_refusal_keeps_baseline_success(
    admin_user, seeded_session
):
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/v1/research/sessions/{seeded_session.id}/evaluations",
            json={
                "evaluator_identifiers": ["baseline", "hybrid_v1"],
                "allow_live": False,
            },
        )
    assert response.status_code == 200
    assert [item["status"] for item in response.json()["results"]] == [
        "success",
        "refused",
    ]
    assert response.json()["results"][1]["error"]["category"] == "live_execution_refused"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("profile", "content_type"),
    [
        ("full", "application/json"),
        ("framework_native", "application/json"),
        ("projection", "application/json"),
        ("tabular", "application/zip"),
    ],
)
async def test_research_evaluation_exports(
    profile, content_type, admin_user, seeded_session
):
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        run = await ac.post(
            f"/v1/research/sessions/{seeded_session.id}/evaluations",
            json={"evaluator_identifiers": ["baseline"]},
        )
        response = await ac.post(
            f"/v1/research/sessions/{seeded_session.id}/evaluation-exports",
            json={
                "profile": profile,
                "envelopes": run.json()["results"],
                "include_transcript_content": False,
            },
        )
    assert run.status_code == 200
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(content_type)
    assert "attachment" in response.headers["content-disposition"]


@pytest.mark.anyio
async def test_research_export_rejects_transcript_hash_mismatch(admin_user, seeded_session):
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        run = await ac.post(
            f"/v1/research/sessions/{seeded_session.id}/evaluations",
            json={"evaluator_identifiers": ["baseline"]},
        )
        envelope = run.json()["results"][0]
        envelope["transcript"]["canonical_transcript_hash"] = "0" * 64
        response = await ac.post(
            f"/v1/research/sessions/{seeded_session.id}/evaluation-exports",
            json={"profile": "full", "envelopes": [envelope]},
        )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /v1/research/sessions
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_research_sessions_returns_envelope(admin_user, seeded_session):
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/sessions")

    assert response.status_code == 200
    body = response.json()
    assert "sessions" in body
    assert "total" in body
    assert "skip" in body
    assert "limit" in body
    assert isinstance(body["sessions"], list)


@pytest.mark.anyio
async def test_research_sessions_pagination_skip_limit(admin_user, seeded_session):
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/sessions?skip=0&limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["skip"] == 0
    assert body["limit"] == 10


@pytest.mark.anyio
async def test_research_sessions_invalid_limit_rejected(admin_user):
    """limit=0 violates ge=1 constraint -> 422 Unprocessable Entity."""
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/sessions?limit=0")

    assert response.status_code == 422


@pytest.mark.anyio
async def test_research_sessions_limit_exceeding_max_rejected(admin_user):
    """limit=501 violates le=500 constraint -> 422."""
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/sessions?limit=501")

    assert response.status_code == 422


@pytest.mark.anyio
async def test_research_sessions_anon_ids_in_response(admin_user, seeded_session):
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/sessions")

    body = response.json()
    for s in body["sessions"]:
        assert str(s["session_id"]).startswith("anon_"), (
            f"Expected anon_ prefix, got {s['session_id']!r}"
        )


@pytest.mark.anyio
async def test_research_sessions_403_for_trainee(trainee_user):
    _override_trainee(trainee_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/sessions")

    assert response.status_code == 403


@pytest.mark.anyio
async def test_research_sessions_403_without_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/sessions")

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /v1/research/sessions/{anon_session_id}
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_research_session_detail_200(admin_user, seeded_session):
    anon_id = generate_anon_session_id(seeded_session.id)
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/v1/research/sessions/{anon_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == seeded_session.case_id


@pytest.mark.anyio
async def test_research_session_detail_404_for_unknown(admin_user):
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/sessions/anon_000000000000")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_research_session_detail_403_for_trainee(trainee_user, seeded_session):
    anon_id = generate_anon_session_id(seeded_session.id)
    _override_trainee(trainee_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/v1/research/sessions/{anon_id}")

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /v1/research/export
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_research_export_json_200(admin_user, seeded_session):
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers.get("content-disposition", "")
    assert "research_export.json" in response.headers.get("content-disposition", "")
    data = json.loads(response.content)
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_research_export_json_403_for_trainee(trainee_user):
    _override_trainee(trainee_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/export")

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /v1/research/export.csv
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_research_export_csv_200(admin_user, seeded_session):
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/export.csv")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]


@pytest.mark.anyio
async def test_research_export_csv_403_for_trainee(trainee_user):
    _override_trainee(trainee_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/export.csv")

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /v1/research/export/metrics.csv
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_research_metrics_csv_200(admin_user, seeded_session):
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/export/metrics.csv")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    content = response.text
    assert "anon_session_id" in content
    assert "empathy_score" in content


@pytest.mark.anyio
async def test_research_metrics_csv_403_for_trainee(trainee_user):
    _override_trainee(trainee_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/export/metrics.csv")

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /v1/research/export/transcripts.csv
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_research_transcripts_csv_200(admin_user, seeded_session):
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/export/transcripts.csv")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    content = response.text
    assert "anon_session_id" in content
    assert "speaker" in content


@pytest.mark.anyio
async def test_research_transcripts_csv_403_for_trainee(trainee_user):
    _override_trainee(trainee_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/export/transcripts.csv")

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /v1/research/export/session/{anon_session_id}.csv
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_research_session_transcript_csv_200(admin_user, seeded_session):
    anon_id = generate_anon_session_id(seeded_session.id)
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/v1/research/export/session/{anon_id}.csv")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    # Filename in Content-Disposition contains a sanitised version of the anon ID
    disposition = response.headers.get("content-disposition", "")
    assert "session_" in disposition
    assert ".csv" in disposition


@pytest.mark.anyio
async def test_research_session_transcript_csv_404_for_unknown(admin_user):
    _override_admin(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/research/export/session/anon_000000000000.csv")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_research_session_transcript_csv_403_for_trainee(trainee_user, seeded_session):
    anon_id = generate_anon_session_id(seeded_session.id)
    _override_trainee(trainee_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/v1/research/export/session/{anon_id}.csv")

    assert response.status_code == 403
