"""Build a CRD 2.1.0 request-form-completion card (SMART DTR launch)."""
from __future__ import annotations

import json

from src.config import settings


def build() -> dict:
    questionnaire_url = (
        f"{settings.payer_dtr_base_url}/fhir/r4/Questionnaire/pa-auth-q"
    )
    return {
        "summary": "Complete Prior Authorization Documentation",
        "indicator": "warning",
        "source": {
            "label": "Stub Payer CRD Service",
            "url": settings.payer_cds_base_url,
        },
        "links": [{
            "label":      "Launch Documentation Requirements (DTR)",
            "url":        f"{settings.payer_dtr_base_url}/smart/launch",
            "type":       "smart",
            "appContext": json.dumps({"questionnaire": questionnaire_url}),
        }],
    }
