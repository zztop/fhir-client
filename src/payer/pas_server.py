"""Da Vinci PAS 2.1.0 stub — Claim/$submit + Claim/$inquire."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

from fastapi import FastAPI, Request

from src.models.pas import PASDispo, ReviewAction, ReviewActionCode

app = FastAPI(title="Da Vinci PAS Stub — PAS 2.1.0")

# code → (scenario_name, disposition, auth_number)
_SCENARIO_MAP: dict[str, tuple[str, PASDispo, str | None]] = {
    "1049502": ("pa-required",     PASDispo.GRANTED, "AUTH-2026-0803-001"),
    "85025":   ("pa-not-required", PASDispo.GRANTED, None),
    "33533":   ("auth-pending",    PASDispo.PENDED,  None),
}


def _extract_claim_code(body: dict) -> str | None:
    for entry in body.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Claim":
            items = resource.get("item", [])
            if items:
                codings = items[0].get("productOrService", {}).get("coding", [])
                if codings:
                    return codings[0].get("code")
    return None


def _patient_ref(body: dict) -> str:
    for entry in body.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Claim":
            return resource.get("patient", {}).get("reference", "Patient/test-patient-001")
    return "Patient/test-patient-001"


def _build_claim_response(
    disposition: PASDispo,
    patient_ref: str,
    auth_number: str | None = None,
) -> dict:
    if disposition == PASDispo.GRANTED:
        review = ReviewAction(code=ReviewActionCode.APPROVED, number=auth_number)
        outcome = "complete"
    elif disposition == PASDispo.DENIED:
        review = ReviewAction(code=ReviewActionCode.DENIED)
        outcome = "complete"
    else:
        review = ReviewAction(code=ReviewActionCode.PENDED)
        outcome = "queued"

    return {
        "resourceType": "ClaimResponse",
        "id": str(uuid4()),
        "meta": {
            "profile": [
                "http://hl7.org/fhir/us/davinci-pas/StructureDefinition/profile-claimresponse"
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
        "patient":  {"reference": patient_ref},
        "created":  date.today().isoformat(),
        "insurer":  {"reference": "Organization/test-payer-001"},
        "outcome":  outcome,
        "disposition": disposition.value,
        "item": [{
            "itemSequence": 1,
            "adjudication": [{
                "category": {"coding": [{"code": "submitted"}]},
                "amount":   {"value": 0, "currency": "USD"},
            }],
        }],
        "extension": [review.to_extension()],
    }


@app.post("/fhir/r4/Claim/$submit")
async def claim_submit(request: Request) -> dict:
    body = await request.json()
    code = _extract_claim_code(body)
    _, disposition, auth_number = _SCENARIO_MAP.get(
        code or "", ("unknown", PASDispo.GRANTED, None)
    )
    return _build_claim_response(disposition, _patient_ref(body), auth_number)


@app.post("/fhir/r4/Claim/$inquire")
async def claim_inquire(request: Request) -> dict:
    body = await request.json()
    return _build_claim_response(
        PASDispo.GRANTED,
        _patient_ref(body),
        auth_number="AUTH-2026-0803-INQ",
    )
