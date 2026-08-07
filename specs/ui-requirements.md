# FHIR Prior Authorization UI — Technical Requirements

Da Vinci CRD 2.1.0 · DTR 2.1.0 · PAS 2.1.0 · React + FastAPI · SQLite

## 1. Overview

Replace the terminal CLI with a browser-based UI that walks an EHR developer through the complete prior authorization workflow:

1. Build and submit a CDS Hook request (CRD)
2. Display returned cards and trigger DTR if documentation is required
3. Answer the DTR questionnaire interactively (static or adaptive)
4. Review and edit the PAS bundle before submission
5. Display the final authorization decision

All sessions are persisted to SQLite and all raw FHIR payloads are inspectable.

**Design decisions:**
- UI: React 18 + TypeScript SPA (port 5173) + new FastAPI BFF (port 8000)
- Users: EHR developers / QA engineers — raw FHIR JSON must be inspectable at every step
- Persistence: SQLite for session history; HAPI FHIR for FHIR resources
- PAS review: editable fields before submission
- Session tracking: step timeline (CRD → DTR → PAS) per session
- Questionnaire: auto-detect static vs adaptive; adaptive renders one question at a time

---

## 2. Architecture

```
Browser (React SPA — port 5173 dev / bundled for prod)
        │  REST/JSON
        ▼
EHR API (FastAPI BFF — port 8000)          ← NEW
        │
        ├──► CDS stub  :3001  (existing — src/payer/cds_hooks_server.py)
        ├──► DTR stub  :3002  (existing — src/payer/dtr_server.py)
        ├──► PAS stub  :3003  (existing — src/payer/pas_server.py)
        ├──► HAPI FHIR :8080  (existing — Docker)
        └──► SQLite db (sessions.db at project root)   ← NEW
```

The existing payer stubs and HAPI FHIR server are unchanged. The new EHR API
replaces `src/cli/runner.py` orchestration logic with REST endpoints consumed
by the React app. All existing modules (`src/hooks/*`, `src/ehr/*`, `src/fhir/*`)
are reused as-is.

---

## 3. New Backend — EHR API (`src/api/`)

### 3.1 Technology

- FastAPI application at `src/api/main.py`, served on port 8000
- SQLite via `aiosqlite` (async); database file `sessions.db` at project root
- Reuses: `src/hooks/*`, `src/ehr/dtr_client.py`, `src/ehr/pas_submitter.py`,
  `src/fhir/server.py`, `src/models/*`, `src/config.py`
- CORS: allow `http://localhost:5173` in development

### 3.2 Database Schema

```sql
CREATE TABLE sessions (
    id           TEXT PRIMARY KEY,   -- UUID v4
    created_at   TEXT NOT NULL,      -- ISO 8601 datetime
    hook         TEXT NOT NULL,      -- order-sign | order-select | appointment-book
    scenario_key TEXT NOT NULL,      -- pa-required | pa-not-required | auth-pending
    status       TEXT NOT NULL DEFAULT 'created',
    updated_at   TEXT NOT NULL
    -- status lifecycle:
    --   created → crd_complete → dtr_in_progress → dtr_complete
    --   → pas_reviewing → pas_submitted → granted | denied | pended
);

CREATE TABLE crd_results (
    id            TEXT PRIMARY KEY,   -- UUID v4
    session_id    TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    hook_request  TEXT NOT NULL,      -- full CDSHookRequest JSON sent (for dev mode)
    raw_response  TEXT NOT NULL,      -- full CDSHookResponse JSON received
    pa_needed     INTEGER NOT NULL,   -- 0 | 1
    smart_url     TEXT,              -- SMART launch URL if card has type="smart" link
    created_at    TEXT NOT NULL
);

CREATE TABLE questionnaire_sessions (
    id                 TEXT PRIMARY KEY,  -- UUID v4
    session_id         TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    questionnaire_url  TEXT NOT NULL,     -- URL used to fetch the Questionnaire
    questionnaire_json TEXT NOT NULL,     -- full Questionnaire resource JSON
    mode               TEXT NOT NULL,     -- static | adaptive
    answered_items     TEXT NOT NULL DEFAULT '[]',  -- JSON array of {linkId, answer} objects
    qr_reference       TEXT,             -- "QuestionnaireResponse/<uuid>" once submitted
    submitted_at       TEXT,
    created_at         TEXT NOT NULL
);

CREATE TABLE pas_submissions (
    id             TEXT PRIMARY KEY,  -- UUID v4
    session_id     TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    bundle_json    TEXT NOT NULL,     -- full editable PAS Bundle JSON
    claim_response TEXT,              -- ClaimResponse JSON after $submit or $inquire
    disposition    TEXT,              -- Granted | Denied | Pended
    auth_number    TEXT,              -- from ReviewAction extension "number" if present
    submitted_at   TEXT,
    created_at     TEXT NOT NULL
);
```

