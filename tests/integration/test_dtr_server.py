"""Integration tests for the DTR 2.1.0 Questionnaire stub server."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.payer.dtr_server import app

BASE = "http://test"


@pytest.fixture
def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE)


# ── GET Questionnaire ─────────────────────────────────────────────────────────

async def test_get_questionnaire_ok(client: AsyncClient) -> None:
    async with client as c:
        r = await c.get("/fhir/r4/Questionnaire/pa-auth-q")
    assert r.status_code == 200


async def test_get_questionnaire_resource_type(client: AsyncClient) -> None:
    async with client as c:
        r = await c.get("/fhir/r4/Questionnaire/pa-auth-q")
    assert r.json()["resourceType"] == "Questionnaire"


async def test_get_questionnaire_has_four_items(client: AsyncClient) -> None:
    async with client as c:
        r = await c.get("/fhir/r4/Questionnaire/pa-auth-q")
    assert len(r.json()["item"]) == 4


async def test_get_questionnaire_dtr_profile(client: AsyncClient) -> None:
    async with client as c:
        r = await c.get("/fhir/r4/Questionnaire/pa-auth-q")
    profiles = r.json()["meta"]["profile"]
    assert any("dtr-questionnaire-r4" in p for p in profiles)


async def test_get_questionnaire_not_found(client: AsyncClient) -> None:
    async with client as c:
        r = await c.get("/fhir/r4/Questionnaire/nonexistent-q")
    assert r.status_code == 404


# ── POST $next-question ───────────────────────────────────────────────────────

async def test_next_question_first_item(client: AsyncClient) -> None:
    body = {"resourceType": "QuestionnaireResponse", "status": "in-progress", "item": []}
    async with client as c:
        r = await c.post("/fhir/r4/Questionnaire/$next-question", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "in-progress"
    assert data["contained"][0]["item"][0]["linkId"] == "1"


async def test_next_question_advances_index(client: AsyncClient) -> None:
    body = {
        "resourceType": "QuestionnaireResponse",
        "status": "in-progress",
        "item": [{"linkId": "1", "answer": [{"valueBoolean": True}]}],
    }
    async with client as c:
        r = await c.post("/fhir/r4/Questionnaire/$next-question", json=body)
    data = r.json()
    assert data["contained"][0]["item"][0]["linkId"] == "2"


async def test_next_question_completed_when_all_answered(client: AsyncClient) -> None:
    answered = [
        {"linkId": "1", "answer": [{"valueBoolean": True}]},
        {"linkId": "2", "answer": [{"valueString": "M54.5"}]},
        {"linkId": "3", "answer": [{"valueString": "1234567890"}]},
        {"linkId": "4", "answer": [{"valueInteger": 30}]},
    ]
    body = {"resourceType": "QuestionnaireResponse", "status": "in-progress", "item": answered}
    async with client as c:
        r = await c.post("/fhir/r4/Questionnaire/$next-question", json=body)
    assert r.json()["status"] == "completed"


# ── POST QuestionnaireResponse ────────────────────────────────────────────────

async def test_submit_qr_ok(client: AsyncClient) -> None:
    body = {
        "resourceType": "QuestionnaireResponse",
        "questionnaire": "http://localhost:3002/fhir/r4/Questionnaire/pa-auth-q",
        "status": "completed",
        "item": [{"linkId": "1", "answer": [{"valueBoolean": True}]}],
    }
    async with client as c:
        r = await c.post("/fhir/r4/QuestionnaireResponse", json=body)
    assert r.status_code == 200


async def test_submit_qr_returns_completed_status(client: AsyncClient) -> None:
    body = {
        "resourceType": "QuestionnaireResponse",
        "questionnaire": "http://localhost:3002/fhir/r4/Questionnaire/pa-auth-q",
        "status": "completed",
        "item": [{"linkId": "1", "answer": [{"valueBoolean": True}]}],
    }
    async with client as c:
        r = await c.post("/fhir/r4/QuestionnaireResponse", json=body)
    data = r.json()
    assert data["status"] == "completed"
    assert "id" in data


async def test_submit_qr_has_dtr_profile(client: AsyncClient) -> None:
    body = {
        "resourceType": "QuestionnaireResponse",
        "questionnaire": "http://localhost:3002/fhir/r4/Questionnaire/pa-auth-q",
        "status": "completed",
        "item": [{"linkId": "1", "answer": [{"valueBoolean": True}]}],
    }
    async with client as c:
        r = await c.post("/fhir/r4/QuestionnaireResponse", json=body)
    profiles = r.json()["meta"]["profile"]
    assert any("dtr-questionnaireresponse-r4" in p for p in profiles)


async def test_submit_qr_without_items_returns_422(client: AsyncClient) -> None:
    body = {
        "resourceType": "QuestionnaireResponse",
        "questionnaire": "http://localhost:3002/fhir/r4/Questionnaire/pa-auth-q",
        "status": "completed",
        "item": [],
    }
    async with client as c:
        r = await c.post("/fhir/r4/QuestionnaireResponse", json=body)
    assert r.status_code == 422
