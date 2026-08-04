"""Validate each FHIR R4B fixture file parses cleanly with fhir.resources 7.x.

fhir.resources 7.x implements FHIR R4B. Python attribute names use camelCase
(matching the JSON wire format) rather than snake_case.
"""

import json
from pathlib import Path

from fhir.resources.coverage import Coverage
from fhir.resources.encounter import Encounter
from fhir.resources.organization import Organization
from fhir.resources.patient import Patient
from fhir.resources.practitioner import Practitioner

FIXTURES = Path(__file__).parents[2] / "src" / "fhir" / "fixtures"


def load(filename: str) -> dict:
    with (FIXTURES / filename).open() as fh:
        return json.load(fh)


# ── Patient ───────────────────────────────────────────────────────────────────

def test_patient_fixture_parses():
    data = load("patient.json")
    patient = Patient.model_validate(data)
    assert patient.id == "test-patient-001"
    assert patient.gender == "female"
    assert patient.birthDate is not None  # camelCase in fhir.resources 7.x
    assert len(patient.name) == 1
    assert patient.name[0].family == "TestPatient"


def test_patient_has_mrn_identifier():
    data = load("patient.json")
    patient = Patient.model_validate(data)
    assert patient.identifier, "Patient must have at least one identifier"
    assert patient.identifier[0].value == "MRN-001"


# ── Organization ──────────────────────────────────────────────────────────────

def test_organization_fixture_parses():
    data = load("organization.json")
    org = Organization.model_validate(data)
    assert org.id == "test-payer-001"
    assert org.name == "Stub Payer Inc."


def test_organization_is_payer_type():
    data = load("organization.json")
    org = Organization.model_validate(data)
    codes = [c.code for t in (org.type or []) for c in (t.coding or [])]
    assert "pay" in codes


# ── Practitioner ──────────────────────────────────────────────────────────────

def test_practitioner_fixture_parses():
    data = load("practitioner.json")
    prac = Practitioner.model_validate(data)
    assert prac.id == "test-practitioner-001"
    assert prac.name[0].family == "TestDoctor"


def test_practitioner_has_npi():
    data = load("practitioner.json")
    prac = Practitioner.model_validate(data)
    npi_ids = [
        i for i in (prac.identifier or []) if i.system == "http://hl7.org/fhir/sid/us-npi"
    ]
    assert len(npi_ids) == 1
    assert npi_ids[0].value == "1234567890"


# ── Coverage ──────────────────────────────────────────────────────────────────

def test_coverage_fixture_parses():
    data = load("coverage.json")
    cov = Coverage.model_validate(data)
    assert cov.id == "test-coverage-001"
    assert cov.status == "active"


def test_coverage_references_patient_and_insurer():
    # R4B: payor → insurer (single Reference); subscriberId → list of Identifiers
    data = load("coverage.json")
    cov = Coverage.model_validate(data)
    assert cov.beneficiary.reference == "Patient/test-patient-001"
    assert cov.insurer.reference == "Organization/test-payer-001"


def test_coverage_subscriber_id_present():
    data = load("coverage.json")
    cov = Coverage.model_validate(data)
    # R4B subscriberId is List[Identifier]
    assert cov.subscriberId and len(cov.subscriberId) > 0
    assert cov.subscriberId[0].value == "MEM-12345"


def test_coverage_has_group_and_plan_classes():
    data = load("coverage.json")
    cov = Coverage.model_validate(data)
    # R4B: class → class_fhir (Python attr); value is Identifier
    class_codes = [c.type.coding[0].code for c in (cov.class_fhir or [])]
    assert "group" in class_codes
    assert "plan" in class_codes


# ── Encounter ─────────────────────────────────────────────────────────────────

def test_encounter_fixture_parses():
    data = load("encounter.json")
    enc = Encounter.model_validate(data)
    assert enc.id == "test-encounter-001"
    assert enc.status == "in-progress"


def test_encounter_references_patient():
    data = load("encounter.json")
    enc = Encounter.model_validate(data)
    assert enc.subject.reference == "Patient/test-patient-001"


def test_encounter_references_practitioner():
    # R4B: participant.individual → participant.actor
    data = load("encounter.json")
    enc = Encounter.model_validate(data)
    actors = [p.actor.reference for p in (enc.participant or []) if p.actor]
    assert "Practitioner/test-practitioner-001" in actors


def test_encounter_has_class():
    # R4B: class is a List[CodeableConcept], not a single Coding
    data = load("encounter.json")
    enc = Encounter.model_validate(data)
    codes = [c.coding[0].code for c in (enc.class_fhir or []) if c.coding]
    assert "AMB" in codes


def test_encounter_has_actual_period():
    # R4B: period → actualPeriod
    data = load("encounter.json")
    enc = Encounter.model_validate(data)
    assert enc.actualPeriod is not None
    assert enc.actualPeriod.start is not None