### 3.3 API Endpoints

#### Sessions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/sessions` | List all sessions (id, hook, scenario_key, status, created_at, disposition) |
| `POST` | `/api/sessions` | Create session, fire CRD hook, store result; return session + CRD cards |
| `GET` | `/api/sessions/{id}` | Full detail: session + crd_result + questionnaire_session + pas_submission |
| `DELETE` | `/api/sessions/{id}` | Delete session and all child records (cascade) |

**POST `/api/sessions` — request:**
```json
{
  "hook": "order-sign",
  "scenario_key": "pa-required"
}
```

**POST `/api/sessions` — response:**
```json
{
  "session": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "hook": "order-sign",
    "scenario_key": "pa-required",
    "status": "crd_complete",
    "created_at": "2026-08-03T12:00:00Z",
    "updated_at": "2026-08-03T12:00:01Z"
  },
  "crd_result": {
    "id": "...",
    "cards": [ { "summary": "...", "indicator": "warning" } ],
    "pa_needed": true,
    "smart_url": "http://localhost:3002/dtr/launch?appContext=..."
  }
}
```

#### DTR Questionnaire

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/sessions/{id}/dtr/start` | Fetch Questionnaire from DTR stub; detect mode; create `questionnaire_sessions` row; update session status → `dtr_in_progress` |
| `GET` | `/api/sessions/{id}/dtr` | Return current questionnaire state: mode, all/current question(s), answered_items |
| `POST` | `/api/sessions/{id}/dtr/next` | **(Adaptive only)** Append answer; call DTR `$next-question`; return next question or `done: true` |
| `POST` | `/api/sessions/{id}/dtr/submit` | Build QuestionnaireResponse from answered_items; POST to DTR stub; store `qr_reference`; update session status → `dtr_complete` |

**POST `/api/sessions/{id}/dtr/next` — request:**
```json
{ "linkId": "1", "answer": [{ "valueBoolean": true }] }
```

**POST `/api/sessions/{id}/dtr/next` — response (in-progress):**
```json
{
  "done": false,
  "current_question": {
    "linkId": "2",
    "text": "Primary diagnosis code (ICD-10)",
    "type": "string",
    "required": true
  },
  "answered_count": 1
}
```

**POST `/api/sessions/{id}/dtr/submit` — request (static mode):**
```json
{
  "items": [
    { "linkId": "1", "answer": [{ "valueBoolean": true }] },
    { "linkId": "2", "answer": [{ "valueString": "M54.5" }] },
    { "linkId": "3", "answer": [{ "valueString": "1234567890" }] },
    { "linkId": "4", "answer": [{ "valueInteger": 30 }] }
  ]
}
```

**POST `/api/sessions/{id}/dtr/submit` — response:**
```json
{ "qr_reference": "QuestionnaireResponse/7c4f9a3e-1234-4abc-9def-000000000001" }
```

#### PAS Bundle

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/sessions/{id}/pas/prepare` | Build default PAS bundle (calls `build_pas_bundle`); store in `pas_submissions`; update session status → `pas_reviewing` |
| `GET` | `/api/sessions/{id}/pas/bundle` | Return stored bundle JSON (with latest edits applied) |
| `PATCH` | `/api/sessions/{id}/pas/bundle` | Merge editable field overrides into stored bundle; re-persist |
| `POST` | `/api/sessions/{id}/pas/submit` | POST bundle to PAS `$submit`; store `claim_response`; update session status |
| `POST` | `/api/sessions/{id}/pas/inquire` | POST bundle to PAS `$inquire`; update `claim_response` + `disposition` + `auth_number` |

**PATCH `/api/sessions/{id}/pas/bundle` — request (all fields optional):**
```json
{
  "diagnosis_code": "M54.5",
  "service_code": "1049502",
  "service_system": "http://www.nlm.nih.gov/research/umls/rxnorm",
  "quantity": 1,
  "priority": "normal"
}
```

**POST `/api/sessions/{id}/pas/submit` — response:**
```json
{
  "disposition": "Granted",
  "auth_number": "AUTH-2026-0803-001",
  "claim_response": { "resourceType": "ClaimResponse" }
}
```

