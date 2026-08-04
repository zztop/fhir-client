"""Build a CRD 2.1.0 coverage-information card."""
from __future__ import annotations

from datetime import date

from src.config import settings


def build(*, pa_needed: bool, coverage_ref: str) -> dict:
    return {
        "summary": (
            "Prior Authorization Required"
            if pa_needed
            else "No Prior Authorization Required"
        ),
        "indicator": "warning" if pa_needed else "info",
        "source": {
            "label": "Stub Payer CRD Service",
            "url": settings.payer_cds_base_url,
        },
        "extension": {
            "davinci-crd.coverage-information": [{
                "coverage":               {"reference": coverage_ref},
                "covered":                "covered",
                "pa-needed":              pa_needed,
                "doc-needed":             "clinical" if pa_needed else "no",
                "doc-purpose":            ["prior-auth"] if pa_needed else [],
                "coverage-assertion-ids": ["ASSERT-001"],
                "date":                   date.today().isoformat(),
            }],
        },
    }
