"""Integration tests for the PAS bundle review + submission lifecycle.

Runs the real CDS and PAS stub apps in-process via ASGITransport against a
temporary SQLite database.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.api import db as api_db
from src.api.main import app
from src.payer.cds_hooks_server import app as cds_app
from src.payer.pas_server import app as pas_app

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
    mounts = {
        "http://localhost:3001": ASGITransport(app=cds_app),
        "http://localhost:3003": ASGITransport(app=pas_app),
    }

    def _client_factory(*args, **kwargs):
        # pas_service issues relative-path requests against a base_url; crd_service
        # issues absolute-URL requests. A base_url here resolves the former, while
        # mounts route both by origin regardless of which one is used.
        return AsyncClient(base_url="http://localhost:3003", mounts=mounts)

    monkeypatch.setattr("httpx.AsyncClient", _client_factory)


@pytest.fixture
def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE)


async def _create_session(c: AsyncClient, hook: str, scenario_key: str) -> str:
    resp = await c.post("/api/sessions", json={"hook": hook, "scenario_key": scenario_key})
    return resp.json()["session"]["id"]


def _claim(bundle: dict) -> dict:
    return next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Claim")


# ── POST /pas/prepare ─────────────────────────────────────────────────────────

async def test_prepare_returns_bundle_with_claim(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        resp = await c.post(f"/api/sessions/{session_id}/pas/prepare")
    assert resp.status_code == 200
    assert _claim(resp.json()["bundle"])["use"] == "preauthorization"


async def test_prepare_updates_session_status(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        await c.post(f"/api/sessions/{session_id}/pas/prepare")
        detail = await c.get(f"/api/sessions/{session_id}")
    assert detail.json()["session"]["status"] == "pas_reviewing"


async def test_prepare_unknown_session_returns_404(client: AsyncClient) -> None:
    async with client as c:
        resp = await c.post("/api/sessions/does-not-exist/pas/prepare")
    assert resp.status_code == 404


# ── GET /pas/bundle ───────────────────────────────────────────────────────────

async def test_get_bundle_before_prepare_returns_404(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        resp = await c.get(f"/api/sessions/{session_id}/pas/bundle")
    assert resp.status_code == 404


async def test_get_bundle_after_prepare(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        await c.post(f"/api/sessions/{session_id}/pas/prepare")
        resp = await c.get(f"/api/sessions/{session_id}/pas/bundle")
    assert resp.status_code == 200
    assert resp.json()["bundle"]["resourceType"] == "Bundle"


# ── PATCH /pas/bundle ─────────────────────────────────────────────────────────

async def test_patch_bundle_updates_diagnosis_code(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        await c.post(f"/api/sessions/{session_id}/pas/prepare")
        resp = await c.patch(
            f"/api/sessions/{session_id}/pas/bundle", json={"diagnosis_code": "M54.5"}
        )
    assert resp.status_code == 200
    claim = _claim(resp.json()["bundle"])
    assert claim["diagnosis"][0]["diagnosisCodeableConcept"]["coding"][0]["code"] == "M54.5"


async def test_patch_bundle_updates_quantity_and_priority(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        await c.post(f"/api/sessions/{session_id}/pas/prepare")
        resp = await c.patch(
            f"/api/sessions/{session_id}/pas/bundle", json={"quantity": 5, "priority": "stat"}
        )
    claim = _claim(resp.json()["bundle"])
    assert claim["item"][0]["quantity"]["value"] == 5
    assert claim["priority"]["coding"][0]["code"] == "stat"


async def test_patch_bundle_persists_across_get(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        await c.post(f"/api/sessions/{session_id}/pas/prepare")
        await c.patch(f"/api/sessions/{session_id}/pas/bundle", json={"quantity": 9})
        resp = await c.get(f"/api/sessions/{session_id}/pas/bundle")
    assert _claim(resp.json()["bundle"])["item"][0]["quantity"]["value"] == 9


async def test_patch_bundle_before_prepare_returns_404(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        resp = await c.patch(f"/api/sessions/{session_id}/pas/bundle", json={"quantity": 2})
    assert resp.status_code == 404


# ── POST /pas/submit ──────────────────────────────────────────────────────────

async def test_submit_pa_required_granted(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        await c.post(f"/api/sessions/{session_id}/pas/prepare")
        resp = await c.post(f"/api/sessions/{session_id}/pas/submit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["disposition"] == "Granted"
    assert body["auth_number"] == "AUTH-2026-0803-001"
    assert body["claim_response"]["resourceType"] == "ClaimResponse"


async def test_submit_updates_session_status_to_granted(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        await c.post(f"/api/sessions/{session_id}/pas/prepare")
        await c.post(f"/api/sessions/{session_id}/pas/submit")
        detail = await c.get(f"/api/sessions/{session_id}")
    body = detail.json()
    assert body["session"]["status"] == "granted"
    assert body["pas_submission"]["disposition"] == "Granted"
    assert body["pas_submission"]["auth_number"] == "AUTH-2026-0803-001"


async def test_submit_without_prepare_returns_404(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "order-sign", "pa-required")
        resp = await c.post(f"/api/sessions/{session_id}/pas/submit")
    assert resp.status_code == 404


# ── POST /pas/inquire ─────────────────────────────────────────────────────────

async def test_auth_pending_then_inquire_resolves_granted(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "appointment-book", "auth-pending")
        await c.post(f"/api/sessions/{session_id}/pas/prepare")

        submit_resp = await c.post(f"/api/sessions/{session_id}/pas/submit")
        assert submit_resp.json()["disposition"] == "Pended"

        inquire_resp = await c.post(f"/api/sessions/{session_id}/pas/inquire")

    assert inquire_resp.status_code == 200
    body = inquire_resp.json()
    assert body["disposition"] == "Granted"
    assert body["auth_number"] == "AUTH-2026-0803-INQ"


async def test_inquire_updates_session_status_to_granted(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "appointment-book", "auth-pending")
        await c.post(f"/api/sessions/{session_id}/pas/prepare")
        await c.post(f"/api/sessions/{session_id}/pas/submit")
        await c.post(f"/api/sessions/{session_id}/pas/inquire")
        detail = await c.get(f"/api/sessions/{session_id}")
    assert detail.json()["session"]["status"] == "granted"


async def test_inquire_without_prepare_returns_404(client: AsyncClient) -> None:
    async with client as c:
        session_id = await _create_session(c, "appointment-book", "auth-pending")
        resp = await c.post(f"/api/sessions/{session_id}/pas/inquire")
    assert resp.status_code == 404
