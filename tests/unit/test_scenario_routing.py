"""Unit tests for scenario_router — maps CDS Hook body codes to Scenarios."""
from __future__ import annotations

from src.payer.scenario_router import route


def _med_req(code: str) -> dict:
    return {"context": {"draftOrders": {"resourceType": "Bundle", "type": "collection", "entry": [
        {"resource": {
            "resourceType": "MedicationRequest",
            "medication": {"concept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": code}]}},
        }}
    ]}}}


def _svc_req(code: str) -> dict:
    return {"context": {"draftOrders": {"resourceType": "Bundle", "type": "collection", "entry": [
        {"resource": {
            "resourceType": "ServiceRequest",
            "code": {"concept": {"coding": [{"system": "http://www.ama-assn.org/go/cpt", "code": code}]}},
        }}
    ]}}}


def _appt(code: str) -> dict:
    return {"context": {"appointments": {"resourceType": "Bundle", "type": "collection", "entry": [
        {"resource": {
            "resourceType": "Appointment",
            "serviceType": [{"concept": {"coding": [{"system": "http://www.ama-assn.org/go/cpt", "code": code}]}}],
        }}
    ]}}}


def test_medication_request_pa_required() -> None:
    s = route(_med_req("1049502"))
    assert s is not None and s.scenario == "pa-required"


def test_service_request_pa_not_required() -> None:
    s = route(_svc_req("85025"))
    assert s is not None and s.scenario == "pa-not-required"


def test_service_request_auth_pending() -> None:
    s = route(_svc_req("33533"))
    assert s is not None and s.scenario == "auth-pending"


def test_appointment_auth_pending() -> None:
    s = route(_appt("33533"))
    assert s is not None and s.scenario == "auth-pending"


def test_appointment_pa_not_required() -> None:
    s = route(_appt("85025"))
    assert s is not None and s.scenario == "pa-not-required"


def test_unknown_medication_returns_none() -> None:
    assert route(_med_req("UNKNOWN-9999")) is None


def test_empty_body_returns_none() -> None:
    assert route({}) is None


def test_route_returns_scenario_code() -> None:
    s = route(_med_req("1049502"))
    assert s is not None and s.code == "1049502"


def test_route_returns_order_resource_type() -> None:
    s = route(_med_req("1049502"))
    assert s is not None and s.order_resource == "MedicationRequest"
