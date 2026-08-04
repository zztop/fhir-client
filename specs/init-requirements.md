# FHIR Prior Authorization Test Harness — Implementation Requirements

**FHIR Version:** R4 (4.0.1)  
**Da Vinci IGs:** CRD 2.1.0 · DTR 2.1.0 · PAS 2.1.0  
**Language:** Python 3.12 + FastAPI  
**Purpose:** Simulate a provider EHR submitting prior authorization workflows end-to-end using the Da Vinci suite

---

## 1. Overview

This harness simulates a Provider EHR that initiates and drives a complete prior authorization workflow through three coordinated Da Vinci implementation guides:

| IG | Role in workflow |
|----|-----------------|
| **CRD** (Coverage Requirements Discovery) | EHR fires a CDS Hook; payer CDS service responds with coverage cards — may trigger DTR or PAS |
| **DTR** (Documentation Templates and Rules) | Provider receives a SMART app launch link; harness simulates the Questionnaire fetch and QuestionnaireResponse submission (no CQL pre-population) |
| **PAS** (Prior Authorization Support) | EHR submits a FHIR Claim bundle to payer's `$submit` endpoint; payer returns auth decision |

The harness acts as both sides of these exchanges: it plays the **EHR/provider** role for requests and provides **stub payer services** (CDS Hooks endpoint, DTR questionnaire server, PAS `$submit` endpoint) for responses.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FHIR Test Harness                            │
│                                                                     │
│  ┌──────────────────────┐         ┌──────────────────────────────┐  │
│  │   Provider EHR       │         │   Stub Payer Services        │  │
│  │   Simulator (CLI)    │         │                              │  │
│  │                      │ ──────► │  CDS Hooks Server  :3001     │  │
│  │  - Hook selector     │ ◄────── │  (CRD 2.1.0 cards)          │  │
│  │  - FHIR R4 context   │         │                              │  │
│  │    builder           │ ──────► │  DTR Stub Server   :3002     │  │
│  │  - DTR client        │ ◄────── │  (Questionnaire only)        │  │
│  │  - PAS Claim         │         │                              │  │
│  │    submitter         │ ──────► │  PAS Endpoint      :3003     │  │
│  │                      │ ◄────── │  ($submit + $inquire)        │  │
│  └──────────────────────┘         └──────────────────────────────┘  │
│            │                                                        │
│            ▼                                                        │
│  ┌──────────────────────┐                                           │
│  │  HAPI FHIR R4 Server │                                           │
│  │  (Docker sidecar)    │                                           │
│  │  :8080               │                                           │
│  └──────────────────────┘                                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack

| Layer | Library / Tool | Purpose |
|-------|---------------|---------|
| Language | Python 3.12 | — |
| FHIR R4 models | `fhir.resources` 7.x (Pydantic v2) | Type-safe R4 resource classes — Patient, Claim, Coverage, Questionnaire, etc. |
| HTTP server | `fastapi` + `uvicorn` | Hosts all three stub payer services |
| Async HTTP client | `httpx` | EHR side: fires CDS Hook requests, submits PAS |
| CLI interaction | `questionary` | Hook selector prompt (checkbox + select) |
| FHIR R4 server | HAPI FHIR JPA Server (Docker) | Stores test fixtures; EHR reads from it |
| Validation | `fhir.resources` built-in + HL7 FHIR Validator (optional) | Pydantic catches malformed resources; HL7 CLI for profile validation |
| Tests | `pytest` + `pytest-asyncio` + `httpx` | Unit, integration, E2E |
| Config | `pydantic-settings` + `.env` | Typed settings from environment |
| Logging | `structlog` | Structured JSON output |
| Containerisation | `docker compose` | Orchestrates HAPI FHIR + all stub services |

---

## 4. Project Structure