#### Utility

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Return HAPI FHIR reachability status + SQLite connected boolean |
| `GET` | `/api/scenarios` | Return list of 3 scenarios: key, code, system, display, expected_outcome |
| `GET` | `/api/hooks` | Return list of 3 hooks: id, title, description |
| `POST` | `/api/bootstrap` | Idempotently PUT all fixtures to HAPI FHIR (calls `bootstrap_fixtures`) |

### 3.4 Static file serving

In production: FastAPI mounts React build output at `/` via `StaticFiles(directory="ui/dist")`.
In development: Vite dev server proxies `/api/*` → `http://localhost:8000`.

---

## 4. New Frontend — React SPA (`ui/`)

### 4.1 Technology

| Library | Purpose |
|---------|---------|
| React 18 + TypeScript | UI framework |
| Vite | Build tool + dev server (port 5173) |
| React Router v6 | Client-side routing |
| TanStack Query v5 | Server state, caching, auto-refetch |
| Tailwind CSS | Utility-first styling |
| shadcn/ui | Pre-built accessible components (Button, Card, Badge, Dialog, Tabs, Switch, Input, Select, Toast) |
| Vitest + React Testing Library | Component unit tests |
| Playwright | E2E tests |

### 4.2 Directory layout

```
ui/
  src/
    api/
      client.ts          # base fetch wrapper with error handling + dev-mode logging
      sessions.ts        # typed wrappers for /api/sessions/* endpoints
      dtr.ts             # typed wrappers for /api/sessions/{id}/dtr/* endpoints
      pas.ts             # typed wrappers for /api/sessions/{id}/pas/* endpoints
      util.ts            # health, scenarios, hooks, bootstrap
    components/
      layout/
        AppShell.tsx          # top navbar (with Dev Mode toggle) + page container
        StepTimeline.tsx      # vertical CRD → DTR → PAS progress indicator
      crd/
        CardDisplay.tsx               # single CDS Hook card with indicator stripe
        CoverageExtensionBadge.tsx    # pa-needed / doc-needed / covered pills
      dtr/
        StaticForm.tsx    # render all Questionnaire items at once
        AdaptiveForm.tsx  # one-question-at-a-time with Next button
        QuestionItem.tsx  # boolean=Switch, string=Input, integer=NumberInput
      pas/
        BundleReviewForm.tsx  # editable fields + Raw JSON tab
        DispositionBadge.tsx  # Granted/Denied/Pended colored badge
        RawJsonPanel.tsx      # syntax-highlighted collapsible JSON block
      shared/
        StatusBadge.tsx  # session status → color + label
        JsonViewer.tsx   # collapsible syntax-highlighted JSON with copy button
        NetworkLog.tsx   # dev mode: timestamped request/response log
    pages/
      Dashboard.tsx      # session list table
      NewSession.tsx     # hook + scenario selector form
      SessionDetail.tsx  # step timeline + CRD + DTR + PAS sections
    hooks/
      useSession.ts      # TanStack Query hooks for session CRUD
      useQuestionnaire.ts
      usePAS.ts
    types/
      index.ts           # TypeScript interfaces mirroring all API response shapes
  index.html
  vite.config.ts         # proxy /api → localhost:8000
  tailwind.config.ts
  tsconfig.json
  vitest.config.ts
  e2e/
    pa-required.spec.ts
    pa-not-required.spec.ts
    auth-pending.spec.ts
```

### 4.3 Pages

#### Page 1 — Dashboard (`/`)

**Purpose:** Overview and entry point for all prior auth sessions.

**Requirements:**
- Table columns: Session ID (first 8 chars of UUID), Hook, Scenario, Status, Created, Disposition
- `StatusBadge` color mapping:
  - `created` → gray
  - `crd_complete` → blue
  - `dtr_in_progress` → yellow
  - `dtr_complete` → blue
  - `pas_reviewing` → yellow
  - `pas_submitted` → purple
  - `granted` → green
  - `denied` → red
  - `pended` → orange
- "New Prior Auth Request" primary button → navigate to `/sessions/new`
- Each row clickable → navigate to `/sessions/:id`
- Per-row delete icon button: shows `AlertDialog` for confirmation; calls `DELETE /api/sessions/{id}`
- Auto-refresh every 5 seconds via TanStack Query `refetchInterval: 5000`
- Empty state: centered message "No sessions yet" + "Create your first request" button
- Loading skeleton rows on initial fetch

