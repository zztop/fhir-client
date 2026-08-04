"""Build a plain informational instructions card."""
from __future__ import annotations

from src.config import settings


def build(message: str) -> dict:
    return {
        "summary":   message,
        "indicator": "info",
        "source": {
            "label": "Stub Payer CRD Service",
            "url":   settings.payer_cds_base_url,
        },
    }
