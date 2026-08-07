"""PAS service: build the default Claim bundle, apply reviewer edits, and
submit/inquire against the payer PAS stub.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from src.ehr.pas_submitter import build_pas_bundle
from src.hooks.base import resolve_scenario
from src.models.pas import FixtureIds, PASDispo

_ICD10_SYSTEM = "http://hl7.org/fhir/sid/icd-10-cm"


async def prepare_bundle(scenario_key: str, qr_reference: str | None) -> str:
    """Build the default PAS bundle for a scenario and return it as JSON."""
    scenario = resolve_scenario(scenario_key)
    bundle = build_pas_bundle(FixtureIds(), scenario, qr_reference)
    return json.dumps(bundle)


def _find_claim(bundle: dict[str, Any]) -> dict[str, Any]:
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Claim":
            claim: dict[str, Any] = resource
            return claim
    raise ValueError("Bundle has no Claim entry")


def apply_edits(bundle_json: str, edits: dict[str, Any]) -> str:
    """Merge editable field overrides into the stored bundle. Unset (None) fields
    are left unchanged."""
    bundle: dict[str, Any] = json.loads(bundle_json)
    claim = _find_claim(bundle)

    if edits.get("diagnosis_code") is not None:
        claim["diagnosis"] = [{
            "sequence": 1,
            "diagnosisCodeableConcept": {
                "coding": [{"system": _ICD10_SYSTEM, "code": edits["diagnosis_code"]}]
            },
        }]

    coding = claim["item"][0]["productOrService"]["coding"][0]
    if edits.get("service_code") is not None:
        coding["code"] = edits["service_code"]
    if edits.get("service_system") is not None:
        coding["system"] = edits["service_system"]

    if edits.get("quantity") is not None:
        claim["item"][0]["quantity"] = {"value": edits["quantity"]}

    if edits.get("priority") is not None:
        claim["priority"] = {"coding": [{"code": edits["priority"]}]}

    return json.dumps(bundle)


def _parse_claim_response(claim_response: dict[str, Any]) -> tuple[str, str | None]:
    disposition = claim_response.get("disposition", PASDispo.GRANTED.value)
    auth_number: str | None = None
    for ext in claim_response.get("extension", []):
        for sub in ext.get("extension", []):
            if sub.get("url") == "number":
                auth_number = sub.get("valueString")
    return disposition, auth_number


async def _post_claim(bundle: dict[str, Any], path: str, pas_base_url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=pas_base_url, timeout=30.0) as client:
        resp = await client.post(
            path, json=bundle, headers={"Content-Type": "application/fhir+json"}
        )
        resp.raise_for_status()
        claim_response: dict[str, Any] = resp.json()
    return claim_response


async def submit_bundle(bundle_json: str, pas_base_url: str) -> dict[str, Any]:
    """POST the bundle to PAS $submit. Returns disposition, auth_number, claim_response."""
    bundle = json.loads(bundle_json)
    claim_response = await _post_claim(bundle, "/fhir/r4/Claim/$submit", pas_base_url)
    disposition, auth_number = _parse_claim_response(claim_response)
    return {
        "disposition": disposition,
        "auth_number": auth_number,
        "claim_response": claim_response,
    }


async def inquire_bundle(bundle_json: str, pas_base_url: str) -> dict[str, Any]:
    """POST the bundle to PAS $inquire. Returns disposition, auth_number, claim_response."""
    bundle = json.loads(bundle_json)
    claim_response = await _post_claim(bundle, "/fhir/r4/Claim/$inquire", pas_base_url)
    disposition, auth_number = _parse_claim_response(claim_response)
    return {
        "disposition": disposition,
        "auth_number": auth_number,
        "claim_response": claim_response,
    }