```
fhir-client/
├── specs/
│   └── init-requirements.md          ← this file
├── docker-compose.yml                ← HAPI FHIR + stub services
├── pyproject.toml                    ← dependencies (uv or Poetry)
├── .env.example
├── src/
│   ├── cli/
│   │   ├── main.py                   ← Entry point, questionary prompts
│   │   └── runner.py                 ← Orchestrates full workflow per hook selection
│   ├── ehr/
│   │   ├── context_builder.py        ← Builds CDS Hook context from FHIR fixtures
│   │   ├── cds_client.py             ← Sends hook requests, processes cards
│   │   ├── dtr_client.py             ← Fetches Questionnaire, POSTs QuestionnaireResponse
│   │   └── pas_submitter.py          ← Builds + submits PAS Claim bundle
│   ├── payer/
│   │   ├── cds_hooks_server.py       ← FastAPI router: CRD hook handlers
│   │   ├── cards/
│   │   │   ├── coverage_info.py      ← Coverage Information card builder
│   │   │   ├── form_completion.py    ← Request Form Completion card builder
│   │   │   └── instructions.py       ← Instructions card builder
│   │   ├── dtr_server.py             ← FastAPI router: Questionnaire + $next-question
│   │   └── pas_server.py             ← FastAPI router: $submit + $inquire
│   ├── fhir/
│   │   ├── server.py                 ← HAPI FHIR bootstrap: loads fixtures on startup
│   │   └── fixtures/
│   │       ├── patient.json          ← Synthetic Patient (R4, US Core)
│   │       ├── coverage.json         ← Synthetic Coverage (R4, CRD profile)
│   │       ├── practitioner.json     ← Synthetic Practitioner (R4)
│   │       ├── organization.json     ← Payer Organization (R4)
│   │       └── encounter.json        ← Active Encounter (R4)
│   ├── hooks/
│   │   ├── order_sign.py             ← order-sign context builder
│   │   ├── order_select.py           ← order-select context builder
│   │   └── appointment_book.py       ← appointment-book context builder
│   ├── models/
│   │   ├── cds_hooks.py              ← CDS Hooks 2.0 Pydantic models
│   │   ├── crd.py                    ← CRD card extension models
│   │   └── pas.py                    ← PAS-specific request/response models
│   └── config.py                     ← pydantic-settings config
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── CLAUDE.md
```

---

## 5. Supported CDS Hooks (CRD 2.1.0)

The CLI prompts the user to select one or more hooks at startup.

### 5.1 `order-sign`

Fired when a provider finalizes and signs an order (medication, device, procedure, or service request).

**Context payload (FHIR R4):**
```json
{
  "hookInstance": "<uuid>",
  "hook": "order-sign",
  "fhirServer": "http://localhost:8080/fhir/r4",
  "context": {
    "userId": "Practitioner/<id>",
    "patientId": "<Patient id>",
    "encounterId": "<Encounter id>",
    "draftOrders": {
      "resourceType": "Bundle",
      "type": "collection",
      "entry": [
        { "resource": { "resourceType": "MedicationRequest" } }
      ]
    }
  },
  "prefetch": {
    "patient": { "resourceType": "Patient" },
    "coverage": { "resourceType": "Coverage" }
  }
}
```

**Payer CDS responses (cards):**
- Coverage Information card (`pa-needed: true/false`)
- Request Form Completion card → DTR Questionnaire link
- Instructions card (informational only)
- External Reference card (payer policy URL)

### 5.2 `order-select`

Fired when a provider selects an order item before signing.

**Key differences from `order-sign`:**
- `draftOrders` entries may be incomplete (no dosage finalized)
- Returns lighter coverage cards; full PA determination deferred to order-sign

**Use case in harness:** Early coverage check before the provider commits to signing.

### 5.3 `appointment-book`

Fired when scheduling an appointment for a procedure that may require prior authorization.

**Context payload (FHIR R4):**
```json
{
  "hook": "appointment-book",
  "fhirServer": "http://localhost:8080/fhir/r4",
  "context": {
    "userId": "Practitioner/<id>",
    "patientId": "<Patient id>",
    "encounterId": "<Encounter id>",
    "appointments": {
      "resourceType": "Bundle",
      "type": "collection",
      "entry": [
        { "resource": { "resourceType": "Appointment" } }
      ]
    }
  }
}
```

**Use case in harness:** Auth check at scheduling time, before clinical ordering.

---

## 6. Implementation Steps

### Phase 1: Project Bootstrap (Sprint 1)

**Step 1.1 — Initialize Python project**
- Create `pyproject.toml` using `uv` (preferred) or Poetry
- Dependencies: `fastapi`, `uvicorn[standard]`, `httpx`, `fhir.resources`, `questionary`, `pydantic-settings`, `structlog`, `pytest`, `pytest-asyncio`
- Python version: 3.12 (specified in `.python-version`)
- `src/` layout with `__init__.py` in each package
- Pre-commit hooks: `ruff` (lint + format), `mypy` (type checking)

