"""Utility endpoints: health, scenario/hook catalogs, fixture bootstrap."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import structlog
from fastapi import APIRouter

from src.api.db import get_db
from src.config import settings
from src.fhir.server import bootstrap_fixtures

logger = structlog.get_logger()

router = APIRouter(prefix="/api", tags=["utility"])

_SCENARIOS_FILE = Path(__file__).parents[2] / "payer" / "scenarios.json"

_EXPECTED_OUTCOMES = {
    "pa-required": "PA Required → Granted",
    "pa-not-required": "No Prior Auth Needed",
    "auth-pending": "Pended → Granted (via $inquire)",
}

_HOOKS = [
    {
        "id": "order-sign",
        "title": "Order Signing",
        "description": "Signed medication/procedure orders with full clinical context",
    },
    {
        "id": "order-select",
        "title": "Order Selection",
        "description": "Pre-sign selection without authoredOn timestamp",
    },
    {
        "id": "appointment-book",
        "title": "Appointment Booking",
        "description": "Uses FHIR Appointment resource (CPT codes)",
    },
]


@router.get("/health")
async def health() -> dict:
    fhir_reachable = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.fhir_base_url}/metadata")
            fhir_reachable = resp.status_code == 200
    except httpx.HTTPError:
        fhir_reachable = False

    sqlite_connected = False
    try:
        async with get_db() as db:
            await db.execute("SELECT 1")
            sqlite_connected = True
    except Exception:
        sqlite_connected = False

    return {"fhir_reachable": fhir_reachable, "sqlite_connected": sqlite_connected}


@router.get("/scenarios")
async def list_scenarios() -> list[dict]:
    raw = json.loads(_SCENARIOS_FILE.read_text())
    return [
        {
            "key": item["scenario"],
            "code": item["code"],
            "system": item["system"],
            "display": item["display"],
            "expected_outcome": _EXPECTED_OUTCOMES.get(item["scenario"], ""),
        }
        for item in raw
    ]


@router.get("/hooks")
async def list_hooks() -> list[dict]:
    return _HOOKS


@router.post("/bootstrap")
async def bootstrap() -> dict:
    fixture_ids = await bootstrap_fixtures(settings.fhir_base_url)
    logger.info("bootstrap_complete")
    return {"status": "ok", "fixture_ids": fixture_ids.model_dump()}
