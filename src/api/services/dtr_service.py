"""DTR service: fetch questionnaires, detect static vs adaptive mode, drive the
adaptive $next-question protocol, and submit the final QuestionnaireResponse.
"""
from __future__ import annotations

from typing import Any, Literal

import httpx

from src.ehr.dtr_client import _extract_questionnaire_url

_ADAPTIVE_PROFILE = "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-adapt"
_DTR_QR_PROFILE = "http://hl7.org/fhir/us/davinci-dtr/StructureDefinition/dtr-questionnaireresponse-r4"


def detect_mode(questionnaire_json: dict[str, Any]) -> Literal["static", "adaptive"]:
    profiles = questionnaire_json.get("meta", {}).get("profile", [])
    return "adaptive" if _ADAPTIVE_PROFILE in profiles else "static"


async def fetch_questionnaire(smart_url: str, dtr_base_url: str) -> dict[str, Any]:
    """Extract the questionnaire URL from a SMART launch URL and GET it."""
    questionnaire_url = _extract_questionnaire_url(smart_url)
    path = (
        questionnaire_url.replace(dtr_base_url.rstrip("/"), "")
        or "/fhir/r4/Questionnaire/pa-auth-q"
    )
    async with httpx.AsyncClient(base_url=dtr_base_url, timeout=15.0) as client:
        resp = await client.get(path)
        resp.raise_for_status()
        questionnaire: dict[str, Any] = resp.json()
        return questionnaire


async def call_next_question(
    answered_items: list[dict[str, Any]],
    questionnaire_url: str,
    dtr_base_url: str,
) -> tuple[dict[str, Any] | None, bool]:
    """POST the answered items so far to $next-question.

    Returns (current_question, done) — current_question is None when done.
    """
    body = {
        "resourceType": "QuestionnaireResponse",
        "status": "in-progress",
        "item": answered_items,
    }
    async with httpx.AsyncClient(base_url=dtr_base_url, timeout=15.0) as client:
        resp = await client.post("/fhir/r4/Questionnaire/$next-question", json=body)
        resp.raise_for_status()
        data = resp.json()

    if data.get("status") == "completed":
        return None, True

    contained = data.get("contained", [])
    current_question = contained[0]["item"][0] if contained else None
    return current_question, False


async def build_and_submit_qr(
    answered_items: list[dict[str, Any]],
    questionnaire_url: str,
    dtr_base_url: str,
) -> str:
    """Build a DTR-profiled QuestionnaireResponse, submit it, and return its reference."""
    qr = {
        "resourceType": "QuestionnaireResponse",
        "meta": {"profile": [_DTR_QR_PROFILE]},
        "questionnaire": questionnaire_url,
        "status": "completed",
        "item": answered_items,
    }
    async with httpx.AsyncClient(base_url=dtr_base_url, timeout=15.0) as client:
        resp = await client.post(
            "/fhir/r4/QuestionnaireResponse",
            json=qr,
            headers={"Content-Type": "application/fhir+json"},
        )
        resp.raise_for_status()
        result = resp.json()
    return f"QuestionnaireResponse/{result['id']}"