**Step 1.2 — Define CDS Hooks 2.0 Pydantic models** (`src/models/cds_hooks.py`)
```python
from pydantic import BaseModel
from typing import Literal, Any

class Link(BaseModel):
    label: str
    url: str
    type: Literal["absolute", "smart"]
    appContext: str | None = None

class Card(BaseModel):
    summary: str
    indicator: Literal["info", "warning", "critical"]
    source: dict[str, str]
    detail: str | None = None
    links: list[Link] = []
    extension: dict[str, Any] = {}

class CDSHookResponse(BaseModel):
    cards: list[Card] = []
    systemActions: list[dict] = []
```

**Step 1.3 — Define CRD card extension models** (`src/models/crd.py`)
- `CoverageInformation`: `covered`, `pa_needed`, `doc_needed`, `doc_purpose`, `coverage_assertion_ids`, `date`
- `CRDExtension`: wraps `davinci-crd.coverage-information` list

**Step 1.4 — pydantic-settings config** (`src/config.py`)
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    fhir_base_url: str = "http://localhost:8080/fhir/r4"
    port_cds: int = 3001
    port_dtr: int = 3002
    port_pas: int = 3003
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
```

---

### Phase 2: Docker Compose + HAPI FHIR (Sprint 1)

**Step 2.1 — `docker-compose.yml`**
```yaml
services:
  hapi-fhir:
    image: hapiproject/hapi:latest
    ports:
      - "8080:8080"
    environment:
      hapi.fhir.fhir_version: R4
      hapi.fhir.allow_multiple_delete: "true"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/fhir/metadata"]
      interval: 10s
      timeout: 5s
      retries: 10

  cds-server:
    build: .
    command: uvicorn src.payer.cds_hooks_server:app --host 0.0.0.0 --port 3001
    ports:
      - "3001:3001"
    depends_on:
      hapi-fhir:
        condition: service_healthy

  dtr-server:
    build: .
    command: uvicorn src.payer.dtr_server:app --host 0.0.0.0 --port 3002
    ports:
      - "3002:3002"

  pas-server:
    build: .
    command: uvicorn src.payer.pas_server:app --host 0.0.0.0 --port 3003
    ports:
      - "3003:3003"
```

**Step 2.2 — Load test fixtures into HAPI on startup** (`src/fhir/server.py`)
- On CLI start: load each JSON fixture from `src/fhir/fixtures/`
- Use `fhir.resources` to parse and validate each resource before POST
- PUT to `http://localhost:8080/fhir/r4/<ResourceType>/<id>` (deterministic IDs)
- Store returned `id` values in a `FixtureIds` dataclass passed into hook builders

**Step 2.3 — Synthetic test fixtures** (`src/fhir/fixtures/`)

Each fixture must satisfy both FHIR R4 base and the relevant CRD 2.1.0 profile.

`patient.json`:
```json
{
  "resourceType": "Patient",
  "id": "test-patient-001",
  "meta": {
    "profile": ["http://hl7.org/fhir/us/davinci-crd/StructureDefinition/profile-patient"]
  },
  "identifier": [{ "system": "http://example.org/mrn", "value": "MRN-001" }],
  "name": [{ "family": "TestPatient", "given": ["Jane"] }],
  "birthDate": "1975-04-15",
  "gender": "female"
}
```

`coverage.json`:
```json
{
  "resourceType": "Coverage",
  "id": "test-coverage-001",
  "meta": {
    "profile": ["http://hl7.org/fhir/us/davinci-crd/StructureDefinition/profile-coverage"]
  },
  "status": "active",
  "subscriber": { "reference": "Patient/test-patient-001" },
  "subscriberId": "MEM-12345",
  "beneficiary": { "reference": "Patient/test-patient-001" },
  "payor": [{ "reference": "Organization/test-payer-001" }],
  "class": [
    { "type": { "coding": [{ "code": "group" }] }, "value": "GRP-ABC" },
    { "type": { "coding": [{ "code": "plan"  }] }, "value": "PLAN-XYZ" }
  ]
}
```

`organization.json`:
```json
{
  "resourceType": "Organization",
  "id": "test-payer-001",
  "type": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "pay" }] }],
  "name": "Stub Payer Inc."
}
```

`practitioner.json`:
```json
{
  "resourceType": "Practitioner",
  "id": "test-practitioner-001",
  "identifier": [{ "system": "http://hl7.org/fhir/sid/us-npi", "value": "1234567890" }],
  "name": [{ "family": "TestDoctor", "given": ["Alice"] }]
}
```

