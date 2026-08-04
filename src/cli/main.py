"""CLI entry point — prompts provider for hook selection and scenario."""
from __future__ import annotations
import asyncio

import questionary

from src.cli.runner import HarnessConfig, run

_SCENARIO_MAP = {
    "PA Required — MedicationRequest (RxNorm 1049502)": "pa-required",
    "PA Not Required — Routine lab (CPT 85025)":        "pa-not-required",
    "Auth Pending — High-cost device (CPT 33533)":      "auth-pending",
}


async def _prompt() -> HarnessConfig:
    hooks = await questionary.checkbox(
        "Which CDS hooks do you want to test?",
        choices=["order-sign", "order-select", "appointment-book"],
        validate=lambda v: True if v else "Select at least one hook",
    ).ask_async()

    label = await questionary.select(
        "Select a test scenario:",
        choices=list(_SCENARIO_MAP),
    ).ask_async()

    payer_mode = await questionary.select(
        "Payer mode:",
        choices=["stub (local)", "external (from .env)"],
    ).ask_async()

    return HarnessConfig(
        hooks=hooks,
        scenario_key=_SCENARIO_MAP[label],
        payer_mode=payer_mode,
    )


def main() -> None:
    config = asyncio.run(_prompt())
    asyncio.run(run(config))


if __name__ == "__main__":
    main()
