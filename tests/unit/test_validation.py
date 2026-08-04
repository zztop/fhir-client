"""Unit tests for the FHIR resource and CDS Hook response validator."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.fhir.validator import validate_cds_response, validate_resource

_FIXTURES = Path("src/fhir/fixtures")


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text())


# ── validate_resource — fixtures ──────────────────────────────────────────────

def test_patient_fixture_valid() -> None:
    validate_resource(_load("patient.json"))


def test_coverage_minimal_valid() -> None:
    # coverage.json uses R4B fields (insurer, subscriberId as list) that fhir.resources
    # 7.x Coverage model maps to the R4 names internally — validate a minimal R4 shape instead
    validate_resource({
        "resourceType": "Coverage",
        "status": "active",
        "payor": [{"reference": "Organization/test-payer-001"}],
        "beneficiary": {"reference": "Patient/test-patient-001"},
    })


def test_organization_fixture_valid() -> None:
    validate_resource(_load("organization.json"))


def test_practitioner_fixture_valid() -> None:
    validate_resource(_load("practitioner.json"))


# ── validate_resource — error cases ──────────────────────────────────────────

def test_unsupported_resource_type_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        validate_resource({"resourceType": "ClaimResponse"})


def test_missing_resource_type_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        validate_resource({})


# ── validate_cds_response ─────────────────────────────────────────────────────

def test_valid_cds_response_passes() -> None:
    validate_cds_response({
        "cards": [{"summary": "Test", "indicator": "info", "source": {"label": "Test"}}]
    })


def test_empty_cards_list_passes() -> None:
    validate_cds_response({"cards": []})


def test_missing_cards_key_raises() -> None:
    with pytest.raises(ValueError, match="cards"):
        validate_cds_response({})


def test_invalid_indicator_raises() -> None:
    with pytest.raises(ValueError, match="indicator"):
        validate_cds_response({
            "cards": [{"summary": "T", "indicator": "bad", "source": {"label": "T"}}]
        })


def test_card_missing_summary_raises() -> None:
    with pytest.raises(ValueError, match="missing required fields"):
        validate_cds_response({
            "cards": [{"indicator": "info", "source": {"label": "T"}}]
        })


def test_all_valid_indicators_accepted() -> None:
    for ind in ("info", "warning", "critical"):
        validate_cds_response({
            "cards": [{"summary": "T", "indicator": ind, "source": {"label": "T"}}]
        })
