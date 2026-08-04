"""Runtime FHIR resource and CDS Hook response validation."""
from __future__ import annotations

from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.coverage import Coverage
from fhir.resources.R4B.encounter import Encounter
from fhir.resources.R4B.organization import Organization
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.practitioner import Practitioner

_REGISTRY: dict[str, type] = {
    "Patient":      Patient,
    "Coverage":     Coverage,
    "Encounter":    Encounter,
    "Practitioner": Practitioner,
    "Organization": Organization,
    "Bundle":       Bundle,
}


def validate_resource(resource: dict) -> None:
    """Validate a FHIR resource dict against its fhir.resources R4B Pydantic model.

    Raises ValueError for unsupported types, pydantic.ValidationError for structural issues.
    """
    rtype = resource.get("resourceType")
    cls = _REGISTRY.get(rtype)  # type: ignore[arg-type]
    if cls is None:
        raise ValueError(f"Unsupported resourceType for validation: {rtype!r}")
    cls.model_validate(resource)


def validate_cds_response(response: dict) -> None:
    """Validate CDS Hook 2.0 response structure (cards required fields + indicator enum)."""
    if "cards" not in response:
        raise ValueError("CDS response missing required 'cards' field")
    valid_indicators = {"info", "warning", "critical"}
    for i, card in enumerate(response["cards"]):
        missing = {"summary", "indicator", "source"} - set(card.keys())
        if missing:
            raise ValueError(f"Card {i} missing required fields: {missing}")
        if card["indicator"] not in valid_indicators:
            raise ValueError(
                f"Card {i} has invalid indicator '{card['indicator']}'; "
                f"must be one of {valid_indicators}"
            )
