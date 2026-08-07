"""Unit tests for the EHR API utility endpoints.

Uses httpx ASGITransport — no running server, real SQLite file, or network
call required. External calls (HAPI FHIR, aiosqlite, bootstrap_fixtures) are
mocked.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.models.pas import FixtureIds

BASE = "http://test"


@pytest.fixture
def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE)


def _mock_fhir_response(status_code: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    client_instance = AsyncMock()
    client_instance.get.return_value = resp
    ctx = AsyncMock()
    ctx.__aenter__.return_value = client_instance
    return ctx


@asynccontextmanager
async def _fake_get_db_ok():
    db = AsyncMock()
    yield db


@asynccontextmanager
async def _fake_get_db_broken():
    raise RuntimeError("no db")
    yield  # pragma: no cover


# ── /api/health ───────────────────────────────────────────────────────────────

async def test_health_reports_reachable_and_connected(client: AsyncClient) -> None:
    with (
        patch("src.api.routers.utility.httpx.AsyncClient", return_value=_mock_fhir_response(200)),
        patch("src.api.routers.utility.get_db", _fake_get_db_ok),
    ):
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"fhir_reachable": True, "sqlite_connected": True}


async def test_health_reports_unreachable_fhir_and_broken_db(client: AsyncClient) -> None:
    with (
        patch("src.api.routers.utility.httpx.AsyncClient", return_value=_mock_fhir_response(500)),
        patch("src.api.routers.utility.get_db", _fake_get_db_broken),
    ):
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"fhir_reachable": False, "sqlite_connected": False}


# ── /api/scenarios ───────────────────────────────────────────────────────────

async def test_list_scenarios_returns_three_scenarios(client: AsyncClient) -> None:
    resp = await client.get("/api/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert {s["key"] for s in body} == {"pa-required", "pa-not-required", "auth-pending"}
    for scenario in body:
        assert scenario["expected_outcome"]


# ── /api/hooks ───────────────────────────────────────────────────────────────

async def test_list_hooks_returns_three_hooks(client: AsyncClient) -> None:
    resp = await client.get("/api/hooks")
    assert resp.status_code == 200
    body = resp.json()
    assert {h["id"] for h in body} == {"order-sign", "order-select", "appointment-book"}


# ── /api/bootstrap ───────────────────────────────────────────────────────────

async def test_bootstrap_calls_fixture_loader(client: AsyncClient) -> None:
    with patch(
        "src.api.routers.utility.bootstrap_fixtures",
        AsyncMock(return_value=FixtureIds()),
    ) as mock_bootstrap:
        resp = await client.post("/api/bootstrap")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    mock_bootstrap.assert_awaited_once()
