"""Tests for GET /admin/plugin-registry (plugin discovery)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.deps import require_admin


@pytest.fixture(autouse=True)
def _overrides():
    """Override admin auth; endpoint does not use DB."""
    dummy_admin = SimpleNamespace(
        id=1, email="admin@test.local", full_name="Test Admin", role="admin"
    )

    async def _as_admin():
        return dummy_admin

    app.dependency_overrides[require_admin] = _as_admin

    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_plugin_registry_returns_evaluators():
    """GET /admin/plugin-registry returns evaluators with name and version."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/v1/admin/plugin-registry")
    assert r.status_code == 200
    data = r.json()
    assert "evaluators" in data
    assert "patient_models" in data
    assert "metrics" in data
    assert isinstance(data["evaluators"], list)
    assert isinstance(data["patient_models"], list)
    assert isinstance(data["metrics"], list)


@pytest.mark.asyncio
async def test_plugin_registry_evaluators_have_version():
    """Each evaluator entry has name and version."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/v1/admin/plugin-registry")
    assert r.status_code == 200
    data = r.json()
    for entry in data["evaluators"]:
        assert "name" in entry
        assert "version" in entry
        assert isinstance(entry["name"], str)
        assert isinstance(entry["version"], str)

    ace_ct = next(
        entry
        for entry in data["evaluators"]
        if entry["name"].endswith(":ACECTInspiredRubricEvaluator")
    )
    assert ace_ct["version"] == "0.1.0-experimental"


@pytest.mark.asyncio
async def test_plugin_registry_response_format():
    """Response shape matches PluginDiscoveryResponse."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/v1/admin/plugin-registry")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"evaluators", "patient_models", "metrics"}
    for key in data:
        for item in data[key]:
            assert set(item.keys()) == {"name", "version"}
