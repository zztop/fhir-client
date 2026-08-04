"""E2E: order-sign → CRD cards → DTR → PAS → Granted."""
from __future__ import annotations

import json

from httpx import ASGITransport, AsyncClient

from src.ehr.pas_submitter import build_pas_bundle
from src.hooks.base import resolve_scenario
from src.hooks.order_sign import build_order_sign_context
from src.models.pas import FixtureIds
from src.payer.cds_hooks_server import app as cds_app
from src.payer.dtr_server import app as dtr_app
from src.payer.pas_server import app as pas_app

_IDS = FixtureIds()
_MOCK_PATIENT = {"resourceType": "Patient", "id": "test-patient-001"}
_MOCK_COVERAGE = {
    "resourceType": "Bundle",
    "entry": [{"resource": {"resourceType": "Coverage", "id": "test-coverage-001"}}],
}


async def _mock_fetch(fhir_base_url: str, url: str) -> dict:
    return _MOCK_COVERAGE if "Coverage" in url else _MOCK_PATIENT


async def test_order_sign_pa_required_full_workflow(monkeypatch) -> None:
    monkeypatch.setattr("src.hooks.base.fetch_resource", _mock_fetch)
    scenario = resolve_scenario("pa-required")
    ctx = await build_order_sign_context(_IDS, scenario, "http://mock-fhir")

    # ── Step 1: CRD ──────────────────────────────────────────────
    async with AsyncClient(transport=ASGITransport(app=cds_app), base_url="http://test") as c:
        cds_r = await c.post("/cds-services/crd-order-sign", json=ctx)
    assert cds_r.status_code == 200
    cards = cds_r.json()["cards"]
    assert len(cards) == 2

    cov_ext = cards[0]["extension"]["davinci-crd.coverage-information"][0]
    assert cov_ext["pa-needed"] is True

    # ── Step 2: DTR — fetch questionnaire ────────────────────────
    smart = next(lnk for card in cards for lnk in card.get("links", []) if lnk["type"] == "smart")
    q_url = json.loads(smart["appContext"])["questionnaire"]
    q_path = q_url.replace("http://localhost:3002", "")

    async with AsyncClient(transport=ASGITransport(app=dtr_app), base_url="http://test") as c:
        q_r = await c.get(q_path)
        assert q_r.status_code == 200
        assert len(q_r.json()["item"]) == 4

        # ── Step 3: DTR — submit QuestionnaireResponse ────────────
        qr_r = await c.post("/fhir/r4/QuestionnaireResponse", json={
            "resourceType": "QuestionnaireResponse",
            "questionnaire": q_url,
            "status": "completed",
            "item": [
                {"linkId": "1", "answer": [{"valueBoolean": True}]},
                {"linkId": "2", "answer": [{"valueString": "M54.5"}]},
                {"linkId": "3", "answer": [{"valueString": "1234567890"}]},
                {"linkId": "4", "answer": [{"valueInteger": 30}]},
            ],
        })
    assert qr_r.status_code == 200
    qr_ref = f"QuestionnaireResponse/{qr_r.json()['id']}"

    # ── Step 4: PAS — submit ─────────────────────────────────────
    bundle = build_pas_bundle(_IDS, scenario, qr_reference=qr_ref)
    async with AsyncClient(transport=ASGITransport(app=pas_app), base_url="http://test") as c:
        pas_r = await c.post("/fhir/r4/Claim/$submit", json=bundle)
    assert pas_r.status_code == 200
    data = pas_r.json()
    assert data["disposition"] == "Granted"
    ext_items = data["extension"][0]["extension"]
    assert any(e.get("url") == "number" for e in ext_items)


async def test_order_sign_crd_response_validates(monkeypatch) -> None:
    """CRD response for PA-required scenario conforms to CDS Hook structure."""
    from src.fhir.validator import validate_cds_response
    monkeypatch.setattr("src.hooks.base.fetch_resource", _mock_fetch)
    scenario = resolve_scenario("pa-required")
    ctx = await build_order_sign_context(_IDS, scenario, "http://mock-fhir")

    async with AsyncClient(transport=ASGITransport(app=cds_app), base_url="http://test") as c:
        r = await c.post("/cds-services/crd-order-sign", json=ctx)
    validate_cds_response(r.json())
