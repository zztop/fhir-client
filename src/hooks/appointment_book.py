"""appointment-book CDS Hook context builder."""
from __future__ import annotations
from uuid import uuid4
from src.hooks.base import build_prefetch
from src.models.pas import FixtureIds, Scenario


def _build_appointment(fixture_ids: FixtureIds, scenario: Scenario) -> dict:
    return {
        "resourceType": "Appointment",
        "status": "pending",
        "serviceType": [{"concept": {"coding": [{
            "system":  scenario.system,
            "code":    scenario.code,
            "display": scenario.display,
        }]}}],
        "subject": {"reference": f"Patient/{fixture_ids.patient}"},
        "participant": [
            {"actor": {"reference": f"Patient/{fixture_ids.patient}"},      "status": "accepted"},
            {"actor": {"reference": f"Practitioner/{fixture_ids.practitioner}"}, "status": "accepted"},
        ],
        "start": "2026-08-10T09:00:00Z",
        "end":   "2026-08-10T09:30:00Z",
    }


async def build_appointment_book_context(
    fixture_ids: FixtureIds,
    scenario: Scenario,
    fhir_base_url: str,
) -> dict:
    appointment = _build_appointment(fixture_ids, scenario)
    prefetch = await build_prefetch(fhir_base_url, fixture_ids)
    return {
        "hook": "appointment-book",
        "hookInstance": str(uuid4()),
        "fhirServer": fhir_base_url,
        "context": {
            "userId":      f"Practitioner/{fixture_ids.practitioner}",
            "patientId":   fixture_ids.patient,
            "encounterId": fixture_ids.encounter,
            "appointments": {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": [{"resource": appointment}],
            },
        },
        "prefetch": prefetch,
    }