`encounter.json`:
```json
{
  "resourceType": "Encounter",
  "id": "test-encounter-001",
  "meta": {
    "profile": ["http://hl7.org/fhir/us/davinci-crd/StructureDefinition/profile-encounter"]
  },
  "status": "in-progress",
  "class": { "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB" },
  "subject": { "reference": "Patient/test-patient-001" },
  "participant": [{ "individual": { "reference": "Practitioner/test-practitioner-001" } }]
}
```

---

### Phase 3: CLI Hook Selector (Sprint 2)

**Step 3.1 — `questionary` prompt flow** (`src/cli/main.py`)

```python
import questionary
import asyncio

async def run_cli():
    hooks = await questionary.checkbox(
        "Which CDS hooks do you want to test?",
        choices=["order-sign", "order-select", "appointment-book"]
    ).ask_async()

    scenario = await questionary.select(
        "Select a test scenario:",
        choices=[
            "PA Required — MedicationRequest (RxNorm 1049502)",
            "PA Not Required — Routine lab (CPT 85025)",
            "Auth Pending — High-cost device (CPT 33533)",
        ]
    ).ask_async()

    payer_mode = await questionary.select(
        "Payer mode:",
        choices=["Stub payer (local)", "External payer (from .env)"]
    ).ask_async()

    return HarnessConfig(hooks=hooks, scenario=scenario, payer_mode=payer_mode)
```

**Step 3.2 — `HarnessConfig` dataclass** (`src/cli/runner.py`)
```python
from dataclasses import dataclass

@dataclass
class HarnessConfig:
    hooks: list[str]
    scenario: str
    payer_mode: str
```

**Step 3.3 — Workflow orchestrator** (`src/cli/runner.py`)
- For each selected hook, call the appropriate context builder
- POST to CDS Hooks server → print cards
- If any card contains a `request-form-completion` link → invoke DTR client
- If any `coverage-information` card has `pa-needed: true` → invoke PAS submitter
- Print final auth status to console

---

### Phase 4: Hook Context Builders (Sprint 2)

**Step 4.1 — `order-sign` builder** (`src/hooks/order_sign.py`)

```python
from fhir.resources.R4B.medicationrequest import MedicationRequest
from fhir.resources.R4B.bundle import Bundle
from uuid import uuid4

def build_order_sign_context(fixture_ids: FixtureIds, scenario: Scenario) -> dict:
    med_request = MedicationRequest.construct(
        status="draft",
        intent="order",
        subject={"reference": f"Patient/{fixture_ids.patient}"},
        encounter={"reference": f"Encounter/{fixture_ids.encounter}"},
        requester={"reference": f"Practitioner/{fixture_ids.practitioner}"},
        medicationCodeableConcept={
            "coding": [{
                "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                "code": scenario.rxnorm_code,
                "display": scenario.display
            }]
        }
    )
    draft_orders = Bundle.construct(type="collection", entry=[{"resource": med_request.dict()}])
    return {
        "hook": "order-sign",
        "hookInstance": str(uuid4()),
        "fhirServer": settings.fhir_base_url,
        "context": {
            "userId": f"Practitioner/{fixture_ids.practitioner}",
            "patientId": fixture_ids.patient,
            "encounterId": fixture_ids.encounter,
            "draftOrders": draft_orders.dict()
        },
        "prefetch": {
            "patient": fetch_fhir(f"Patient/{fixture_ids.patient}"),
            "coverage": fetch_fhir(f"Coverage?patient={fixture_ids.patient}&status=active")
        }
    }
```

**Step 4.2 — `order-select` builder** (`src/hooks/order_select.py`)
- Same structure as order-sign
- MedicationRequest omits `dosageInstruction` (provider still selecting)
- No `authoredOn` field set

**Step 4.3 — `appointment-book` builder** (`src/hooks/appointment_book.py`)

```python
from fhir.resources.R4B.appointment import Appointment

def build_appointment_book_context(fixture_ids: FixtureIds, scenario: Scenario) -> dict:
    appointment = Appointment.construct(
        status="pending",
        serviceType=[{
            "coding": [{
                "system": "http://www.ama-assn.org/go/cpt",
                "code": scenario.cpt_code
            }]
        }],
        participant=[
            {"actor": {"reference": f"Patient/{fixture_ids.patient}"}, "status": "accepted"},
            {"actor": {"reference": f"Practitioner/{fixture_ids.practitioner}"}, "status": "accepted"}
        ],
        start="2026-08-10T09:00:00Z",
        end="2026-08-10T09:30:00Z"
    )
    ...
```

