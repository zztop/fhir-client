"""Integration tests for the PAS 2.1.0 Claim stub server."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.payer.pas_server import app

BASE = "http://test"


@pytest.fixture
def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE)


def _bundle(code: str, system: str) -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Claim",
                    "status": "active",
                    "use": "preauthorization",
                    "patient": {"reference": "Patient/test-patient-001"},
                    "item": [{
                        "sequence": 1,
                        "productOrService": {
                            "coding": [{"system": system, "code": code}]
                        },
                    }],
                }
            },
            {"resource": {"resourceType": "Patient", "id": "test-patient-001"}},
        ],
    }


# ── Claim/$submit ─────────────────────────────────────────────────────────────

async def test_submit_pa_required_granted(client: AsyncClient) -> None:
    async with client as c:
        r = await c.post("/fhir/r4/Claim/$submit", json=_bundle("1049502", "http://www.nlm.nih.gov/research/umls/rxnorm"))
    assert r.status_code == 200
    assert r.json()["disposition"] == "Granted"


async def test_submit_pa_required_has_auth_number(client: AsyncClient) -> None:
    async with client as c:
        r = await c.post("/fhir/r4/Claim/$submit", json=_bundle("1049502", "http://www.nlm.nih.gov/research/umls/rxnorm"))
    ext_items = r.json()["extension"][0]["extension"]
    auth = next((e["valueString"] for e in ext_items if e["url"] == "number"), None)
    assert auth is not None


async def test_submit_pa_not_required_granted(client: AsyncClient) -> None:
    async with client as c:
        r = await c.post("/fhir/r4/Claim/$submit", json=_bundle("85025", "http://www.ama-assn.org/go/cpt"))
    assert r.json()["disposition"] == "Granted"


async def test_submit_auth_pending_pended(client: AsyncClient) -> None:
    async with client as c:
        r = await c.post("/fhir/r4/Claim/$submit", json=_bundle("33533", "http://www.ama-assn.org/go/cpt"))
    assert r.json()["disposition"] == "Pended"


async def test_submit_unknown_code_defaults_granted(client: AsyncClient) -> None:
    async with client as c:
        r = await c.post("/fhir/r4/Claim/$submit", json=_bundle("UNKNOWN-9999", "http://example.org"))
    assert r.json()["disposition"] == "Granted"


async def test_submit_returns_claim_response_type(client: AsyncClient) -> None:
    async with client as c:
        r = await c.post("/fhir/r4/Claim/$submit", json=_bundle("1049502", "http://www.nlm.nih.gov/research/umls/rxnorm"))
    data = r.json()
    assert data["resourceType"] == "ClaimResponse"
    assert "id" in data


async def test_submit_has_pas_profile(client: AsyncClient) -> None:
    async with client as c:
        r = await c.post("/fhir/r4/Claim/$submit", json=_bundle("1049502", "http://www.nlm.nih.gov/research/umls/rxnorm"))
    profiles = r.json()["meta"]["profile"]
    assert any("profile-claimresponse" in p for p in profiles)


async def test_submit_use_preauthorization(client: AsyncClient) -> None:
    async with client as c:
        r = await c.post("/fhir/r4/Claim/$submit", json=_bundle("1049502", "http://www.nlm.nih.gov/research/umls/rxnorm"))
    assert r.json()["use"] == "preauthorization"


async def test_submit_pended_outcome_queued(client: AsyncClient) -> None:
    async with client as c:
        r = await c.post("/fhir/r4/Claim/$submit", json=_bundle("33533", "http://www.ama-assn.org/go/cpt"))
    assert r.json()["outcome"] == "queued"


# ── Claim/$inquire ────────────────────────────────────────────────────────────

async def test_inquire_always_granted(client: AsyncClient) -> None:
    async with client as c:
        r = await c.post("/fhir/r4/Claim/$inquire", json=_bundle("33533", "http://www.ama-assn.org/go/cpt"))
    assert r.status_code == 200
    assert r.json()["disposition"] == "Granted"


async def test_inquire_has_auth_number(client: AsyncClient) -> None:
    async with client as c:
        r = await c.post("/fhir/r4/Claim/$inquire", json=_bundle("33533", "http://www.ama-assn.org/go/cpt"))
    ext_items = r.json()["extension"][0]["extension"]
    auth = next((e["valueString"] for e in ext_items if e["url"] == "number"), None)
    assert auth is not None
