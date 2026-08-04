"""CDS Hooks 2.0 request and response Pydantic models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Link(BaseModel):
    label: str
    url: str
    type: Literal["absolute", "smart"]
    appContext: str | None = None


class Suggestion(BaseModel):
    label: str
    uuid: str | None = None
    actions: list[dict[str, Any]] = Field(default_factory=list)


class Card(BaseModel):
    uuid: str | None = None
    summary: str
    detail: str | None = None
    indicator: Literal["info", "warning", "critical"]
    source: dict[str, str]
    suggestions: list[Suggestion] = Field(default_factory=list)
    selectionBehavior: Literal["at-most-one"] | None = None
    overrideReasons: list[dict[str, Any]] | None = None
    links: list[Link] = Field(default_factory=list)
    extension: dict[str, Any] | None = None


class CDSHookResponse(BaseModel):
    cards: list[Card] = Field(default_factory=list)
    systemActions: list[dict[str, Any]] = Field(default_factory=list)


class CDSService(BaseModel):
    hook: str
    id: str
    title: str
    description: str = ""
    prefetch: dict[str, str] = Field(default_factory=dict)


class CDSServicesResponse(BaseModel):
    services: list[CDSService]


# Generic hook request — context varies by hook type so we use dict
class CDSHookRequest(BaseModel):
    hook: str
    hookInstance: str
    fhirServer: str | None = None
    fhirAuthorization: dict[str, Any] | None = None
    context: dict[str, Any]
    prefetch: dict[str, Any] = Field(default_factory=dict)
