"""Extract the order/appointment code from a CDS Hook body and map it to a Scenario."""
from __future__ import annotations

import json
from pathlib import Path

from src.models.pas import Scenario

_SCENARIOS_FILE = Path(__file__).parent / "scenarios.json"
_by_code: dict[str, Scenario] | None = None


def _load() -> dict[str, Scenario]:
    global _by_code
    if _by_code is None:
        raw = json.loads(_SCENARIOS_FILE.read_text())
        _by_code = {item["code"]: Scenario.model_validate(item) for item in raw}
    return _by_code


def _extract_code(body: dict) -> str | None:
    ctx = body.get("context", {})

    # order-sign / order-select  ──  draftOrders bundle
    for entry in ctx.get("draftOrders", {}).get("entry", []):
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType", "")
        if rtype == "MedicationRequest":
            codings = (
                resource.get("medication", {})
                        .get("concept", {})
                        .get("coding", [])
            )
        elif rtype == "ServiceRequest":
            codings = (
                resource.get("code", {})
                        .get("concept", {})
                        .get("coding", [])
            )
        else:
            codings = []
        if codings:
            return codings[0].get("code")

    # appointment-book  ──  appointments bundle
    for entry in ctx.get("appointments", {}).get("entry", []):
        resource = entry.get("resource", {})
        service_types = resource.get("serviceType", [])
        if service_types:
            codings = service_types[0].get("concept", {}).get("coding", [])
            if codings:
                return codings[0].get("code")

    return None


def route(body: dict) -> Scenario | None:
    """Return the matching Scenario for the order/appointment code, or None."""
    code = _extract_code(body)
    return _load().get(code) if code else None