#### Page 2 — New Session (`/sessions/new`)

**Purpose:** Select hook + scenario and trigger the CRD request.

**Hook selector** — radio group, 3 options:

| Value | Label | Description shown |
|-------|-------|-------------------|
| `order-sign` | Order Signing | Signed medication/procedure orders with full clinical context |
| `order-select` | Order Selection | Pre-sign selection without authoredOn timestamp |
| `appointment-book` | Appointment Booking | Uses FHIR Appointment resource (CPT codes) |

**Scenario selector** — radio group, 3 options (each shows code + expected outcome chip):

| Value | Display | Code | Expected outcome chip |
|-------|---------|------|-----------------------|
| `pa-required` | PA Required | RxNorm `1049502` | `PA Required → Granted` |
| `pa-not-required` | PA Not Required | CPT `85025` | `No Prior Auth Needed` |
| `auth-pending` | Auth Pending | CPT `33533` | `Pended → Granted (via $inquire)` |

- "Send CRD Request" button: disabled until both hook + scenario selected
- On click: `POST /api/sessions` → on success redirect to `/sessions/:id`
- Loading spinner with "Sending CRD request…" label during request
- Error banner (dismissible) if request fails, showing error message

#### Page 3 — Session Detail (`/sessions/:id`)

**Layout:**
- Left sidebar (240 px): vertical `StepTimeline` with 3 steps; each step shows name + status icon (pending / active / complete / error)
- Main content area: shows the section for the active or most recent completed step

---

##### Step 1 — CRD Result

Always shown once session is created.

**Card rendering** — for each card in `crd_result.cards`, render `CardDisplay`:
- 4 px colored left border: `info`=blue-500, `warning`=amber-500, `critical`=red-500
- Card header: indicator badge + summary text (bold)
- Card body: `detail` text (collapsible via "Show more" if > 200 chars)
- Source: label as link if URL present
- Coverage extension section (if `extension["davinci-crd.coverage-information"]` present):
  - `CoverageExtensionBadge`: `pa-needed` pill (green if false, amber if true), `doc-needed` value, `covered` value
- SMART links: listed as "Launch DTR →" buttons for each `type="smart"` link

**Banners:**
- If `pa_needed=true`: amber banner "Documentation Required — complete the DTR questionnaire before submitting PA" with "Start DTR" CTA button
- If `pa_needed=false`: green banner "No Prior Authorization Required"
- If no cards returned: gray info banner "No CDS cards returned"

**Developer panel** (collapsed by default; expand via "Show Raw Payloads" toggle):
- "Request sent" tab: `hook_request` JSON with copy button
- "Response received" tab: `raw_response` JSON with copy button

---

##### Step 2 — DTR Questionnaire

Only available when `crd_result.smart_url` is not null.

**Activation:** "Start DTR" button → `POST /api/sessions/{id}/dtr/start` → reveals questionnaire UI

**Static mode** (`GET /api/sessions/{id}/dtr` returns `mode: "static"`):
- `StaticForm` renders all Questionnaire items in a single form
- `QuestionItem` renders each item by `type`:
  - `boolean` → labeled `Switch` (on/off toggle)
  - `string` → `Input` with placeholder
  - `integer` → `Input type="number"` with `min=0`
- Required items (`.required=true`) show asterisk; "Submit Answers" button disabled until all required items answered
- "Submit Answers" → `POST /api/sessions/{id}/dtr/submit` with all items

**Adaptive mode** (`GET /api/sessions/{id}/dtr` returns `mode: "adaptive"`):
- `AdaptiveForm` shows one `QuestionItem` at a time
- Progress indicator: "N questions answered"
- "Next →" button: disabled if current question is required and unanswered; calls `POST /api/sessions/{id}/dtr/next`
- "← Previous" button: always disabled (adaptive protocol does not support back-navigation)
- When `/next` returns `done: true`: replace form with "All questions answered" + "Submit" button
- "Submit" → `POST /api/sessions/{id}/dtr/submit` (no body — uses stored `answered_items`)

**Mode detection (backend, `src/api/services/dtr_service.py`):**
- Check `questionnaire.meta.profile` for the SDC adaptive profile URL:
  `http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-adapt`
- If present → `adaptive`; otherwise → `static`
- Current DTR stub always returns static mode

**After DTR submit:**
- Success banner: "Documentation submitted ✓ — Reference: `QuestionnaireResponse/{id}`"
- Developer panel: raw QuestionnaireResponse JSON + copy button
- "Proceed to PAS Submission →" CTA button → calls `POST /api/sessions/{id}/pas/prepare`

