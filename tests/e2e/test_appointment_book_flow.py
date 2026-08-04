"""E2E: appointment-book → CRD cards → PAS Pended → $inquire → Granted."""
from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from src.ehr.pas_submitter import build_pas_bundle
from src.hooks.appointment_book import build_appointment_book_context
from src.hooks.base import resolve_scenario
from src.models.pas import FixtureIds
from src.payer.cds_hooks_server import app as cds_app
from src.payer.pas_server import app as pas_app

_IDS = FixtureIds()
_MOCK_PATIENT = {"resourceType": "Patient", "id": "test-patient-001"}
_MOCK_COVERAGE = {
    "resourceType": "Bundle",
    "entry": [{"resource": {"resourceType": "Coverage", "id": "test-coverage-001"}}],
}


async def _mock_fetch(fhir_base_url: str, url: str) -> dict:
    return _MOCK_COVERAGE if "Coverage" in url else _MOCK_PATIENT


async def test_appointment_book_auth_pending_resolves_via_inquire(monkeypatch) -> None:
    monkeypatch.setattr("src.hooks.base.fetch_resource", _mock_fetch)
    scenario = resolve_scenario("auth-pending")
    ctx = await build_appointment_book_context(_IDS, scenario, "http://mock-fhir")

    # ── Step 1: CRD ──────────────────────────────────────────────
    async with AsyncClient(transport=ASGITransport(app=cds_app), base_url="http://test") as c:
        cds_r = await c.post("/cds-services/crd-appointment-book", json=ctx)
    assert cds_r.status_code == 200
    cards = cds_r.json()["cards"]
    assert len(cards) == 2

    cov_ext = cards[0]["extension"]["davinci-crd.coverage-information"][0]
    assert cov_ext["pa-needed"] is True

    # ── Step 2: PAS $submit → Pended ─────────────────────────────
    bundle = build_pas_bundle(_IDS, scenario)
    async with AsyncClient(transport=ASGITransport(app=pas_app), base_url="http://test") as c:
        submit_r = await c.post("/fhir/r4/Claim/$submit", json=bundle)
    assert submit_r.status_code == 200
    assert submit_r.json()["disposition"] == "Pended"

    # ── Step 3: PAS $inquire → Granted ───────────────────────────
    async with AsyncClient(transport=ASGITransport(app=pas_app), base_url="http://test") as c:
        inq_r = await c.post("/fhir/r4/Claim/$inquire", json=bundle)
    assert inq_r.status_code == 200
    data = inq_r.json()
    assert data["disposition"] == "Granted"
    ext_items = data["extension"][0]["extension"]
    assert any(e.get("url") == "number" for e in ext_items)


async def test_appointment_book_crd_returns_smart_link(monkeypatch) -> None:
    monkeypatch.setattr("src.hooks.base.fetch_resource", _mock_fetch)
    scenario = resolve_scenario("auth-pending")
    ctx = await build_appointment_book_context(_IDS, scenario, "http://mock-fhir")

    async with AsyncClient(transport=ASGITransport(app=cds_app), base_url="http://test") as c:
        r = await c.post("/cds-services/crd-appointment-book", json=ctx)
    cards = r.json()["cards"]
    smart_links = [lnk for card in cards for lnk in card.get("links", []) if lnk["type"] == "smart"]
    assert len(smart_links) == 1
