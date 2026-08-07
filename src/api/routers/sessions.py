"""Session CRUD + CRD trigger endpoints."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.db import get_db
from src.api.services.crd_service import fire_crd
from src.config import settings

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    hook: Literal["order-sign", "order-select", "appointment-book"]
    scenario_key: Literal["pa-required", "pa-not-required", "auth-pending"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _crd_result_dict(row: Any) -> dict | None:
    if row is None:
        return None
    raw_response = json.loads(row["raw_response"])
    return {
        "id": row["id"],
        "cards": raw_response.get("cards", []),
        "hook_request": json.loads(row["hook_request"]),
        "raw_response": raw_response,
        "pa_needed": bool(row["pa_needed"]),
        "smart_url": row["smart_url"],
    }


def _questionnaire_dict(row: Any) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "questionnaire_url": row["questionnaire_url"],
        "questionnaire_json": json.loads(row["questionnaire_json"]),
        "mode": row["mode"],
        "answered_items": json.loads(row["answered_items"]),
        "qr_reference": row["qr_reference"],
        "submitted_at": row["submitted_at"],
    }


def _pas_dict(row: Any) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "bundle_json": json.loads(row["bundle_json"]),
        "claim_response": json.loads(row["claim_response"]) if row["claim_response"] else None,
        "disposition": row["disposition"],
        "auth_number": row["auth_number"],
        "submitted_at": row["submitted_at"],
    }


@router.get("")
async def list_sessions() -> list[dict]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT s.id, s.hook, s.scenario_key, s.status, s.created_at, s.updated_at,
                   p.disposition
            FROM sessions s
            LEFT JOIN pas_submissions p ON p.session_id = s.id
            ORDER BY s.created_at DESC
            """
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


@router.post("")
async def create_session(body: CreateSessionRequest) -> dict:
    try:
        hook_request, raw_response, pa_needed, smart_url = await fire_crd(
            body.hook, body.scenario_key, settings.fhir_base_url, settings.payer_cds_base_url
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session_id = str(uuid4())
    crd_result_id = str(uuid4())
    now = _now()
    status = "crd_complete"

    async with get_db() as db:
        await db.execute(
            "INSERT INTO sessions (id, created_at, hook, scenario_key, status, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, now, body.hook, body.scenario_key, status, now),
        )
        await db.execute(
            "INSERT INTO crd_results "
            "(id, session_id, hook_request, raw_response, pa_needed, smart_url, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                crd_result_id,
                session_id,
                json.dumps(hook_request),
                json.dumps(raw_response),
                int(pa_needed),
                smart_url,
                now,
            ),
        )
        await db.commit()

    return {
        "session": {
            "id": session_id,
            "hook": body.hook,
            "scenario_key": body.scenario_key,
            "status": status,
            "created_at": now,
            "updated_at": now,
        },
        "crd_result": {
            "id": crd_result_id,
            "cards": raw_response.get("cards", []),
            "pa_needed": pa_needed,
            "smart_url": smart_url,
        },
    }


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session_row = await cursor.fetchone()
        if session_row is None:
            raise HTTPException(status_code=404, detail="Session not found")

        cursor = await db.execute("SELECT * FROM crd_results WHERE session_id = ?", (session_id,))
        crd_row = await cursor.fetchone()

        cursor = await db.execute(
            "SELECT * FROM questionnaire_sessions WHERE session_id = ?", (session_id,)
        )
        questionnaire_row = await cursor.fetchone()

        cursor = await db.execute(
            "SELECT * FROM pas_submissions WHERE session_id = ?", (session_id,)
        )
        pas_row = await cursor.fetchone()

    return {
        "session": dict(session_row),
        "crd_result": _crd_result_dict(crd_row),
        "questionnaire_session": _questionnaire_dict(questionnaire_row),
        "pas_submission": _pas_dict(pas_row),
    }


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict:
    async with get_db() as db:
        cursor = await db.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found")
        await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await db.commit()
    return {"status": "deleted"}