---

##### Step 3 — PAS Bundle Review & Submit

Available once DTR is complete (or immediately if `pa_needed=true` and no SMART launch URL exists — `POST /api/sessions/{id}/pas/prepare` called automatically in that case).

**Bundle Editor (`BundleReviewForm`) — two tabs:**

**Edit Fields tab:**

| Field | UI Control | Editable | Default |
|-------|-----------|----------|---------|
| Patient | Text (read-only) | No | `Patient/test-patient-001` |
| Coverage | Text (read-only) | No | `Coverage/test-coverage-001` |
| Practitioner | Text (read-only) | No | `Practitioner/test-practitioner-001` |
| Payer | Text (read-only) | No | `Organization/test-payer-001` |
| Diagnosis Code | `Input` | Yes | `M54.5` |
| Service Code | `Input` | Yes | Scenario-derived |
| Service System | `Input` | Yes | Scenario-derived |
| Quantity | `Input type="number"` | Yes | `1` |
| Priority | `Select` | Yes | `normal` / `stat` / `deferred` |
| QR Reference | Text (read-only) | No | From DTR step (if present) |

- Each editable field change triggers `PATCH /api/sessions/{id}/pas/bundle` debounced 500 ms
- Auto-save indicator chip: "Saved ✓" / "Saving…" / "Save failed ✗"

**Raw JSON tab:** `RawJsonPanel` showing the full assembled Bundle JSON; updated after each successful PATCH; copy button.

**Submission:**
- "Submit Prior Authorization" primary button → `POST /api/sessions/{id}/pas/submit`
- Loading state: spinner + "Submitting to payer…"
- Error state: dismissible error banner with message

**Result display:**
- `DispositionBadge`: `Granted` (green + check) / `Denied` (red + X) / `Pended` (orange + clock)
- If `Granted`: prominent card "Authorization Granted — Auth # `{auth_number}`"
- If `Denied`: red banner "Prior Authorization Denied"
- If `Pended`:
  - "Check Status" button → `POST /api/sessions/{id}/pas/inquire`
  - Auto-poll: `useEffect` with `setInterval(10_000)`, max 3 automatic polls
  - After 3 polls with no resolution: "Still pending — click Check Status to retry manually"
  - On resolve to Granted: update `DispositionBadge` + show auth number card
- Developer panel (collapsed by default): raw `ClaimResponse` JSON + copy button

---

## 5. Questionnaire Flow Detail

### 5.1 Static flow

```
User clicks "Start DTR"
  → POST /api/sessions/{id}/dtr/start
      → GET Questionnaire from DTR stub :3002/fhir/r4/Questionnaire/{id}
      → detect_mode() → "static"
      → INSERT questionnaire_sessions row (mode="static", answered_items="[]")
      → UPDATE sessions.status = "dtr_in_progress"
  → Response: { mode: "static", questions: [...all 4 items...] }

User fills form, clicks "Submit Answers"
  → POST /api/sessions/{id}/dtr/submit  { items: [...4 answered items...] }
      → Build QuestionnaireResponse with DTR R4 profile
      → POST to DTR stub :3002/fhir/r4/QuestionnaireResponse
      → UPDATE questionnaire_sessions: qr_reference, submitted_at
      → UPDATE sessions.status = "dtr_complete"
  → Response: { qr_reference: "QuestionnaireResponse/<uuid>" }
```

### 5.2 Adaptive flow

```
User clicks "Start DTR"
  → POST /api/sessions/{id}/dtr/start
      → GET Questionnaire → detect_mode() → "adaptive"
      → POST $next-question with item=[] → receive first question
      → INSERT questionnaire_sessions (mode="adaptive", answered_items="[]")
  → Response: { mode: "adaptive", current_question: <item 1>, answered_count: 0 }

User answers Q1, clicks "Next →"
  → POST /api/sessions/{id}/dtr/next  { linkId: "1", answer: [{valueBoolean: true}] }
      → Append answer to DB answered_items
      → POST $next-question with item: [{linkId:"1", answer:[...]}]
  → Response: { done: false, current_question: <item 2>, answered_count: 1 }

  ...repeat for Q2, Q3, Q4...

After Q4, $next-question returns status: "completed"
  → Response: { done: true, answered_count: 4 }

User clicks "Submit"
  → POST /api/sessions/{id}/dtr/submit  (no body — uses stored answered_items)
      → Build QR from DB answered_items → POST to DTR stub → store qr_reference
  → Response: { qr_reference: "QuestionnaireResponse/<uuid>" }
```

