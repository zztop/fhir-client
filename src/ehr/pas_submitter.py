"""EHR-side PAS 2.1.0 submitter — builds PAS Claim bundle and posts to payer."""
from __future__ import annotations

import asyncio
from datetime import date
from uuid import uuid4

import httpx

from src.config import settings
from src.models.pas import FixtureIds, PASDispo, Scenario


def build_pas_bundle(
    fixture_ids: FixtureIds,
    scenario: Scenario,
    qr_reference: str | None = None,
) -> dict:
    supporting_info: list[dict] = []
    if qr_reference:
        supporting_info.append({
            "sequence": 1,
            "category": {
                "coding": [{
                    "system": "http://hl7.org/fhir/us/davinci-pas/CodeSystem/PASSupportingInfoType",
                    "code":   "patientEvent",
                }]
            },
            "valueReference": {"reference": qr_reference},
        })

    claim: dict = {
        "resourceType": "Claim",
        "id": f"pas-claim-{uuid4().hex[:8]}",
        "meta": {
            "profile": [
                "http://hl7.org/fhir/us/davinci-pas/StructureDefinition/profile-claim"
            ]
        },
        "status": "active",
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                "code":   "professional",
            }]
        },
        "use":      "preauthorization",
        "patient":  {"reference": f"Patient/{fixture_ids.patient}"},
        "created":  date.today().isoformat(),
        "insurer":  {"reference": f"Organization/{fixture_ids.payer}"},
        "provider": {"reference": f"Practitioner/{fixture_ids.practitioner}"},
        "priority": {"coding": [{"code": "normal"}]},
        "insurance": [{
            "sequence": 1,
            "focal":    True,
            "coverage": {"reference": f"Coverage/{fixture_ids.coverage}"},
        }],
        "item": [{
            "sequence": 1,
            "productOrService": {
                "coding": [{
                    "system":  scenario.system,
                    "code":    scenario.code,
                    "display": scenario.display,
                }]
            },
            "quantity": {"value": 1},
        }],
    }
    if supporting_info:
        claim["supportingInfo"] = supporting_info

    return {
        "resourceType": "Bundle",
        "id": f"pas-bundle-{uuid4().hex[:8]}",
        "meta": {
            "profile": [
                "http://hl7.org/fhir/us/davinci-pas/StructureDefinition/profile-pas-request-bundle"
            ]
        },
        "type": "collection",
        "entry": [
            {"resource": claim},
            {"resource": {"resourceType": "Patient",      "id": fixture_ids.patient}},
            {"resource": {"resourceType": "Coverage",     "id": fixture_ids.coverage}},
            {"resource": {"resourceType": "Practitioner", "id": fixture_ids.practitioner}},
            {"resource": {"resourceType": "Organization", "id": fixture_ids.payer}},
        ],
    }


async def submit_prior_auth(
    fixture_ids: FixtureIds,
    scenario: Scenario,
    pas_base_url: str,
    qr_reference: str | None = None,
) -> dict:
    """Submit PA request; polls $inquire up to 3× if payer responds Pended."""
    bundle = build_pas_bundle(fixture_ids, scenario, qr_reference)

    async with httpx.AsyncClient(base_url=pas_base_url, timeout=30.0) as client:
        r = await client.post(
            "/fhir/r4/Claim/$submit",
            json=bundle,
            headers={"Content-Type": "application/fhir+json"},
        )
        r.raise_for_status()
        claim_response = r.json()

    if claim_response.get("disposition") == PASDispo.PENDED.value:
        for _ in range(3):
            await asyncio.sleep(settings.pend_delay_seconds)
            async with httpx.AsyncClient(base_url=pas_base_url, timeout=30.0) as client:
                r = await client.post(
                    "/fhir/r4/Claim/$inquire",
                    json=bundle,
                    headers={"Content-Type": "application/fhir+json"},
                )
                r.raise_for_status()
                claim_response = r.json()
            if claim_response.get("disposition") != PASDispo.PENDED.value:
                break

    return claim_response