---

### Phase 5: Stub Payer — CDS Hooks Server (CRD 2.1.0) (Sprint 3)

**Step 5.1 — FastAPI router** (`src/payer/cds_hooks_server.py`)

```python
from fastapi import FastAPI
app = FastAPI()

@app.get("/cds-services")
def discovery():
    return {
        "services": [
            {
                "hook": "order-sign",
                "id": "crd-order-sign",
                "title": "Da Vinci CRD — Order Sign",
                "prefetch": {
                    "patient": "Patient/{{context.patientId}}",
                    "coverage": "Coverage?patient={{context.patientId}}&status=active"
                }
            },
            { "hook": "order-select",      "id": "crd-order-select",      "title": "Da Vinci CRD — Order Select" },
            { "hook": "appointment-book",  "id": "crd-appointment-book",  "title": "Da Vinci CRD — Appointment Book" }
        ]
    }

@app.post("/cds-services/crd-order-sign")
async def order_sign(request: dict): ...

@app.post("/cds-services/crd-order-select")
async def order_select(request: dict): ...

@app.post("/cds-services/crd-appointment-book")
async def appointment_book(request: dict): ...
```

**Step 5.2 — Scenario routing**

`src/payer/scenarios.json`:
```json
[
  { "code": "1049502", "system": "rxnorm", "scenario": "pa-required",     "display": "Oxycodone 5mg" },
  { "code": "85025",   "system": "cpt",    "scenario": "pa-not-required", "display": "CBC with differential" },
  { "code": "33533",   "system": "cpt",    "scenario": "auth-pending",    "display": "CABG, arterial, single" }
]
```

Stub reads `draftOrders` → extracts the first order coding → looks up scenario → routes to card builders.

**Step 5.3 — Coverage Information card** (`src/payer/cards/coverage_info.py`)

Per CRD 2.1.0 §3.3.1:

```python
from datetime import date

def build_coverage_info_card(pa_needed: bool, coverage_ref: str) -> dict:
    return {
        "summary": "Prior Authorization Required" if pa_needed else "No Prior Authorization Required",
        "indicator": "warning" if pa_needed else "info",
        "source": {"label": "Stub Payer", "url": "http://localhost:3001"},
        "extension": {
            "davinci-crd.coverage-information": [{
                "coverage": {"reference": coverage_ref},
                "covered": "covered",
                "pa-needed": pa_needed,
                "doc-needed": "clinical" if pa_needed else "no",
                "doc-purpose": ["prior-auth"] if pa_needed else [],
                "coverage-assertion-ids": ["ASSERT-001"],
                "date": date.today().isoformat()
            }]
        }
    }
```

**Step 5.4 — Request Form Completion card** (`src/payer/cards/form_completion.py`)

Returned alongside Coverage Info when `pa-needed: true`:

```python
import json

def build_form_completion_card() -> dict:
    return {
        "summary": "Complete Prior Auth Documentation",
        "indicator": "warning",
        "source": {"label": "Stub Payer"},
        "links": [{
            "label": "Launch Documentation Requirements",
            "url": "http://localhost:3002/smart/launch",
            "type": "smart",
            "appContext": json.dumps({
                "questionnaire": "http://localhost:3002/fhir/r4/Questionnaire/pa-auth-q"
            })
        }]
    }
```

---

### Phase 6: Stub Payer — DTR Server (DTR 2.1.0) (Sprint 4)

**Step 6.1 — FastAPI router** (`src/payer/dtr_server.py`)

```python
@app.get("/fhir/r4/Questionnaire/{questionnaire_id}")
def get_questionnaire(questionnaire_id: str):
    # Returns static FHIR R4 Questionnaire

@app.post("/fhir/r4/Questionnaire/$next-question")
def next_question(body: dict):
    # Adaptive form: simple index-based state machine, no CQL

@app.post("/fhir/r4/QuestionnaireResponse")
async def submit_response(body: dict):
    # Accepts and acknowledges completed QuestionnaireResponse
    return {"resourceType": "QuestionnaireResponse", "id": str(uuid4()), "status": "completed"}
```

**Step 6.2 — Static Questionnaire resource** (DTR 2.1.0 profile)

