"""EHR API — FastAPI BFF for the prior authorization web UI."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.db import init_db
from src.api.routers import dtr, pas, sessions, utility

_UI_DIST = Path(__file__).parents[2] / "ui" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db("sessions.db")
    yield


app = FastAPI(title="FHIR Prior Auth — EHR API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(utility.router)
app.include_router(sessions.router)
app.include_router(dtr.router)
app.include_router(pas.router)

if _UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=_UI_DIST, html=True), name="ui")
