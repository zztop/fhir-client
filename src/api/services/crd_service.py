"""CRD service: build a hook context, fire it at the payer CDS stub, and
extract the PA signal (pa_needed, smart_url) from the response cards.
"""
from __future__ import annotations

from typing import Any

import httpx

from src.hooks.appointment_book import build_appointment_book_context
from src.hooks.base import resolve_scenario
from src.hooks.order_select import build_order_select_context
from src.hooks.order_sign import build_order_sign_context
from src.models.pas import FixtureIds

_BUILDERS = {
    "order-sign": build_order_sign_context,
    "order-select": build_order_select_context,
    "appointment-book": build_appointment_book_context,
}

_SERVICE_IDS = {
    "order-sign": "crd-order-sign",
    "order-select": "crd-order-select",
    "appointment-book": "crd-appointment-book",
}


async def fire_crd(
    hook: str,
    scenario_key: str,
    fhir_base_url: str,
    payer_cds_base_url: str,
) -> tuple[dict[str, Any], dict[str, Any], bool, str | None]:
    """Build the hook context, POST it to the payer CDS stub, and extract the
    PA signal from the response.

    Returns (hook_request, raw_response, pa_needed, smart_url).
    """
    if hook not in _BUILDERS:
        raise ValueError(f"Unknown hook '{hook}'. Valid hooks: {sorted(_BUILDERS)}")

    scenario = resolve_scenario(scenario_key)
    fixture_ids = FixtureIds()
    hook_request = await _BUILDERS[hook](fixture_ids, scenario, fhir_base_url)

    service_id = _SERVICE_IDS[hook]
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{payer_cds_base_url}/cds-services/{service_id}",
            json=hook_request,
        )
        resp.raise_for_status()
        raw_response = resp.json()

    pa_needed = False
    smart_url: str | None = None
    for card in raw_response.get("cards", []):
        extension = card.get("extension") or {}
        coverage_info = extension.get("davinci-crd.coverage-information")
        if coverage_info:
            pa_needed = bool(coverage_info[0].get("pa-needed", False))
        if smart_url is None:
            for link in card.get("links", []):
                if link.get("type") == "smart":
                    smart_url = link.get("url")
                    if link.get("appContext"):
                        smart_url = f"{smart_url}?appContext={link['appContext']}"
                    break

    return hook_request, raw_response, pa_needed, smart_url
