"""Unit tests for the EHR-side DTR 2.1.0 client."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ehr.dtr_client import _build_qr, _extract_questionnaire_url, run_dtr

_Q_URL = "http://localhost:3002/fhir/r4/Questionnaire/pa-auth-q"

_QUESTIONNAIRE = {
    "resourceType": "Questionnaire",
    "id": "pa-auth-q",
    "url": _Q_URL,
    "status": "active",
    "item": [
        {"linkId": "1", "text": "Medically necessary?", "type": "boolean", "required": True},
        {"linkId": "2", "text": "ICD-10 code", "type": "string", "required": True},
        {"linkId": "3", "text": "Physician NPI", "type": "string", "required": True},
        {"linkId": "4", "text": "Quantity", "type": "integer", "required": True},
    ],
}

_SMART_LAUNCH_URL = (
    f"http://localhost:3002/smart/launch"
    f"?appContext={json.dumps({'questionnaire': _Q_URL})}"
)


# ── _extract_questionnaire_url ────────────────────────────────────────────────

def test_extract_url_from_smart_launch() -> None:
    url = _extract_questionnaire_url(_SMART_LAUNCH_URL)
    assert url == _Q_URL


def test_extract_url_missing_app_context_raises() -> None:
    with pytest.raises(ValueError, match="No appContext"):
        _extract_questionnaire_url("http://localhost:3002/smart/launch")


# ── _build_qr ─────────────────────────────────────────────────────────────────

def test_build_qr_resource_type() -> None:
    qr = _build_qr(_Q_URL, _QUESTIONNAIRE["item"])
    assert qr["resourceType"] == "QuestionnaireResponse"


def test_build_qr_status_completed() -> None:
    qr = _build_qr(_Q_URL, _QUESTIONNAIRE["item"])
    assert qr["status"] == "completed"


def test_build_qr_has_four_items() -> None:
    qr = _build_qr(_Q_URL, _QUESTIONNAIRE["item"])
    assert len(qr["item"]) == 4


def test_build_qr_item_1_boolean() -> None:
    qr = _build_qr(_Q_URL, _QUESTIONNAIRE["item"])
    item1 = next(i for i in qr["item"] if i["linkId"] == "1")
    assert item1["answer"][0]["valueBoolean"] is True


def test_build_qr_item_3_npi() -> None:
    qr = _build_qr(_Q_URL, _QUESTIONNAIRE["item"])
    item3 = next(i for i in qr["item"] if i["linkId"] == "3")
    assert item3["answer"][0]["valueString"] == "1234567890"


def test_build_qr_dtr_profile() -> None:
    qr = _build_qr(_Q_URL, _QUESTIONNAIRE["item"])
    profiles = qr["meta"]["profile"]
    assert any("dtr-questionnaireresponse-r4" in p for p in profiles)


# ── run_dtr ───────────────────────────────────────────────────────────────────

def _make_response(json_data: dict, status_code: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data
    r.raise_for_status = MagicMock()
    return r


async def test_run_dtr_returns_qr_reference() -> None:
    get_resp = _make_response(_QUESTIONNAIRE)
    post_resp = _make_response({"id": "qr-test-001", "status": "completed", "resourceType": "QuestionnaireResponse"})

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=get_resp)
    mock_client.post = AsyncMock(return_value=post_resp)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("src.ehr.dtr_client.httpx.AsyncClient", return_value=mock_cm):
        result = await run_dtr(_SMART_LAUNCH_URL, "http://localhost:3002")

    assert result == "QuestionnaireResponse/qr-test-001"


async def test_run_dtr_posts_qr_with_all_items() -> None:
    get_resp = _make_response(_QUESTIONNAIRE)
    post_resp = _make_response({"id": "qr-abc", "status": "completed", "resourceType": "QuestionnaireResponse"})

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=get_resp)
    mock_client.post = AsyncMock(return_value=post_resp)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("src.ehr.dtr_client.httpx.AsyncClient", return_value=mock_cm):
        await run_dtr(_SMART_LAUNCH_URL, "http://localhost:3002")

    posted_body = mock_client.post.call_args.kwargs["json"]
    assert len(posted_body["item"]) == 4
    assert posted_body["status"] == "completed"
