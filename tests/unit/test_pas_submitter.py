"""Unit tests for the EHR-side PAS 2.1.0 submitter."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ehr.pas_submitter import build_pas_bundle, submit_prior_auth
from src.models.pas import FixtureIds, Scenario

_IDS = FixtureIds()

_SCENARIO_PA = Scenario(
    code="1049502",
    system="http://www.nlm.nih.gov/research/umls/rxnorm",
    scenario="pa-required",
    display="Oxycodone 5mg",
    order_resource="MedicationRequest",
)
_SCENARIO_PENDED = Scenario(
    code="33533",
    system="http://www.ama-assn.org/go/cpt",
    scenario="auth-pending",
    display="CABG, arterial, single",
    order_resource="ServiceRequest",
)


# ── build_pas_bundle ──────────────────────────────────────────────────────────

def test_bundle_resource_type() -> None:
    b = build_pas_bundle(_IDS, _SCENARIO_PA)
    assert b["resourceType"] == "Bundle"


def test_bundle_has_claim_entry() -> None:
    types = [e["resource"]["resourceType"] for e in build_pas_bundle(_IDS, _SCENARIO_PA)["entry"]]
    assert "Claim" in types


def test_bundle_has_patient_entry() -> None:
    types = [e["resource"]["resourceType"] for e in build_pas_bundle(_IDS, _SCENARIO_PA)["entry"]]
    assert "Patient" in types


def test_bundle_claim_use_preauthorization() -> None:
    b = build_pas_bundle(_IDS, _SCENARIO_PA)
    claim = next(e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Claim")
    assert claim["use"] == "preauthorization"


def test_bundle_claim_code_matches_scenario() -> None:
    b = build_pas_bundle(_IDS, _SCENARIO_PA)
    claim = next(e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Claim")
    assert claim["item"][0]["productOrService"]["coding"][0]["code"] == "1049502"


def test_bundle_with_qr_adds_supporting_info() -> None:
    b = build_pas_bundle(_IDS, _SCENARIO_PA, qr_reference="QuestionnaireResponse/qr-001")
    claim = next(e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Claim")
    assert "supportingInfo" in claim
    assert claim["supportingInfo"][0]["valueReference"]["reference"] == "QuestionnaireResponse/qr-001"


def test_bundle_without_qr_no_supporting_info() -> None:
    b = build_pas_bundle(_IDS, _SCENARIO_PA)
    claim = next(e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Claim")
    assert "supportingInfo" not in claim


def test_bundle_has_pas_profile() -> None:
    b = build_pas_bundle(_IDS, _SCENARIO_PA)
    assert any("profile-pas-request-bundle" in p for p in b["meta"]["profile"])


# ── submit_prior_auth ─────────────────────────────────────────────────────────

def _mock_http(json_data: dict) -> AsyncMock:
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()

    client = AsyncMock()
    client.post = AsyncMock(return_value=resp)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


async def test_submit_returns_disposition() -> None:
    cr = {"disposition": "Granted", "resourceType": "ClaimResponse"}
    with patch("src.ehr.pas_submitter.httpx.AsyncClient", return_value=_mock_http(cr)):
        result = await submit_prior_auth(_IDS, _SCENARIO_PA, "http://localhost:3003")
    assert result["disposition"] == "Granted"


async def test_submit_pended_polls_inquire() -> None:
    pended = {"disposition": "Pended", "resourceType": "ClaimResponse"}
    granted = {"disposition": "Granted", "resourceType": "ClaimResponse"}

    call_count = 0

    def make_cm(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _mock_http(pended if call_count == 1 else granted)

    with patch("src.ehr.pas_submitter.httpx.AsyncClient", side_effect=make_cm):
        with patch("src.ehr.pas_submitter.asyncio.sleep", new_callable=AsyncMock):
            result = await submit_prior_auth(_IDS, _SCENARIO_PENDED, "http://localhost:3003")

    assert result["disposition"] == "Granted"
    assert call_count == 2
