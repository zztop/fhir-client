"""Integration tests for the CRD 2.1.0 CDS Hooks stub server.

Uses httpx ASGITransport — no running server required.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.payer.cds_hooks_server import app

BASE = "http://test"


@pytest.fixture
def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE)


# ── Helpers: shared request bodies ───────────────────────────────────────────

def _order_sign_body(code: str, system: str, resource_type: str = "MedicationRequest") -> dict:
    if resource_type == "MedicationRequest":
        order_resource = {
            "resourceType": "MedicationRequest",
            "status": "draft", "intent": "order",
            "medication": {"concept": {"coding": [{"system": system, "code": code}]}},
            "subject": {"reference": "Patient/test-patient-001"},
        }
    else:
        order_resource = {
            "resourceType": "ServiceRequest",
            "status": "draft", "intent": "order",
            "code": {"concept": {"coding": [{"system": system, "code": code}]}},
            "subject": {"reference": "Patient/test-patient-001"},
        }
    return {
        "hook": "order-sign",
        "hookInstance": "int-test-001",
        "context": {
            "userId": "Practitioner/test-practitioner-001",
            "patientId": "test-patient-001",
            "encounterId": "test-encounter-001",
            "draftOrders": {
                "resourceType": "Bundle", "type": "collection",
                "entry": [{"resource": order_resource}],
            },
        },
        "prefetch": {},
    }


def _appt_book_body(code: str, system: str) -> dict:
    return {
        "hook": "appointment-book",
        "hookInstance": "int-test-002",
        "context": {
            "userId": "Practitioner/test-practitioner-001",
            "patientId": "test-patient-001",
            "encounterId": "test-encounter-001",
            "appointments": {
                "resourceType": "Bundle", "type": "collection",
                "entry": [{"resource": {
                    "resourceType": "Appointment",
                    "status": "pending",
                    "serviceType": [{"concept": {"coding": [{"system": system, "code": code}]}}],
                    "participant": [{"actor": {"reference": "Patient/test-patient-001"}, "status": "accepted"}],
                }}],
            },
        },
        "prefetch": {},
    }


# ── Discovery ─────────────────────────────────────────────────────────────────

async def test_discovery_ok(client: AsyncClient) -> None:
    async with client as c:
        r = await c.get("/cds-services")
    assert r.status_code == 200


async def test_discovery_returns_three_services(client: AsyncClient) -> None:
    async with client as c:
        r = await c.get("/cds-services")
    ids = {s["id"] for s in r.json()["services"]}
    assert ids == {"crd-order-sign", "crd-order-select", "crd-appointment-book"}


async def test_discovery_prefetch_keys_present(client: AsyncClient) -> None:
    async with client as c:
        r = await c.get("/cds-services")
    for svc in r.json()["services"]:
        assert "patient"   in svc["prefetch"]
        assert "coverage"  in svc["prefetch"]


# ── order-sign: PA required (RxNorm 1049502 → MedicationRequest) ──────────────

async def test_order_sign_pa_required_status_ok(client: AsyncClient) -> None:
    body = _order_sign_body("1049502", "http://www.nlm.nih.gov/research/umls/rxnorm")
    async with client as c:
        r = await c.post("/cds-services/crd-order-sign", json=body)
    assert r.status_code == 200


async def test_order_sign_pa_required_two_cards(client: AsyncClient) -> None:
    body = _order_sign_body("1049502", "http://www.nlm.nih.gov/research/umls/rxnorm")
    async with client as c:
        r = await c.post("/cds-services/crd-order-sign", json=body)
    assert len(r.json()["cards"]) == 2


async def test_order_sign_pa_required_coverage_ext(client: AsyncClient) -> None:
    body = _order_sign_body("1049502", "http://www.nlm.nih.gov/research/umls/rxnorm")
    async with client as c:
        r = await c.post("/cds-services/crd-order-sign", json=body)
    ext = r.json()["cards"][0]["extension"]["davinci-crd.coverage-information"][0]
    assert ext["pa-needed"] is True
    assert ext["covered"] == "covered"
    assert "date" in ext


async def test_order_sign_pa_required_smart_link(client: AsyncClient) -> None:
    body = _order_sign_body("1049502", "http://www.nlm.nih.gov/research/umls/rxnorm")
    async with client as c:
        r = await c.post("/cds-services/crd-order-sign", json=body)
    form_card = r.json()["cards"][1]
    link_types = {lnk["type"] for lnk in form_card["links"]}
    assert "smart" in link_types


# ── order-sign: PA not required (CPT 85025 → ServiceRequest) ─────────────────

async def test_order_sign_pa_not_required_one_card(client: AsyncClient) -> None:
    body = _order_sign_body("85025", "http://www.ama-assn.org/go/cpt", "ServiceRequest")
    async with client as c:
        r = await c.post("/cds-services/crd-order-sign", json=body)
    assert len(r.json()["cards"]) == 1


async def test_order_sign_pa_not_required_ext_false(client: AsyncClient) -> None:
    body = _order_sign_body("85025", "http://www.ama-assn.org/go/cpt", "ServiceRequest")
    async with client as c:
        r = await c.post("/cds-services/crd-order-sign", json=body)
    ext = r.json()["cards"][0]["extension"]["davinci-crd.coverage-information"][0]
    assert ext["pa-needed"] is False
    assert ext["doc-needed"] == "no"


# ── order-sign: auth-pending (CPT 33533 → ServiceRequest) ────────────────────

async def test_order_sign_auth_pending_pa_needed(client: AsyncClient) -> None:
    body = _order_sign_body("33533", "http://www.ama-assn.org/go/cpt", "ServiceRequest")
    async with client as c:
        r = await c.post("/cds-services/crd-order-sign", json=body)
    ext = r.json()["cards"][0]["extension"]["davinci-crd.coverage-information"][0]
    assert ext["pa-needed"] is True


# ── order-select ──────────────────────────────────────────────────────────────

async def test_order_select_routes_correctly(client: AsyncClient) -> None:
    body = _order_sign_body("1049502", "http://www.nlm.nih.gov/research/umls/rxnorm")
    body["hook"] = "order-select"
    async with client as c:
        r = await c.post("/cds-services/crd-order-select", json=body)
    assert r.status_code == 200
    assert len(r.json()["cards"]) == 2


# ── appointment-book ──────────────────────────────────────────────────────────

async def test_appointment_book_auth_pending(client: AsyncClient) -> None:
    body = _appt_book_body("33533", "http://www.ama-assn.org/go/cpt")
    async with client as c:
        r = await c.post("/cds-services/crd-appointment-book", json=body)
    assert r.status_code == 200
    ext = r.json()["cards"][0]["extension"]["davinci-crd.coverage-information"][0]
    assert ext["pa-needed"] is True


async def test_appointment_book_pa_not_required(client: AsyncClient) -> None:
    body = _appt_book_body("85025", "http://www.ama-assn.org/go/cpt")
    async with client as c:
        r = await c.post("/cds-services/crd-appointment-book", json=body)
    ext = r.json()["cards"][0]["extension"]["davinci-crd.coverage-information"][0]
    assert ext["pa-needed"] is False


# ── unknown code ──────────────────────────────────────────────────────────────

async def test_unknown_code_returns_info_card(client: AsyncClient) -> None:
    body = _order_sign_body("UNKNOWN-9999", "http://example.org")
    async with client as c:
        r = await c.post("/cds-services/crd-order-sign", json=body)
    assert r.status_code == 200
    card = r.json()["cards"][0]
    assert card["indicator"] == "info"
    assert "extension" not in card
