"""Da Vinci CRD 2.1.0 stub — CDS Hooks 2.0 server."""
from __future__ import annotations

from fastapi import FastAPI, Request

from src.models.cds_hooks import CDSHookResponse, CDSService, CDSServicesResponse
from src.payer import scenario_router
from src.payer.cards import coverage_info, form_completion, instructions

app = FastAPI(title="Da Vinci CRD Stub — CDS Hooks 2.0")

_PREFETCH = {
    "patient":  "Patient/{{context.patientId}}",
    "coverage": "Coverage?patient={{context.patientId}}&status=active",
}

_SERVICES = [
    CDSService(
        hook="order-sign",
        id="crd-order-sign",
        title="Da Vinci CRD — Order Sign",
        description="Coverage requirements discovery for signed orders (CRD 2.1.0)",
        prefetch=_PREFETCH,
    ),
    CDSService(
        hook="order-select",
        id="crd-order-select",
        title="Da Vinci CRD — Order Select",
        description="Coverage requirements discovery when selecting an order item (CRD 2.1.0)",
        prefetch=_PREFETCH,
    ),
    CDSService(
        hook="appointment-book",
        id="crd-appointment-book",
        title="Da Vinci CRD — Appointment Book",
        description="Coverage requirements discovery when booking an appointment (CRD 2.1.0)",
        prefetch=_PREFETCH,
    ),
]


def _coverage_ref(body: dict) -> str:
    entries = (
        body.get("prefetch", {})
            .get("coverage", {})
            .get("entry", [])
    )
    if entries:
        rid = entries[0].get("resource", {}).get("id", "test-coverage-001")
        return f"Coverage/{rid}"
    return "Coverage/test-coverage-001"


def _handle(body: dict) -> CDSHookResponse:
    scenario = scenario_router.route(body)

    if scenario is None:
        return CDSHookResponse(cards=[
            instructions.build(
                "Unable to determine coverage requirements — unrecognised order code."
            ),
        ])

    pa_needed = scenario.scenario in ("pa-required", "auth-pending")
    cards = [coverage_info.build(pa_needed=pa_needed, coverage_ref=_coverage_ref(body))]
    if pa_needed:
        cards.append(form_completion.build())

    return CDSHookResponse(cards=cards)


@app.get("/cds-services", response_model=CDSServicesResponse)
def discovery() -> CDSServicesResponse:
    return CDSServicesResponse(services=_SERVICES)


@app.post("/cds-services/crd-order-sign")
async def order_sign(request: Request) -> dict:
    return _handle(await request.json()).model_dump(exclude_none=True)


@app.post("/cds-services/crd-order-select")
async def order_select(request: Request) -> dict:
    return _handle(await request.json()).model_dump(exclude_none=True)


@app.post("/cds-services/crd-appointment-book")
async def appointment_book_hook(request: Request) -> dict:
    return _handle(await request.json()).model_dump(exclude_none=True)
