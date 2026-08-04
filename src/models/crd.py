"""CRD 2.1.0 card extension models.

Field names match the Da Vinci CRD IG extension keys (hyphens preserved via aliases).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FHIRReference(BaseModel):
    reference: str


class CoverageInformation(BaseModel):
    """Single entry in the davinci-crd.coverage-information extension array."""

    coverage: FHIRReference
    covered: Literal["covered", "not-covered", "conditional"]
    pa_needed: bool = Field(alias="pa-needed")
    doc_needed: Literal["clinical", "admin", "patient", "no"] = Field(alias="doc-needed")
    doc_purpose: list[str] = Field(default_factory=list, alias="doc-purpose")
    info_needed: str | None = Field(default=None, alias="info-needed")
    coverage_assertion_ids: list[str] = Field(
        default_factory=list, alias="coverage-assertion-ids"
    )
    satisfied_pa_codes: list[str] = Field(default_factory=list, alias="satisfied-pa-codes")
    date: str  # ISO date (YYYY-MM-DD)

    model_config = {"populate_by_name": True}

    def to_extension_dict(self) -> dict:
        """Serialize using hyphenated aliases for the wire format."""
        return self.model_dump(by_alias=True, exclude_none=True)


class CRDCoverageExtension(BaseModel):
    """Top-level extension block added to a CRD coverage-information card."""

    coverage_information: list[CoverageInformation] = Field(
        default_factory=list, alias="davinci-crd.coverage-information"
    )

    model_config = {"populate_by_name": True}

    def to_extension_dict(self) -> dict:
        return {
            "davinci-crd.coverage-information": [
                ci.to_extension_dict() for ci in self.coverage_information
            ]
        }