```json
{
  "resourceType": "Questionnaire",
  "id": "pa-auth-q",
  "meta": {
    "profile": ["http://hl7.org/fhir/us/davinci-dtr/StructureDefinition/dtr-questionnaire-r4"]
  },
  "url": "http://localhost:3002/fhir/r4/Questionnaire/pa-auth-q",
  "status": "active",
  "title": "Prior Authorization Documentation",
  "item": [
    { "linkId": "1", "text": "Is this service medically necessary?", "type": "boolean",  "required": true },
    { "linkId": "2", "text": "Primary diagnosis code (ICD-10)",      "type": "string",   "required": true },
    { "linkId": "3", "text": "Treating physician NPI",               "type": "string",   "required": true },
    { "linkId": "4", "text": "Requested quantity / units",           "type": "integer",  "required": true }
  ]
}
```

**Step 6.3 — DTR client (EHR side)** (`src/ehr/dtr_client.py`)
- Parses SMART launch URL from CRD Request Form Completion card link
- GETs Questionnaire from DTR server
- In `--interactive` mode: prints questions to console, collects answers from provider via stdin
- In automated mode: uses hardcoded test answers (`true`, `M54.5`, `1234567890`, `30`)
- Builds `QuestionnaireResponse` (DTR 2.1.0 profile) with provider answers
- POSTs QuestionnaireResponse to DTR server → returns `QuestionnaireResponse/<id>` reference for PAS

---

### Phase 7: PAS Claim Submission (PAS 2.1.0) (Sprint 5)

**Step 7.1 — PAS Claim Bundle builder** (`src/ehr/pas_submitter.py`)

Builds a `PASRequestBundle` (FHIR R4 Bundle, `type: collection`) per PAS 2.1.0:

Required bundle entries:
1. **PASClaim** (`Claim`)
   - `status: active`
   - `use: preauthorization`
   - `type`: `professional | institutional`
   - `patient` → Patient reference
   - `insurer` → Payer Organization reference
   - `provider` → Practitioner reference
   - `priority`: `normal`
   - `insurance[0].coverage` → Coverage reference
   - `item[0]`: service line with CPT/HCPCS code, quantity
   - If DTR was completed: `supportingInfo` entry referencing `QuestionnaireResponse/<id>`
2. **Patient** (US Core)
3. **Coverage** (CRD Coverage profile)
4. **Practitioner** (US Core)
5. **Organization** (payer)
6. **Condition** (active diagnosis, ICD-10)

**Step 7.2 — Submit to PAS endpoint**
```
POST http://localhost:3003/fhir/r4/Claim/$submit
Content-Type: application/fhir+json
Body: PASRequestBundle
```

Expected response — `ClaimResponse`:
- `outcome`: `complete | error | partial`
- `disposition`: `Granted | Denied | Pended`
- Extension `reviewAction.code` with authorization number if granted

**Step 7.3 — Pending / polling**
- If `disposition == "Pended"` → poll `POST /fhir/r4/Claim/$inquire` every 5 seconds, up to 3 retries
- `$inquire` body: Bundle containing a `ClaimInquiry` resource (PAS 2.1.0 profile) referencing the original claim

**Step 7.4 — Stub PAS server** (`src/payer/pas_server.py`)

```python
@app.post("/fhir/r4/Claim/$submit")
async def submit(body: dict):
    scenario = resolve_scenario_from_claim(body)
    match scenario:
        case "pa-required":
            return build_claim_response("Granted", auth_number="AUTH-2026-0803-001")
        case "auth-pending":
            return build_claim_response("Pended")
        case "pa-not-required":
            return build_claim_response("Granted", note="No PA required")

@app.post("/fhir/r4/Claim/$inquire")
async def inquire(body: dict):
    return build_claim_response("Granted", auth_number="AUTH-2026-0803-002")
```

---

### Phase 8: End-to-End Orchestration (Sprint 5)

**Step 8.1 — Workflow runner** (`src/cli/runner.py`)

```
User selects hooks + scenario via CLI
        │
        ▼
HAPI FHIR health check
Load fixtures (PUT to HAPI) → store FixtureIds
        │
        ▼
For each selected hook (in clinical order: select → sign → book):
  1. Build hook context using fhir.resources
  2. POST to CDS Hooks server
  3. Parse CDSHookResponse → print cards
  4. If card links contain type=smart (DTR launch):
       → GET Questionnaire from DTR server
       → Collect/auto-fill answers
       → POST QuestionnaireResponse → save QR reference
  5. If coverage-information.pa-needed == true:
       → Build PAS Claim Bundle (include QR ref if available)
       → POST Claim/$submit
       → If Pended: poll $inquire (3x, 5s interval)
       → Print final disposition + auth number
  6. Print workflow summary
```