---

## 6. Developer Mode

**Toggle:** "Dev Mode" switch in top-right of `AppShell` navbar. State persisted to `localStorage["devMode"]`.

**Features enabled in dev mode:**

| Feature | Location | Default (normal mode) |
|---------|----------|-----------------------|
| CDS Hook request JSON panel | Step 1 | Collapsed |
| CDS Hook response JSON panel | Step 1 | Collapsed |
| QuestionnaireResponse JSON | Step 2 after submit | Collapsed |
| PAS Bundle JSON | Step 3 bundle editor | Behind "Raw JSON" tab |
| ClaimResponse JSON | Step 3 result | Collapsed |
| Network request log | Bottom of every page | Hidden |

The network log intercepts calls via a custom `apiFetch` wrapper in `ui/src/api/client.ts`
which appends `{timestamp, method, url, status, durationMs}` entries to a module-level
array. `NetworkLog` component subscribes via a custom `EventTarget`.

---

## 7. Implementation Sprints

### Sprint 7 — EHR API Backend Foundation

**Goal:** Runnable FastAPI app on port 8000 with DB init and utility endpoints.

1. Create `src/api/` package: `__init__.py`, `main.py`, `db.py`, `routers/`, `services/`
2. `src/api/db.py`:
   - `init_db(db_path: str)` — `CREATE TABLE IF NOT EXISTS` for all 4 tables; enable WAL mode
   - `get_db()` — async context manager yielding `aiosqlite.Connection`
3. `src/api/main.py`:
   - `lifespan` calls `init_db("sessions.db")`
   - `CORSMiddleware`: allow `http://localhost:5173`
   - Include routers: `utility`, `sessions`, `dtr`, `pas`
4. Add `aiosqlite>=0.20.0` to `pyproject.toml` `[project.dependencies]`
5. `src/api/routers/utility.py`: `GET /api/health`, `GET /api/scenarios`, `GET /api/hooks`, `POST /api/bootstrap`
6. Add `ehr-api` service to `docker-compose.yml`:
   `command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload`
7. Unit tests `tests/unit/test_api_utility.py` via `httpx.ASGITransport`

### Sprint 8 — Session Management + CRD Flow

**Goal:** `POST /api/sessions` fires CRD and stores results.

1. `src/api/services/crd_service.py`:
   - `fire_crd(hook, scenario_key, fhir_base_url, payer_cds_base_url)`:
     - Calls `build_*_context` (reuse from `src/hooks/`)
     - POSTs to CDS stub
     - Extracts `pa_needed` from `davinci-crd.coverage-information[0]["pa-needed"]`
     - Extracts `smart_url` from first card SMART link
     - Returns `(hook_request_json, response_json, pa_needed, smart_url)`
2. `src/api/routers/sessions.py`: all 4 session endpoints
3. `POST /api/sessions`: create row → fire CRD → INSERT `crd_results` → UPDATE session status → return combined response
4. Integration tests `tests/integration/test_api_sessions.py`: monkeypatch `src.hooks.base.fetch_resource`

### Sprint 9 — DTR Service

**Goal:** Full static and adaptive questionnaire flow.

1. `src/api/services/dtr_service.py`:
   - `detect_mode(questionnaire_json: dict) -> Literal["static", "adaptive"]`
   - `fetch_questionnaire(smart_url: str, dtr_base_url: str) -> dict`
   - `call_next_question(answered_items: list, questionnaire_url: str, dtr_base_url: str) -> tuple[dict | None, bool]`
   - `build_and_submit_qr(answered_items: list, questionnaire_url: str, dtr_base_url: str) -> str` (returns qr_reference)
2. `src/api/routers/dtr.py`: `POST /start`, `GET /dtr`, `POST /next`, `POST /submit`
3. `answered_items` stored as JSON string; updated atomically on each `/next` call
4. Integration tests `tests/integration/test_api_dtr.py`: static flow; adaptive flow (monkeypatch DTR stub via ASGITransport)

### Sprint 10 — PAS Bundle Service

**Goal:** Full PAS lifecycle — prepare, edit, submit, inquire.

