"""Integration tests for session management + CRD flow.

Runs hook context builders and the real CRD stub app in-process (via
ASGITransport) against a temporary SQLite database. Only `fetch_resource`
(which would otherwise hit a live HAPI FHIR server for prefetch resources)
is monkeypatched.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.api import db as api_db
from src.api.main import app
from src.payer.cds_hooks_server import app as cds_app

BASE = "http://test"

_FAKE_PATIENT = {"resourceType": "Patient", "id": "test-patient-001"}
_FAKE_COVERAGE = {
    "resourceType": "Bundle",
    "type": "searchset",
    "entry": [{"resource": {"resourceType": "Coverage", "id": "test-coverage-001"}}],
}


async def _fake_fetch_resource(fhir_base_url: str, relative_url: str) -> dict:
    if relative_url.startswith("Patient"):
        return _FAKE_PATIENT
    return _FAKE_COVERAGE


@pytest.fixture(autouse=True)
async def _isolated_db(tmp_path):
    await api_db.init_db(str(tmp_path / "test-sessions.db"))


@pytest.fixture(autouse=True)
def _patch_fetch_resource(monkeypatch):
    monkeypatch.setattr("src.hooks.base.fetch_resource", _fake_fetch_resource)


@pytest.fixture(autouse=True)
def _patch_cds_transport(monkeypatch):
    def _client_factory(*args, **kwargs):
        return AsyncClient(transport=ASGITransport(app=cds_app), base_url="http://cds-stub")

    monkeypatch.setattr("src.api.services.crd_service.httpx.AsyncClient", _client_factory)


@pytest.fixture
def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE)


# ── POST /api/sessions ───────────────────────────────────────────────────────

async def test_create_session_pa_required(client: AsyncClient) -> None:
    async with client as c:
        resp = await c.post(
            "/api/sessions", json={"hook": "order-sign", "scenario_key": "pa-required"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["session"]["status"] == "crd_complete"
    assert body["session"]["hook"] == "order-sign"
    assert body["crd_result"]["pa_needed"] is True
    assert body["crd_result"]["smart_url"] is not None
    assert len(body["crd_result"]["cards"]) == 2


async def test_create_session_pa_not_required(client: AsyncClient) -> None:
    async with client as c:
        resp = await c.post(
            "/api/sessions", json={"hook": "order-sign", "scenario_key": "pa-not-required"}
        )
    body = resp.json()
    assert body["crd_result"]["pa_needed"] is False
    assert body["crd_result"]["smart_url"] is None
    assert len(body["crd_result"]["cards"]) == 1


async def test_create_session_auth_pending(client: AsyncClient) -> None:
    async with client as c:
        resp = await c.post(
            "/api/sessions", json={"hook": "appointment-book", "scenario_key": "auth-pending"}
        )
    body = resp.json()
    assert body["crd_result"]["pa_needed"] is True
    assert len(body["crd_result"]["cards"]) == 2


async def test_create_session_invalid_hook_returns_422(client: AsyncClient) -> None:
    async with client as c:
        resp = await c.post(
            "/api/sessions", json={"hook": "not-a-hook", "scenario_key": "pa-required"}
        )
    assert resp.status_code == 422


# ── GET /api/sessions ────────────────────────────────────────────────────────

async def test_list_sessions_after_create(client: AsyncClient) -> None:
    async with client as c:
        await c.post("/api/sessions", json={"hook": "order-sign", "scenario_key": "pa-required"})
        resp = await c.get("/api/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["hook"] == "order-sign"
    assert body[0]["disposition"] is None


# ── GET /api/sessions/{id} ───────────────────────────────────────────────────

async def test_get_session_detail(client: AsyncClient) -> None:
    async with client as c:
        create_resp = await c.post(
            "/api/sessions", json={"hook": "order-sign", "scenario_key": "pa-required"}
        )
        session_id = create_resp.json()["session"]["id"]
        resp = await c.get(f"/api/sessions/{session_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session"]["id"] == session_id
    assert body["crd_result"]["pa_needed"] is True
    assert body["questionnaire_session"] is None
    assert body["pas_submission"] is None


async def test_get_session_not_found(client: AsyncClient) -> None:
    async with client as c:
        resp = await c.get("/api/sessions/does-not-exist")
    assert resp.status_code == 404


# ── DELETE /api/sessions/{id} ────────────────────────────────────────────────

async def test_delete_session(client: AsyncClient) -> None:
    async with client as c:
        create_resp = await c.post(
            "/api/sessions", json={"hook": "order-sign", "scenario_key": "pa-required"}
        )
        session_id = create_resp.json()["session"]["id"]
        del_resp = await c.delete(f"/api/sessions/{session_id}")
        get_resp = await c.get(f"/api/sessions/{session_id}")
    assert del_resp.status_code == 200
    assert get_resp.status_code == 404


async def test_delete_session_not_found(client: AsyncClient) -> None:
    async with client as c:
        resp = await c.delete("/api/sessions/does-not-exist")
    assert resp.status_code == 404
