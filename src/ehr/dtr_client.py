"""EHR-side DTR 2.1.0 client — fetches Questionnaire and submits QuestionnaireResponse."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import httpx

_DTR_QR_PROFILE = (
    "http://hl7.org/fhir/us/davinci-dtr/StructureDefinition/dtr-questionnaireresponse-r4"
)

_AUTO_ANSWERS_BY_LINK: dict[str, dict] = {
    "1": {"valueBoolean": True},
    "2": {"valueString": "M54.5"},
    "3": {"valueString": "1234567890"},
    "4": {"valueInteger": 30},
}

_TYPE_FALLBACK: dict[str, dict] = {
    "boolean": {"valueBoolean": True},
    "string": {"valueString": "auto"},
    "integer": {"valueInteger": 1},
}


def _extract_questionnaire_url(smart_launch_url: str) -> str:
    parsed = urlparse(smart_launch_url)
    params = parse_qs(parsed.query)
    raw = params.get("appContext", [None])[0]
    if raw:
        return json.loads(raw)["questionnaire"]
    raise ValueError(f"No appContext with questionnaire URL in: {smart_launch_url}")


def _build_qr(questionnaire_url: str, items: list[dict]) -> dict:
    answered = []
    for item in items:
        link_id = item["linkId"]
        answer = _AUTO_ANSWERS_BY_LINK.get(link_id) or _TYPE_FALLBACK.get(item.get("type", "string"), {"valueString": "auto"})
        answered.append({"linkId": link_id, "answer": [answer]})
    return {
        "resourceType": "QuestionnaireResponse",
        "meta": {"profile": [_DTR_QR_PROFILE]},
        "questionnaire": questionnaire_url,
        "status": "completed",
        "item": answered,
    }


async def run_dtr(smart_launch_url: str, dtr_base_url: str) -> str:
    """Complete DTR flow in automated mode. Returns 'QuestionnaireResponse/<id>'."""
    questionnaire_url = _extract_questionnaire_url(smart_launch_url)

    async with httpx.AsyncClient(base_url=dtr_base_url) as client:
        path = questionnaire_url.replace(dtr_base_url.rstrip("/"), "") or "/fhir/r4/Questionnaire/pa-auth-q"
        r = await client.get(path)
        r.raise_for_status()
        questionnaire = r.json()

    qr = _build_qr(questionnaire_url, questionnaire.get("item", []))

    async with httpx.AsyncClient(base_url=dtr_base_url) as client:
        r = await client.post(
            "/fhir/r4/QuestionnaireResponse",
            json=qr,
            headers={"Content-Type": "application/fhir+json"},
        )
        r.raise_for_status()
        result = r.json()

    return f"QuestionnaireResponse/{result['id']}"