**Step 8.2 — Console output format**

```
═══════════════════════════════════════════════════════
  Hook: order-sign   |   Scenario: PA Required
═══════════════════════════════════════════════════════
  CRD Response (2 cards):
  [COVERAGE]  covered=true  |  pa-needed=YES  |  doc-needed=clinical
  [FORM]      DTR Launch → http://localhost:3002/smart/launch

  DTR Questionnaire (pa-auth-q):
  Q1: Is this service medically necessary? → true
  Q2: Primary diagnosis code (ICD-10)     → M54.5
  Q3: Treating physician NPI              → 1234567890
  Q4: Requested quantity / units          → 30
  QuestionnaireResponse submitted ✓ (id: qr-abc123)

  PAS Submission:
  POST /fhir/r4/Claim/$submit ... 200 OK
  disposition: Granted
  auth number: AUTH-2026-0803-001
═══════════════════════════════════════════════════════
```

---

### Phase 9: Validation (Sprint 6)

**Step 9.1 — `fhir.resources` runtime validation**
- All FHIR R4 resources constructed via `fhir.resources` Pydantic v2 models
- Pydantic validates required fields, cardinality, and allowed values at construction time
- Catches malformed resources before they leave the process

**Step 9.2 — Optional HL7 FHIR Validator (profile-level)**
- Invoked with `--validate` CLI flag: `java -jar validator_cli.jar -version 4.0.1 -ig hl7.fhir.us.davinci-pas#2.1.0 <resource.json>`
- Validates conformance to Da Vinci CRD/DTR/PAS StructureDefinitions
- Non-blocking in test mode (logs warnings, does not fail the run)

**Step 9.3 — CDS Hooks schema validation**
- `jsonschema` library validates hook responses against CDS Hooks 2.0 JSON schema
- Validates `coverage-information` extension structure per CRD 2.1.0 §3.3

---

### Phase 10: Testing Strategy (Sprint 6)

**Unit tests** (`tests/unit/`)
- `test_context_builders.py`: assert correct FHIR R4 resource shapes per hook
- `test_card_builders.py`: assert each card type serializes to valid CDS Hooks 2.0 shape
- `test_pas_bundle.py`: assert required PAS 2.1.0 bundle entries are present
- `test_scenario_routing.py`: assert correct scenario selected per incoming order code

**Integration tests** (`tests/integration/`)
- Full CDS Hook request/response cycle against live stub server (`pytest-asyncio` + `httpx.AsyncClient`)
- DTR: GET Questionnaire → POST QuestionnaireResponse → assert 201
- PAS: POST `$submit` → synchronous `Granted`
- PAS async: POST `$submit` (Pended) → POST `$inquire` → `Granted`

**E2E tests** (`tests/e2e/`)
- `test_order_sign_full_flow.py`: order-sign → CRD cards → DTR → PAS → `Granted`
- `test_appointment_book_flow.py`: appointment-book → CRD cards → PAS → `Granted`
- `test_pa_not_required.py`: order-select → `pa-needed: false` → no DTR, no PAS

---

## 7. Key FHIR R4 Profiles (Da Vinci 2.1.0)

### CRD 2.1.0 Profiles
| Profile | Base Resource | Canonical URL |
|---------|--------------|---------------|
| CRD Patient | Patient | `http://hl7.org/fhir/us/davinci-crd/StructureDefinition/profile-patient` |
| CRD Coverage | Coverage | `http://hl7.org/fhir/us/davinci-crd/StructureDefinition/profile-coverage` |
| CRD Encounter | Encounter | `http://hl7.org/fhir/us/davinci-crd/StructureDefinition/profile-encounter` |
| CRD MedicationRequest | MedicationRequest | `http://hl7.org/fhir/us/davinci-crd/StructureDefinition/profile-medicationrequest` |
| CRD ServiceRequest | ServiceRequest | `http://hl7.org/fhir/us/davinci-crd/StructureDefinition/profile-servicerequest` |
| CRD Appointment | Appointment | `http://hl7.org/fhir/us/davinci-crd/StructureDefinition/profile-appointment` |

