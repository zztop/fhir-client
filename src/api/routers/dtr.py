"""DTR questionnaire endpoints — static and adaptive flows."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.db import get_db
from src.api.services.dtr_service import (
    build_and_submit_qr,
    call_next_question,
    detect_mode,
    fetch_questionnaire,
)
from src.config import settings

router = APIRouter(prefix="/api/sessions/{session_id}/dtr", tags=["dtr"])


class AnsweredItem(BaseModel):
    linkId: str
    answer: list[dict[str, Any]]


class SubmitRequest(BaseModel):
    items: list[AnsweredItem] | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def _require_session(db: Any, session_id: str) -> None:
    cursor = await db.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if await cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="Session not found")


async def _require_questionnaire_row(db: Any, session_id: str) -> Any:
    cursor = await db.execute(
        "SELECT * FROM questionnaire_sessions WHERE session_id = ?", (session_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="DTR not started for this session")
    return row


@router.post("/start")
async def start_dtr(session_id: str) -> dict:
    async with get_db() as db:
        await _require_session(db, session_id)
        cursor = await db.execute(
            "SELECT smart_url FROM crd_results WHERE session_id = ?", (session_id,)
        )
        crd_row = await cursor.fetchone()

    if crd_row is None or not crd_row["smart_url"]:
        raise HTTPException(status_code=400, detail="No DTR launch available for this session")

    smart_url = crd_row["smart_url"]
    questionnaire_json = await fetch_questionnaire(smart_url, settings.payer_dtr_base_url)
    mode = detect_mode(questionnaire_json)
    questionnaire_url = questionnaire_json["url"]
    now = _now()

    answered_items: list[dict] = []
    current_question: dict | None = None
    if mode == "adaptive":
        current_question, _ = await call_next_question(
            answered_items, questionnaire_url, settings.payer_dtr_base_url
        )

    async with get_db() as db:
        await db.execute(
            "INSERT INTO questionnaire_sessions "
            "(id, session_id, questionnaire_url, questionnaire_json, mode, answered_items, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid4()),
                session_id,
                questionnaire_url,
                json.dumps(questionnaire_json),
                mode,
                json.dumps(answered_items),
                now,
            ),
        )
        await db.execute(
            "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
            ("dtr_in_progress", now, session_id),
        )
        await db.commit()

    if mode == "static":
        return {"mode": mode, "questions": questionnaire_json.get("item", [])}
    return {"mode": mode, "current_question": current_question, "answered_count": 0}


@router.get("")
async def get_dtr_state(session_id: str) -> dict:
    async with get_db() as db:
        row = await _require_questionnaire_row(db, session_id)

    questionnaire_json = json.loads(row["questionnaire_json"])
    answered_items = json.loads(row["answered_items"])
    mode = row["mode"]

    if mode == "static":
        return {
            "mode": mode,
            "questions": questionnaire_json.get("item", []),
            "answered_items": answered_items,
        }

    current_question, done = await call_next_question(
        answered_items, row["questionnaire_url"], settings.payer_dtr_base_url
    )
    return {
        "mode": mode,
        "current_question": current_question,
        "done": done,
        "answered_items": answered_items,
    }


@router.post("/next")
async def next_question(session_id: str, body: AnsweredItem) -> dict:
    async with get_db() as db:
        row = await _require_questionnaire_row(db, session_id)

        if row["mode"] != "adaptive":
            raise HTTPException(status_code=400, detail="Session is not in adaptive mode")

        answered_items = json.loads(row["answered_items"])
        answered_items.append(body.model_dump())

        current_question, done = await call_next_question(
            answered_items, row["questionnaire_url"], settings.payer_dtr_base_url
        )

        await db.execute(
            "UPDATE questionnaire_sessions SET answered_items = ? WHERE session_id = ?",
            (json.dumps(answered_items), session_id),
        )
        await db.commit()

    return {
        "done": done,
        "current_question": current_question,
        "answered_count": len(answered_items),
    }


@router.post("/submit")
async def submit_dtr(session_id: str, body: SubmitRequest | None = None) -> dict:
    async with get_db() as db:
        row = await _require_questionnaire_row(db, session_id)

        if row["mode"] == "static":
            if body is None or body.items is None:
                raise HTTPException(status_code=400, detail="Static submission requires 'items'")
            answered_items = [item.model_dump() for item in body.items]
        else:
            answered_items = json.loads(row["answered_items"])

        qr_reference = await build_and_submit_qr(
            answered_items, row["questionnaire_url"], settings.payer_dtr_base_url
        )

        now = _now()
        await db.execute(
            "UPDATE questionnaire_sessions "
            "SET answered_items = ?, qr_reference = ?, submitted_at = ? WHERE session_id = ?",
            (json.dumps(answered_items), qr_reference, now, session_id),
        )
        await db.execute(
            "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
            ("dtr_complete", now, session_id),
        )
        await db.commit()

    return {"qr_reference": qr_reference}
