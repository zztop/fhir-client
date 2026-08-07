"""Integration tests for the DTR questionnaire flow (static + adaptive).

Runs the real CDS and DTR stub apps in-process via ASGITransport against a
temporary SQLite database. The DTR stub always serves a static questionnaire,
so the adaptive path is exercised by monkeypatching `detect_mode` to force
"adaptive" — the underlying $next-question protocol is identical either way.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.api import db as api_db
from src.api.main import app
from src.payer.cds_hooks_server import app as cds_app
from src.payer.dtr_server import app as dtr_app

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
def _patch_payer_transports(monkeypatch):
    # Both crd_service and dtr_service do a plain `import httpx`, so patching
    # `httpx.AsyncClient` from either module's namespace patches the same
    # shared global attribute — a second such patch silently clobbers the
    # first. Route by origin instead, with a single global patch.
    mounts = {
        "http://localhost:3001": ASGITransport(app=cds_app),
        "http://localhost:3002": ASGITransport(app=dtr_app),
    }

    def _client_factory(*args, **kwargs):
        # dtr_service issues relative-path requests against a base_url; crd_service
        # issues absolute-URL requests. A base_url here resolves the former, while
        # mounts route both by origin regardless of which one is used.
        return AsyncClient(base_url="http://localhost:3002", mounts=mounts)

    monkeypatch.setattr("httpx.AsyncClient", _client_factory)


@pytest.fixture
def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE)


async def _create_session(c: AsyncClient, hook: str, scenario_key: str) -> str:
    resp = await c.post("/api/sessions", json={"hook": hook, "scenario_key": scenario_key})
    return resp.json()["session"]["id"]


_STATIC_ANSWERS = [
    {"linkId": "1", "answer": [{"valueBoolean": True}]},
    {"linkId": "2", "answer": [{"valueString": "M54.5"}]},
    {"linkId": "3", "answer": [{"valueString": "1234567890"}]},
    {"linkId": "4", "answer": [{"valueInteger": 30}]},
]


# ── POST /dtr/start ───────────────────────────────────────────────────────────

async def test_start_dtr_static_returns_all_questions(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        resp = await c.post(f"/api/sessions/{session_id}/dtr/start")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "static"
    assert len(body["questions"]) == 4


async def test_start_dtr_updates_session_status(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        await c.post(f"/api/sessions/{session_id}/dtr/start")
        detail = await c.get(f"/api/sessions/{session_id}")
    assert detail.json()["session"]["status"] == "dtr_in_progress"


async def test_start_dtr_without_smart_url_returns_400(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-not-required")
        resp = await c.post(f"/api/sessions/{session_id}/dtr/start")
    assert resp.status_code == 400


async def test_start_dtr_unknown_session_returns_404(client: AsyncClient) -> None:
    async with client as c:
        resp = await c.post("/api/sessions/does-not-exist/dtr/start")
    assert resp.status_code == 404


# ── GET /dtr ──────────────────────────────────────────────────────────────────

async def test_get_dtr_state_static(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        await c.post(f"/api/sessions/{session_id}/dtr/start")
        resp = await c.get(f"/api/sessions/{session_id}/dtr")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "static"
    assert len(body["questions"]) == 4
    assert body["answered_items"] == []


async def test_get_dtr_state_before_start_returns_404(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        resp = await c.get(f"/api/sessions/{session_id}/dtr")
    assert resp.status_code == 404


# ── POST /dtr/submit (static) ────────────────────────────────────────────────

async def test_submit_static_returns_qr_reference(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        await c.post(f"/api/sessions/{session_id}/dtr/start")
        resp = await c.post(
            f"/api/sessions/{session_id}/dtr/submit", json={"items": _STATIC_ANSWERS}
        )
    assert resp.status_code == 200
    assert resp.json()["qr_reference"].startswith("QuestionnaireResponse/")


async def test_submit_static_updates_session_status(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        await c.post(f"/api/sessions/{session_id}/dtr/start")
        await c.post(f"/api/sessions/{session_id}/dtr/submit", json={"items": _STATIC_ANSWERS})
        detail = await c.get(f"/api/sessions/{session_id}")
    body = detail.json()
    assert body["session"]["status"] == "dtr_complete"
    assert body["questionnaire_session"]["qr_reference"].startswith("QuestionnaireResponse/")


async def test_submit_static_without_items_returns_400(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        await c.post(f"/api/sessions/{session_id}/dtr/start")
        resp = await c.post(f"/api/sessions/{session_id}/dtr/submit")
    assert resp.status_code == 400


# ── POST /dtr/next rejected outside adaptive mode ────────────────────────────

async def test_next_question_rejected_in_static_mode(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        await c.post(f"/api/sessions/{session_id}/dtr/start")
        resp = await c.post(
            f"/api/sessions/{session_id}/dtr/next",
            json={"linkId": "1", "answer": [{"valueBoolean": True}]},
        )
    assert resp.status_code == 400


# ── Adaptive flow (mode forced via monkeypatch) ──────────────────────────────

async def test_adaptive_flow_full(monkeypatch, client: AsyncClient) -> None:
    monkeypatch.setattr("src.api.routers.dtr.detect_mode", lambda questionnaire_json: "adaptive")

    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")

        start_resp = await c.post(f"/api/sessions/{session_id}/dtr/start")
        assert start_resp.status_code == 200
        start_body = start_resp.json()
        assert start_body["mode"] == "adaptive"
        assert start_body["current_question"]["linkId"] == "1"
        assert start_body["answered_count"] == 0

        for i, answer in enumerate(_STATIC_ANSWERS[:-1], start=1):
            r = await c.post(f"/api/sessions/{session_id}/dtr/next", json=answer)
            assert r.status_code == 200
            body = r.json()
            assert body["done"] is False
            assert body["answered_count"] == i
            assert body["current_question"]["linkId"] == str(i + 1)

        r = await c.post(f"/api/sessions/{session_id}/dtr/next", json=_STATIC_ANSWERS[-1])
        body = r.json()
        assert body["done"] is True
        assert body["current_question"] is None
        assert body["answered_count"] == 4

        submit_resp = await c.post(f"/api/sessions/{session_id}/dtr/submit")
        assert submit_resp.status_code == 200
        assert submit_resp.json()["qr_reference"].startswith("QuestionnaireResponse/")

        detail = await c.get(f"/api/sessions/{session_id}")

    detail_body = detail.json()
    assert detail_body["session"]["status"] == "dtr_complete"
    assert detail_body["questionnaire_session"]["mode"] == "adaptive"
    assert len(detail_body["questionnaire_session"]["answered_items"]) == 4
