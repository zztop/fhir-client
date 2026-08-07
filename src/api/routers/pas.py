"""PAS bundle review + submission endpoints."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.db import get_db
from src.api.services.pas_service import (
    apply_edits,
    inquire_bundle,
    prepare_bundle,
    submit_bundle,
)
from src.config import settings

router = APIRouter(prefix="/api/sessions/{session_id}/pas", tags=["pas"])


class BundleEdits(BaseModel):
    diagnosis_code: str | None = None
    service_code: str | None = None
    service_system: str | None = None
    quantity: int | None = None
    priority: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def _require_session_row(db: Any, session_id: str) -> Any:
    cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return row


async def _require_pas_row(db: Any, session_id: str) -> Any:
    cursor = await db.execute("SELECT * FROM pas_submissions WHERE session_id = ?", (session_id,))
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="PAS bundle not prepared for this session")
    return row


@router.post("/prepare")
async def prepare(session_id: str) -> dict:
    async with get_db() as db:
        session_row = await _require_session_row(db, session_id)
        cursor = await db.execute(
            "SELECT qr_reference FROM questionnaire_sessions WHERE session_id = ?", (session_id,)
        )
        qr_row = await cursor.fetchone()

    qr_reference = qr_row["qr_reference"] if qr_row else None
    bundle_json = await prepare_bundle(session_row["scenario_key"], qr_reference)
    pas_id = str(uuid4())
    now = _now()

    async with get_db() as db:
        await db.execute(
            "INSERT INTO pas_submissions (id, session_id, bundle_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            (pas_id, session_id, bundle_json, now),
        )
        await db.execute(
            "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
            ("pas_reviewing", now, session_id),
        )
        await db.commit()

    return {"id": pas_id, "bundle": json.loads(bundle_json)}


@router.get("/bundle")
async def get_bundle(session_id: str) -> dict:
    async with get_db() as db:
        row = await _require_pas_row(db, session_id)
    return {"bundle": json.loads(row["bundle_json"])}


@router.patch("/bundle")
async def patch_bundle(session_id: str, body: BundleEdits) -> dict:
    async with get_db() as db:
        row = await _require_pas_row(db, session_id)
        new_bundle_json = apply_edits(row["bundle_json"], body.model_dump())
        await db.execute(
            "UPDATE pas_submissions SET bundle_json = ? WHERE session_id = ?",
            (new_bundle_json, session_id),
        )
        await db.commit()
    return {"bundle": json.loads(new_bundle_json)}


@router.post("/submit")
async def submit(session_id: str) -> dict:
    async with get_db() as db:
        row = await _require_pas_row(db, session_id)
        result = await submit_bundle(row["bundle_json"], settings.payer_pas_base_url)

        now = _now()
        await db.execute(
            "UPDATE pas_submissions "
            "SET claim_response = ?, disposition = ?, auth_number = ?, submitted_at = ? "
            "WHERE session_id = ?",
            (
                json.dumps(result["claim_response"]),
                result["disposition"],
                result["auth_number"],
                now,
                session_id,
            ),
        )
        await db.execute(
            "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
            (result["disposition"].lower(), now, session_id),
        )
        await db.commit()

    return result


@router.post("/inquire")
async def inquire(session_id: str) -> dict:
    async with get_db() as db:
        row = await _require_pas_row(db, session_id)
        result = await inquire_bundle(row["bundle_json"], settings.payer_pas_base_url)

        now = _now()
        await db.execute(
            "UPDATE pas_submissions SET claim_response = ?, disposition = ?, auth_number = ? "
            "WHERE session_id = ?",
            (
                json.dumps(result["claim_response"]),
                result["disposition"],
                result["auth_number"],
                session_id,
            ),
        )
        await db.execute(
            "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
            (result["disposition"].lower(), now, session_id),
        )
        await db.commit()

    return result
