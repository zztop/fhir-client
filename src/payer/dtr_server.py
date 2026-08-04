"""Da Vinci DTR 2.1.0 stub — Questionnaire server."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request

app = FastAPI(title="Da Vinci DTR Stub — DTR 2.1.0")

_FIXTURES = Path(__file__).parent.parent / "fhir" / "fixtures"


def _load_questionnaire(questionnaire_id: str) -> dict:
    path = _FIXTURES / "questionnaire.json"
    q = json.loads(path.read_text())
    if q.get("id") != questionnaire_id:
        raise FileNotFoundError
    return q


@app.get("/fhir/r4/Questionnaire/{questionnaire_id}")
def get_questionnaire(questionnaire_id: str) -> dict:
    try:
        return _load_questionnaire(questionnaire_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Questionnaire/{questionnaire_id} not found")


@app.post("/fhir/r4/Questionnaire/$next-question")
async def next_question(request: Request) -> dict:
    body = await request.json()
    answered_items: list = body.get("item", [])
    answered_count = len(answered_items)

    q = _load_questionnaire("pa-auth-q")
    all_items: list = q["item"]

    if answered_count >= len(all_items):
        return {
            "resourceType": "QuestionnaireResponse",
            "questionnaire": q["url"],
            "status": "completed",
            "item": answered_items,
        }

    next_item = all_items[answered_count]
    return {
        "resourceType": "QuestionnaireResponse",
        "questionnaire": q["url"],
        "status": "in-progress",
        "item": answered_items,
        "contained": [
            {
                "resourceType": "Questionnaire",
                "item": [next_item],
            }
        ],
    }


@app.post("/fhir/r4/QuestionnaireResponse")
async def submit_response(request: Request) -> dict:
    body = await request.json()
    if not body.get("item"):
        raise HTTPException(status_code=422, detail="QuestionnaireResponse must include at least one item")
    return {
        "resourceType": "QuestionnaireResponse",
        "id": str(uuid4()),
        "meta": {
            "profile": [
                "http://hl7.org/fhir/us/davinci-dtr/StructureDefinition/dtr-questionnaireresponse-r4"
            ]
        },
        "questionnaire": body.get("questionnaire", ""),
        "status": "completed",
        "item": body.get("item", []),
    }
