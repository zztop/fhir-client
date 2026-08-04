"""Bootstrap the HAPI FHIR R4 server with test fixtures.

Call wait_for_fhir() first, then bootstrap_fixtures() to PUT all synthetic
resources. Returns a FixtureIds instance whose fields are the stable resource IDs.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import structlog

from src.models.pas import FixtureIds

logger = structlog.get_logger()

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Load order matters: Organization must exist before Coverage references it,
# Patient before Coverage and Encounter, Practitioner before Encounter.
_LOAD_ORDER: list[tuple[str, str, str]] = [
    ("organization.json", "Organization", "test-payer-001"),
    ("patient.json", "Patient", "test-patient-001"),
    ("practitioner.json", "Practitioner", "test-practitioner-001"),
    ("coverage.json", "Coverage", "test-coverage-001"),
    ("encounter.json", "Encounter", "test-encounter-001"),
]


def _read_fixture(filename: str) -> dict:
    path = FIXTURES_DIR / filename
    with path.open() as fh:
        return json.load(fh)


async def wait_for_fhir(
    fhir_base_url: str,
    *,
    retries: int = 20,
    delay: float = 3.0,
) -> None:
    """Poll HAPI FHIR /metadata until the server is ready."""
    metadata_url = f"{fhir_base_url}/metadata"
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(1, retries + 1):
            try:
                resp = await client.get(metadata_url)
                if resp.status_code == 200:
                    logger.info("fhir_server_ready", url=fhir_base_url)
                    return
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            logger.info("waiting_for_fhir", attempt=attempt, of=retries)
            await asyncio.sleep(delay)
    raise RuntimeError(
        f"FHIR server at {fhir_base_url} did not become ready after {retries} attempts"
    )


async def bootstrap_fixtures(fhir_base_url: str) -> FixtureIds:
    """PUT each fixture into HAPI FHIR using its deterministic resource ID.

    Returns the stable FixtureIds so callers can build FHIR references.
    """
    headers = {
        "Content-Type": "application/fhir+json",
        "Accept": "application/fhir+json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        for filename, resource_type, resource_id in _LOAD_ORDER:
            data = _read_fixture(filename)
            url = f"{fhir_base_url}/{resource_type}/{resource_id}"
            resp = await client.put(url, json=data, headers=headers)
            resp.raise_for_status()
            logger.info(
                "fixture_loaded",
                resource_type=resource_type,
                resource_id=resource_id,
                status=resp.status_code,
            )

    return FixtureIds()


async def fetch_resource(fhir_base_url: str, relative_url: str) -> dict:
    """GET a single resource or search result from HAPI FHIR.

    relative_url examples:
      "Patient/test-patient-001"
      "Coverage?patient=test-patient-001&status=active"
    """
    url = f"{fhir_base_url}/{relative_url}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            url,
            headers={"Accept": "application/fhir+json"},
        )
        resp.raise_for_status()
        return resp.json()
