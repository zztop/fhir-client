"""E2E: order-select with pa-not-required → single card, no DTR, no PAS."""
from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from src.hooks.base import resolve_scenario
from src.hooks.order_select import build_order_select_context
from src.models.pas import FixtureIds
from src.payer.cds_hooks_server import app as cds_app

_IDS = FixtureIds()
_MOCK_PATIENT = {"resourceType": "Patient", "id": "test-patient-001"}
_MOCK_COVERAGE = {
    "resourceType": "Bundle",
    "entry": [{"resource": {"resourceType": "Coverage", "id": "test-coverage-001"}}],
}


async def _mock_fetch(fhir_base_url: str, url: str) -> dict:
    return _MOCK_COVERAGE if "Coverage" in url else _MOCK_PATIENT


async def test_order_select_pa_not_required_one_card(monkeypatch) -> None:
    monkeypatch.setattr("src.hooks.base.fetch_resource", _mock_fetch)
    scenario = resolve_scenario("pa-not-required")
    ctx = await build_order_select_context(_IDS, scenario, "http://mock-fhir")

    async with AsyncClient(transport=ASGITransport(app=cds_app), base_url="http://test") as c:
        r = await c.post("/cds-services/crd-order-select", json=ctx)
    assert r.status_code == 200
    assert len(r.json()["cards"]) == 1


async def test_order_select_pa_not_required_pa_needed_false(monkeypatch) -> None:
    monkeypatch.setattr("src.hooks.base.fetch_resource", _mock_fetch)
    scenario = resolve_scenario("pa-not-required")
    ctx = await build_order_select_context(_IDS, scenario, "http://mock-fhir")

    async with AsyncClient(transport=ASGITransport(app=cds_app), base_url="http://test") as c:
        r = await c.post("/cds-services/crd-order-select", json=ctx)
    ext = r.json()["cards"][0]["extension"]["davinci-crd.coverage-information"][0]
    assert ext["pa-needed"] is False


async def test_order_select_pa_not_required_no_smart_links(monkeypatch) -> None:
    monkeypatch.setattr("src.hooks.base.fetch_resource", _mock_fetch)
    scenario = resolve_scenario("pa-not-required")
    ctx = await build_order_select_context(_IDS, scenario, "http://mock-fhir")

    async with AsyncClient(transport=ASGITransport(app=cds_app), base_url="http://test") as c:
        r = await c.post("/cds-services/crd-order-select", json=ctx)
    cards = r.json()["cards"]
    smart_links = [lnk for card in cards for lnk in card.get("links", []) if lnk["type"] == "smart"]
    assert len(smart_links) == 0


async def test_order_select_pa_not_required_doc_needed_no(monkeypatch) -> None:
    monkeypatch.setattr("src.hooks.base.fetch_resource", _mock_fetch)
    scenario = resolve_scenario("pa-not-required")
    ctx = await build_order_select_context(_IDS, scenario, "http://mock-fhir")

    async with AsyncClient(transport=ASGITransport(app=cds_app), base_url="http://test") as c:
        r = await c.post("/cds-services/crd-order-select", json=ctx)
    ext = r.json()["cards"][0]["extension"]["davinci-crd.coverage-information"][0]
    assert ext["doc-needed"] == "no"
