"""order-select CDS Hook context builder.

Identical to order-sign except authoredOn is omitted (provider still selecting)
and a selections array names the chosen item.
"""
from __future__ import annotations
from uuid import uuid4
from src.hooks.base import build_prefetch
from src.hooks.order_sign import _build_draft_order
from src.models.pas import FixtureIds, Scenario


async def build_order_select_context(
    fixture_ids: FixtureIds,
    scenario: Scenario,
    fhir_base_url: str,
) -> dict:
    draft_order = _build_draft_order(fixture_ids, scenario, include_authored=False)
    prefetch = await build_prefetch(fhir_base_url, fixture_ids)
    resource_type = draft_order["resourceType"]
    return {
        "hook": "order-select",
        "hookInstance": str(uuid4()),
        "fhirServer": fhir_base_url,
        "context": {
            "userId":      f"Practitioner/{fixture_ids.practitioner}",
            "patientId":   fixture_ids.patient,
            "encounterId": fixture_ids.encounter,
            "selections":  [f"{resource_type}#draft-order-001"],
            "draftOrders": {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": [{"resource": draft_order}],
            },
        },
        "prefetch": prefetch,
    }
