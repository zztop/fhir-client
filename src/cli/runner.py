"""Workflow orchestrator — wires fixture loading, hook firing, and card display."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass

import httpx
import structlog

from src.config import settings
from src.ehr.dtr_client import run_dtr
from src.ehr.pas_submitter import submit_prior_auth
from src.fhir.server import wait_for_fhir, bootstrap_fixtures
from src.hooks.base import resolve_scenario
from src.hooks.order_sign import build_order_sign_context
from src.hooks.order_select import build_order_select_context
from src.hooks.appointment_book import build_appointment_book_context
from src.models.cds_hooks import CDSHookResponse
from src.models.pas import FixtureIds, Scenario

logger = structlog.get_logger()

# Clinical trigger order — determines run sequence when multiple hooks selected
_HOOK_ORDER = ["order-select", "order-sign", "appointment-book"]


@dataclass
class HarnessConfig:
    hooks:        list[str]
    scenario_key: str
    payer_mode:   str  # "stub (local)" | "external (from .env)"


async def _build_context(
    hook: str,
    fixture_ids: FixtureIds,
    scenario: Scenario,
    fhir_base_url: str,
) -> dict:
    match hook:
        case "order-sign":
            return await build_order_sign_context(fixture_ids, scenario, fhir_base_url)
        case "order-select":
            return await build_order_select_context(fixture_ids, scenario, fhir_base_url)
        case "appointment-book":
            return await build_appointment_book_context(fixture_ids, scenario, fhir_base_url)
        case _:
            raise ValueError(f"Unknown hook: {hook}")


async def _fire_hook(hook: str, context: dict, payer_cds_base: str) -> CDSHookResponse:
    url = f"{payer_cds_base}/cds-services/crd-{hook}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url, json=context, headers={"Content-Type": "application/json"}
        )
        resp.raise_for_status()
    return CDSHookResponse.model_validate(resp.json())


def _find_smart_launch_url(response: CDSHookResponse) -> str | None:
    for card in response.cards:
        for link in card.links:
            if link.type == "smart":
                url = link.url
                if link.appContext:
                    url = f"{url}?appContext={link.appContext}"
                return url
    return None


def _is_pa_needed(response: CDSHookResponse) -> bool:
    for card in response.cards:
        if card.extension:
            info = card.extension.get("davinci-crd.coverage-information", [])
            if info and info[0].get("pa-needed"):
                return True
    return False


def _print_cards(hook: str, scenario_key: str, response: CDSHookResponse) -> None:
    ICONS = {"info": "ℹ", "warning": "⚠", "critical": "✖"}
    print(f"
{'═'*57}")
    print(f"  Hook: {hook:<20} Scenario: {scenario_key}")
    print(f"{'─'*57}")
    if not response.cards:
        print("  (no cards returned)")
    for card in response.cards:
        icon = ICONS.get(card.indicator, "?")
        print(f"  [{icon}] {card.summary}")
        for link in card.links:
            print(f"       → {link.label}: {link.url}")
    print(f"{'═'*57}")


async def run(config: HarnessConfig) -> None:
    await wait_for_fhir(settings.fhir_base_url)
    fixture_ids = await bootstrap_fixtures(settings.fhir_base_url)
    scenario    = resolve_scenario(config.scenario_key)
    payer_base  = settings.payer_cds_base_url  # same for stub and external in .env

    ordered_hooks = [h for h in _HOOK_ORDER if h in config.hooks]
    for hook in ordered_hooks:
        ctx      = await _build_context(hook, fixture_ids, scenario, settings.fhir_base_url)
        response = await _fire_hook(hook, ctx, payer_base)
        _print_cards(hook, config.scenario_key, response)

        # DTR
        qr_reference: str | None = None
        smart_url = _find_smart_launch_url(response)
        if smart_url:
            print("\n  [DTR] Launching documentation form…")
            qr_reference = await run_dtr(smart_url, settings.payer_dtr_base_url)
            print(f"  [DTR] QuestionnaireResponse submitted ✓  ({qr_reference})")

        # PAS
        if _is_pa_needed(response):
            print("\n  [PAS] Submitting prior authorization…")
            cr = await submit_prior_auth(
                fixture_ids, scenario, settings.payer_pas_base_url, qr_reference
            )
            dispo = cr.get("disposition", "unknown")
            ext_items = cr.get("extension", [{}])[0].get("extension", [])
            auth = next((e.get("valueString") for e in ext_items if e.get("url") == "number"), None)
            print(f"  [PAS] disposition: {dispo}")
            if auth:
                print(f"  [PAS] auth number: {auth}")
