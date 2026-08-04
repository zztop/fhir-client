"""Shared helpers for all CDS Hook context builders."""

from __future__ import annotations

import json
from pathlib import Path

from src.fhir.server import fetch_resource
from src.models.pas import FixtureIds, Scenario

_SCENARIOS_FILE = Path(__file__).parents[1] / "payer" / "scenarios.json"
_cache: dict[str, Scenario] | None = None


def _load() -> dict[str, Scenario]:
    global _cache
    if _cache is None:
        raw = json.loads(_SCENARIOS_FILE.read_text())
        _cache = {item["scenario"]: Scenario.model_validate(item) for item in raw}
    return _cache


def resolve_scenario(key: str) -> Scenario:
    scenarios = _load()
    if key not in scenarios:
        raise ValueError(f"Unknown scenario '{key}'. Valid keys: {sorted(scenarios)}")
    return scenarios[key]


async def build_prefetch(fhir_base_url: str, fixture_ids: FixtureIds) -> dict:
    """Resolve prefetch resources from HAPI FHIR and embed them inline."""
    patient = await fetch_resource(fhir_base_url, f"Patient/{fixture_ids.patient}")
    coverage = await fetch_resource(
        fhir_base_url,
        f"Coverage?patient={fixture_ids.patient}&status=active",
    )
    return {"patient": patient, "coverage": coverage}
