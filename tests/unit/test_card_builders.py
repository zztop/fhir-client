"""Unit tests for CRD 2.1.0 card builder functions."""
from __future__ import annotations

import json

from src.payer.cards import coverage_info, form_completion, instructions

_COV_REF = "Coverage/test-coverage-001"


# ── coverage_info ─────────────────────────────────────────────────────────────

def test_coverage_info_pa_required_summary() -> None:
    assert "Prior Authorization" in coverage_info.build(pa_needed=True, coverage_ref=_COV_REF)["summary"]


def test_coverage_info_pa_required_indicator_warning() -> None:
    assert coverage_info.build(pa_needed=True, coverage_ref=_COV_REF)["indicator"] == "warning"


def test_coverage_info_pa_not_required_indicator_info() -> None:
    assert coverage_info.build(pa_needed=False, coverage_ref=_COV_REF)["indicator"] == "info"


def test_coverage_info_has_extension_key() -> None:
    card = coverage_info.build(pa_needed=True, coverage_ref=_COV_REF)
    assert "davinci-crd.coverage-information" in card["extension"]


def test_coverage_info_ext_pa_needed_true() -> None:
    ext = coverage_info.build(pa_needed=True, coverage_ref=_COV_REF)["extension"]["davinci-crd.coverage-information"][0]
    assert ext["pa-needed"] is True


def test_coverage_info_ext_pa_needed_false() -> None:
    ext = coverage_info.build(pa_needed=False, coverage_ref=_COV_REF)["extension"]["davinci-crd.coverage-information"][0]
    assert ext["pa-needed"] is False


def test_coverage_info_ext_coverage_ref() -> None:
    ext = coverage_info.build(pa_needed=True, coverage_ref=_COV_REF)["extension"]["davinci-crd.coverage-information"][0]
    assert ext["coverage"]["reference"] == _COV_REF


def test_coverage_info_ext_date_present() -> None:
    ext = coverage_info.build(pa_needed=True, coverage_ref=_COV_REF)["extension"]["davinci-crd.coverage-information"][0]
    assert "date" in ext


def test_coverage_info_ext_doc_needed_clinical_when_pa() -> None:
    ext = coverage_info.build(pa_needed=True, coverage_ref=_COV_REF)["extension"]["davinci-crd.coverage-information"][0]
    assert ext["doc-needed"] == "clinical"


def test_coverage_info_ext_doc_needed_no_when_no_pa() -> None:
    ext = coverage_info.build(pa_needed=False, coverage_ref=_COV_REF)["extension"]["davinci-crd.coverage-information"][0]
    assert ext["doc-needed"] == "no"


# ── form_completion ───────────────────────────────────────────────────────────

def test_form_completion_has_smart_link() -> None:
    card = form_completion.build()
    assert any(lnk["type"] == "smart" for lnk in card["links"])


def test_form_completion_app_context_has_questionnaire() -> None:
    card = form_completion.build()
    smart = next(lnk for lnk in card["links"] if lnk["type"] == "smart")
    ctx = json.loads(smart["appContext"])
    assert "questionnaire" in ctx


def test_form_completion_indicator_warning() -> None:
    assert form_completion.build()["indicator"] == "warning"


# ── instructions ──────────────────────────────────────────────────────────────

def test_instructions_no_extension() -> None:
    assert "extension" not in instructions.build("Test")


def test_instructions_indicator_info() -> None:
    assert instructions.build("Test")["indicator"] == "info"


def test_instructions_summary_matches_message() -> None:
    assert instructions.build("Hello world")["summary"] == "Hello world"
