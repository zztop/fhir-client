"""Unit tests for CDS Hook context builders — no live FHIR server required."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from src.hooks.appointment_book import _build_appointment, build_appointment_book_context
from src.hooks.order_select import build_order_select_context
from src.hooks.order_sign import _build_draft_order, build_order_sign_context
from src.models.pas import FixtureIds, Scenario

IDS = FixtureIds()

MED_SCENARIO = Scenario(
    code="1049502", system="http://www.nlm.nih.gov/research/umls/rxnorm",
    scenario="pa-required", display="Oxycodone 5mg", order_resource="MedicationRequest",
)
SVC_SCENARIO = Scenario(
    code="85025", system="http://www.ama-assn.org/go/cpt",
    scenario="pa-not-required", display="CBC with differential", order_resource="ServiceRequest",
)
FHIR_URL = "http://localhost:8080/fhir/r4"

_MOCK_PATIENT = {"resourceType": "Patient", "id": "test-patient-001"}


@pytest.fixture(autouse=True)
def _mock_fetch(monkeypatch: pytest.MonkeyPatch):
    async def _fake_fetch(base_url: str, rel: str) -> dict:
        if rel.startswith("Coverage"):
            return {"resourceType": "Bundle", "type": "searchset", "entry": []}
        return _MOCK_PATIENT
    monkeypatch.setattr("src.hooks.base.fetch_resource", _fake_fetch)


# ── draft order helpers ───────────────────────────────────────────────────────

def test_medication_request_built_for_rxnorm():
    order = _build_draft_order(IDS, MED_SCENARIO, include_authored=True)
    assert order["resourceType"] == "MedicationRequest"
    assert order["medication"]["concept"]["coding"][0]["code"] == "1049502"

def test_service_request_built_for_cpt():
    order = _build_draft_order(IDS, SVC_SCENARIO, include_authored=True)
    assert order["resourceType"] == "ServiceRequest"
    assert order["code"]["concept"]["coding"][0]["code"] == "85025"

def test_draft_order_has_correct_references():
    order = _build_draft_order(IDS, MED_SCENARIO)
    assert order["subject"]["reference"]   == f"Patient/{IDS.patient}"
    assert order["encounter"]["reference"] == f"Encounter/{IDS.encounter}"
    assert order["requester"]["reference"] == f"Practitioner/{IDS.practitioner}"

def test_authored_on_present_when_requested():
    assert "authoredOn" in _build_draft_order(IDS, MED_SCENARIO, include_authored=True)

def test_authored_on_absent_when_not_requested():
    assert "authoredOn" not in _build_draft_order(IDS, MED_SCENARIO, include_authored=False)


# ── order-sign ────────────────────────────────────────────────────────────────

async def test_order_sign_hook_field():
    ctx = await build_order_sign_context(IDS, MED_SCENARIO, FHIR_URL)
    assert ctx["hook"] == "order-sign"

async def test_order_sign_has_draft_orders_bundle():
    ctx = await build_order_sign_context(IDS, MED_SCENARIO, FHIR_URL)
    bundle = ctx["context"]["draftOrders"]
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert len(bundle["entry"]) == 1

async def test_order_sign_patient_and_encounter_ids():
    ctx = await build_order_sign_context(IDS, MED_SCENARIO, FHIR_URL)
    assert ctx["context"]["patientId"]   == IDS.patient
    assert ctx["context"]["encounterId"] == IDS.encounter

async def test_order_sign_has_prefetch():
    ctx = await build_order_sign_context(IDS, MED_SCENARIO, FHIR_URL)
    assert "prefetch" in ctx
    assert "patient" in ctx["prefetch"]
    assert "coverage" in ctx["prefetch"]


# ── order-select ──────────────────────────────────────────────────────────────

async def test_order_select_hook_field():
    ctx = await build_order_select_context(IDS, MED_SCENARIO, FHIR_URL)
    assert ctx["hook"] == "order-select"

async def test_order_select_has_selections():
    ctx = await build_order_select_context(IDS, MED_SCENARIO, FHIR_URL)
    assert isinstance(ctx["context"]["selections"], list)
    assert len(ctx["context"]["selections"]) > 0

async def test_order_select_draft_order_has_no_authored_on():
    ctx = await build_order_select_context(IDS, MED_SCENARIO, FHIR_URL)
    resource = ctx["context"]["draftOrders"]["entry"][0]["resource"]
    assert "authoredOn" not in resource


# ── appointment-book ──────────────────────────────────────────────────────────

def test_appointment_has_correct_service_code():
    appt = _build_appointment(IDS, SVC_SCENARIO)
    code = appt["serviceType"][0]["concept"]["coding"][0]["code"]
    assert code == "85025"

def test_appointment_participants_include_patient_and_practitioner():
    appt = _build_appointment(IDS, SVC_SCENARIO)
    actors = {p["actor"]["reference"] for p in appt["participant"]}
    assert f"Patient/{IDS.patient}"           in actors
    assert f"Practitioner/{IDS.practitioner}" in actors

async def test_appointment_book_hook_field():
    ctx = await build_appointment_book_context(IDS, SVC_SCENARIO, FHIR_URL)
    assert ctx["hook"] == "appointment-book"

async def test_appointment_book_has_appointments_bundle():
    ctx = await build_appointment_book_context(IDS, SVC_SCENARIO, FHIR_URL)
    bundle = ctx["context"]["appointments"]
    assert bundle["resourceType"] == "Bundle"
    assert len(bundle["entry"]) == 1