### PAS 2.1.0 Profiles
| Profile | Base Resource | Canonical URL |
|---------|--------------|---------------|
| PAS Request Bundle | Bundle | `http://hl7.org/fhir/us/davinci-pas/StructureDefinition/profile-pas-request-bundle` |
| PAS Claim | Claim | `http://hl7.org/fhir/us/davinci-pas/StructureDefinition/profile-claim` |
| PAS Claim Response | ClaimResponse | `http://hl7.org/fhir/us/davinci-pas/StructureDefinition/profile-claimresponse` |
| PAS Claim Inquiry | Claim | `http://hl7.org/fhir/us/davinci-pas/StructureDefinition/profile-claim-inquiry` |

### DTR 2.1.0 Profiles
| Profile | Base Resource | Canonical URL |
|---------|--------------|---------------|
| DTR Questionnaire | Questionnaire | `http://hl7.org/fhir/us/davinci-dtr/StructureDefinition/dtr-questionnaire-r4` |
| DTR QuestionnaireResponse | QuestionnaireResponse | `http://hl7.org/fhir/us/davinci-dtr/StructureDefinition/dtr-questionnaireresponse-r4` |

---

## 8. Key API Endpoints Summary

| Service | Method | Path | Description |
|---------|--------|------|-------------|
| CDS (CRD) | GET | `/cds-services` | Hook discovery |
| CDS (CRD) | POST | `/cds-services/crd-order-sign` | Fire order-sign hook |
| CDS (CRD) | POST | `/cds-services/crd-order-select` | Fire order-select hook |
| CDS (CRD) | POST | `/cds-services/crd-appointment-book` | Fire appointment-book hook |
| DTR | GET | `/fhir/r4/Questionnaire/<id>` | Fetch questionnaire |
| DTR | POST | `/fhir/r4/Questionnaire/$next-question` | Adaptive form next question |
| DTR | POST | `/fhir/r4/QuestionnaireResponse` | Save completed response |
| PAS | POST | `/fhir/r4/Claim/$submit` | Submit prior auth request |
| PAS | POST | `/fhir/r4/Claim/$inquire` | Poll pending prior auth |
| FHIR | GET | `/fhir/r4/Patient/<id>` | Get test patient |
| FHIR | GET | `/fhir/r4/Coverage?patient=<id>` | Get patient coverage |
| FHIR | GET | `/fhir/r4/Encounter/<id>` | Get encounter |

---

## 9. Environment Variables

```bash
# .env.example
PORT_FHIR=8080
PORT_CDS=3001
PORT_DTR=3002
PORT_PAS=3003

FHIR_BASE_URL=http://localhost:8080/fhir/r4

# External payer mode (optional — overrides localhost stubs)
PAYER_CDS_BASE_URL=http://localhost:3001
PAYER_DTR_BASE_URL=http://localhost:3002
PAYER_PAS_BASE_URL=http://localhost:3003

LOG_LEVEL=INFO

# Auth (optional)
ENABLE_AUTH=false

# PAS async scenario
PEND_DELAY_SECONDS=0
```

---

## 10. Sprint Plan Summary

| Sprint | Deliverable | Steps Covered |
|--------|-------------|---------------|
| Sprint 1 | Python project + Docker Compose + HAPI FHIR + fixtures | 1.1–2.3 |
| Sprint 2 | CLI hook selector + hook context builders | 3.1–4.3 |
| Sprint 3 | Stub CDS Hooks server (CRD 2.1.0) | 5.1–5.4 |
| Sprint 4 | Stub DTR server + DTR client | 6.1–6.3 |
| Sprint 5 | PAS submission + E2E orchestration | 7.1–8.2 |
| Sprint 6 | Validation + full test suite | 9.1–10 |

---

## 11. Open Questions / Decisions Needed

1. **FHIR server persistence**: HAPI FHIR Docker uses H2 in-memory by default (resets on restart). Use a PostgreSQL volume for persistence across runs, or keep H2 for full isolation? **Recommendation**: H2 in-memory; fixtures reload on each harness start.

2. **DTR interactive vs. automated mode**: Should the CLI pause for provider to fill in Questionnaire answers interactively, or auto-fill hardcoded test answers? **Recommendation**: Both — `--interactive` flag for manual demos, auto-fill default for CI/tests.

3. **PAS async delay**: Should the `auth-pending` scenario introduce a real time delay before `$inquire` resolves? **Recommendation**: Configurable via `PEND_DELAY_SECONDS` env var (default `0` for tests, `5` for demos).

4. **Multi-hook run order**: When multiple hooks selected (e.g. `order-select` + `order-sign`), run sequentially in clinical order (select → sign → PAS) or independently? **Recommendation**: Sequential clinical order to model a realistic EHR workflow.