1. `src/api/services/pas_service.py`:
   - `prepare_bundle(session, qr_reference) -> str` — calls `build_pas_bundle`; returns serialized JSON; INSERTs row
   - `apply_edits(bundle_json: str, edits: dict) -> str` — merge PATCH fields into bundle dict
   - `submit_bundle(bundle_json: str, pas_base_url: str) -> dict` — POST to `$submit`; parse `disposition` + `auth_number`
   - `inquire_bundle(bundle_json: str, pas_base_url: str) -> dict` — POST to `$inquire`
2. `src/api/routers/pas.py`: all 5 PAS endpoints
3. Integration tests `tests/integration/test_api_pas.py`: pa-required → Granted; auth-pending → Pended → inquire → Granted

### Sprint 11 — React App Scaffold

**Goal:** Running React app with routing, API wiring, and typed interfaces.

1. `npm create vite@latest ui -- --template react-ts`
2. Install: `tailwindcss postcss autoprefixer @tanstack/react-query react-router-dom class-variance-authority clsx lucide-react`
3. `npx shadcn@latest init`; add components: `button card badge dialog tabs switch input select toast alert`
4. `vite.config.ts`: `server.proxy: { "/api": "http://localhost:8000" }`
5. `ui/src/api/client.ts`: `apiFetch` wrapper with JSON parse, error throw, dev-mode network log append
6. `ui/src/types/index.ts`: interfaces — `Session`, `CRDResult`, `Card`, `QuestionnaireState`, `QuestionItem`, `PASBundle`, `PASResult`
7. Typed API modules: `sessions.ts`, `dtr.ts`, `pas.ts`, `util.ts`
8. `AppShell.tsx`: navbar with title + Dev Mode toggle (reads/writes `localStorage`)
9. `BrowserRouter` with routes: `/` → `Dashboard`, `/sessions/new` → `NewSession`, `/sessions/:id` → `SessionDetail`

### Sprint 12 — Dashboard + New Session UI

**Goal:** Users can see session history and create new sessions.

1. `Dashboard.tsx`: `useQuery({ queryKey: ["sessions"], queryFn: ..., refetchInterval: 5000 })`; table with `StatusBadge`; delete row with `AlertDialog` + `useMutation`
2. `StatusBadge.tsx`: status string → Tailwind classes + label text
3. `NewSession.tsx`: hook radio group + scenario radio group with code chips and outcome labels; `useMutation` for `POST /api/sessions`; `useNavigate` on success
4. Toast notifications for API errors; loading skeleton rows on Dashboard

### Sprint 13 — CRD + DTR UI

**Goal:** Full CRD card display and interactive questionnaire.

1. `CardDisplay.tsx`: indicator border, summary, collapsible detail, source link, extension section, SMART link buttons
2. `CoverageExtensionBadge.tsx`: parse `davinci-crd.coverage-information[0]`; render 3 colored pills
3. `JsonViewer.tsx`: `<pre>` block with copy-to-clipboard via `navigator.clipboard.writeText`
4. `StaticForm.tsx`: map items → `QuestionItem`; collect answers in `useReducer`; validate required; submit handler
5. `AdaptiveForm.tsx`: single `QuestionItem` display; "Next →" → `useMutation` for `/next`; handle `done: true`
6. `QuestionItem.tsx`: `switch(item.type)` → shadcn/ui `Switch` | `Input` | numeric `Input`; `onChange(linkId, answer)` callback
7. Step 1 + Step 2 sections wired in `SessionDetail.tsx` using `useQuery` for `GET /api/sessions/{id}`

### Sprint 14 — PAS Bundle Review + Submission UI

**Goal:** Editable bundle, submission, and disposition result display.

1. `BundleReviewForm.tsx`: "Edit Fields" + "Raw JSON" tabs; controlled inputs; debounced `useMutation` for PATCH; auto-save indicator
2. `RawJsonPanel.tsx`: refetched bundle JSON after each PATCH; copy button
3. `DispositionBadge.tsx`: Granted/Denied/Pended with icon and Tailwind color
4. Submit → `useMutation` for `POST /api/sessions/{id}/pas/submit`; loading + error states
5. Pended state: `useEffect` with `setInterval(10_000)`; max 3 auto-polls; manual "Check Status" button
6. Auth number card (green) displayed prominently on Granted
7. Step 3 section wired in `SessionDetail.tsx`

### Sprint 15 — Developer Mode + E2E Polish

**Goal:** Developer mode visible, E2E tests green, production build working.

