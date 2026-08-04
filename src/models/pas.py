"""PAS 2.1.0 request/response helpers, shared enums, and runtime types."""
from __future__ import annotations
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field


class PASDispo(StrEnum):
    GRANTED = "Granted"
    DENIED  = "Denied"
    PENDED  = "Pended"


class ReviewActionCode(StrEnum):
    APPROVED = "A1"
    PARTIAL  = "A2"
    DENIED   = "A3"
    PENDED   = "A4"


class ReviewAction(BaseModel):
    code:   ReviewActionCode
    reason: str | None = None
    number: str | None = None

    def to_extension(self) -> dict[str, Any]:
        ext: dict[str, Any] = {
            "url": "http://hl7.org/fhir/us/davinci-pas/StructureDefinition/extension-reviewAction",
            "extension": [{
                "url": "code",
                "valueCodeableConcept": {"coding": [{
                    "system": "https://valueset.x12.org/x217/005010/response/2000F/HCR/1/01/00/306",
                    "code": self.code.value,
                }]},
            }],
        }
        if self.number:
            ext["extension"].append({"url": "number", "valueString": self.number})
        return ext


class FixtureIds(BaseModel):
    patient:      str = "test-patient-001"
    coverage:     str = "test-coverage-001"
    practitioner: str = "test-practitioner-001"
    payer:        str = "test-payer-001"
    encounter:    str = "test-encounter-001"


class Scenario(BaseModel):
    code:           str
    system:         str
    scenario:       str
    display:        str
    order_resource: str = "ServiceRequest"  # MedicationRequest | ServiceRequest
