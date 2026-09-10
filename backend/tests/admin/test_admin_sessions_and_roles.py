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