1. Dev mode toggle in `AppShell.tsx`; propagate via React context (`DevModeContext`); conditionally render raw panels and `NetworkLog`
2. `NetworkLog.tsx`: scrollable table at page bottom; subscribe to custom `EventTarget` fed by `apiFetch`
3. Error boundary in `SessionDetail.tsx` with "Retry" button calling `queryClient.invalidateQueries`
4. `POST /api/bootstrap` called non-blocking in `AppShell.tsx` `useEffect` on mount
5. Playwright E2E tests:
   - `pa-required.spec.ts`: create session → assert 2 cards → "Start DTR" → fill static form → submit → prepare PAS → edit diagnosis code → submit → assert Granted + auth number
   - `pa-not-required.spec.ts`: create session → assert green "No PA Required" banner → assert Step 2 locked
   - `auth-pending.spec.ts`: create session → prepare + submit PAS → assert Pended → click "Check Status" → assert Granted
6. Add `ui` service to `docker-compose.yml`: `vite preview --port 5173`
7. FastAPI `StaticFiles(directory="ui/dist", html=True)` mount at `/` in `src/api/main.py`

---

## 8. Non-Functional Requirements

- Non-FHIR API responses (session CRUD, DB reads): under 200 ms
- React initial load: under 2 s on localhost (Vite dev server)
- SQLite WAL mode enabled for concurrent reads
- No authentication required (`ENABLE_AUTH=false` in `.env`)
- All FHIR resource payloads stored verbatim as JSON strings in SQLite — no parsing or field extraction
- Vite HMR and `uvicorn --reload` both supported in development
- Minimum viewport target: 1024 px wide
- No breaking changes to existing payer stubs (ports 3001–3003) or HAPI FHIR (port 8080)

---

## 9. New Files Summary

### Backend

```
src/api/__init__.py
src/api/main.py
src/api/db.py
src/api/routers/__init__.py
src/api/routers/sessions.py
src/api/routers/dtr.py
src/api/routers/pas.py
src/api/routers/utility.py
src/api/services/__init__.py
src/api/services/crd_service.py
src/api/services/dtr_service.py
src/api/services/pas_service.py
tests/unit/test_api_utility.py
tests/integration/test_api_sessions.py
tests/integration/test_api_dtr.py
tests/integration/test_api_pas.py
```

**New `pyproject.toml` dependency:** `aiosqlite>=0.20.0`

### Frontend

```
ui/package.json
ui/vite.config.ts
ui/tailwind.config.ts
ui/tsconfig.json
ui/vitest.config.ts
ui/src/api/client.ts
ui/src/api/sessions.ts
ui/src/api/dtr.ts
ui/src/api/pas.ts
ui/src/api/util.ts
ui/src/types/index.ts
ui/src/components/layout/AppShell.tsx
ui/src/components/layout/StepTimeline.tsx
ui/src/components/crd/CardDisplay.tsx
ui/src/components/crd/CoverageExtensionBadge.tsx
ui/src/components/dtr/StaticForm.tsx
ui/src/components/dtr/AdaptiveForm.tsx
ui/src/components/dtr/QuestionItem.tsx
ui/src/components/pas/BundleReviewForm.tsx
ui/src/components/pas/DispositionBadge.tsx
ui/src/components/pas/RawJsonPanel.tsx
ui/src/components/shared/StatusBadge.tsx
ui/src/components/shared/JsonViewer.tsx
ui/src/components/shared/NetworkLog.tsx
ui/src/pages/Dashboard.tsx
ui/src/pages/NewSession.tsx
ui/src/pages/SessionDetail.tsx
ui/src/hooks/useSession.ts
ui/src/hooks/useQuestionnaire.ts
ui/src/hooks/usePAS.ts
ui/e2e/pa-required.spec.ts
ui/e2e/pa-not-required.spec.ts
ui/e2e/auth-pending.spec.ts
```

---

## 10. Testing Strategy

| Layer | Tool | Scope | Location |
|-------|------|-------|----------|
| API unit | pytest + `httpx.ASGITransport` | All utility + session + DTR + PAS endpoints; mock payer stubs | `tests/unit/test_api_*.py` |
| API integration | pytest + ASGITransport for stubs | Full CRD→DTR→PAS lifecycle; monkeypatch `fetch_resource` | `tests/integration/test_api_*.py` |
| React component | Vitest + React Testing Library | Components in isolation; mock API responses | `ui/src/**/*.test.tsx` |
| E2E | Playwright | 3 critical user paths (pa-required, pa-not-required, auth-pending) | `ui/e2e/*.spec.ts` |

**E2E prerequisites:** HAPI FHIR (port 8080), all 3 stubs (3001–3003), EHR API (port 8000) all running.
