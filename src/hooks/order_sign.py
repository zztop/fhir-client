"""order-sign CDS Hook context builder."""
from __future__ import annotations
from uuid import uuid4
from src.hooks.base import build_prefetch
from src.models.pas import FixtureIds, Scenario


def _build_draft_order(
    fixture_ids: FixtureIds,
    scenario: Scenario,
    include_authored: bool = True,
) -> dict:
    if scenario.order_resource == "MedicationRequest":
        resource: dict = {
            "resourceType": "MedicationRequest",
            "status": "draft",
            "intent": "order",
            "medication": {"concept": {"coding": [{
                "system": scenario.system,
                "code":   scenario.code,
                "display": scenario.display,
            }]}},
            "subject":   {"reference": f"Patient/{fixture_ids.patient}"},
            "encounter": {"reference": f"Encounter/{fixture_ids.encounter}"},
            "requester": {"reference": f"Practitioner/{fixture_ids.practitioner}"},
        }
    else:
        resource = {
            "resourceType": "ServiceRequest",
            "status": "draft",
            "intent": "order",
            "code": {"concept": {"coding": [{
                "system": scenario.system,
                "code":   scenario.code,
                "display": scenario.display,
            }]}},
            "subject":   {"reference": f"Patient/{fixture_ids.patient}"},
            "encounter": {"reference": f"Encounter/{fixture_ids.encounter}"},
            "requester": {"reference": f"Practitioner/{fixture_ids.practitioner}"},
        }
    if include_authored:
        resource["authoredOn"] = "2026-08-03T09:30:00Z"
    return resource


async def build_order_sign_context(
    fixture_ids: FixtureIds,
    scenario: Scenario,
    fhir_base_url: str,
) -> dict:
    draft_order = _build_draft_order(fixture_ids, scenario, include_authored=True)
    prefetch = await build_prefetch(fhir_base_url, fixture_ids)
    return {
        "hook": "order-sign",
        "hookInstance": str(uuid4()),
        "fhirServer": fhir_base_url,
        "context": {
            "userId":      f"Practitioner/{fixture_ids.practitioner}",
            "patientId":   fixture_ids.patient,
            "encounterId": fixture_ids.encounter,
            "draftOrders": {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": [{"resource": draft_order}],
            },
        },
        "prefetch": prefetch,
    }
