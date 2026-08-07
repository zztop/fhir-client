# FHIR Prior Authorization Test Harness

Da Vinci CRD 2.1.0 · DTR 2.1.0 · PAS 2.1.0 · FHIR R4 (4.0.1) · Python 3.12 + FastAPI · React 18 + TypeScript

## Setup

Only the payer stub services (CDS Hooks, DTR, PAS) run in Docker. HAPI FHIR, the
EHR API, and the React SPA run directly on the host, Docker-free — this makes it
possible to point the EHR API/UI at a real external payer instead of the stubs.

```bash
# Install dependencies (requires uv)
uv pip install -e ".[dev]"

# Copy env config
cp .env.example .env

# Start everything with one command: stub services (Docker) + HAPI FHIR + EHR API + UI (host)
./scripts/dev-up.sh
```

`scripts/dev-up.sh` is idempotent (safe to re-run — skips anything already up),
waits for each service to become ready, and re-bootstraps FHIR fixtures. Logs go
to `.dev/logs/*.log`, PIDs to `.dev/pids/*.pid` (both gitignored). It expects a
runnable HAPI FHIR Spring Boot artifact at `HAPI_WAR_PATH` (default
`~/hapi-fhir-local/main.war`), built natively — no Docker involved:

```bash
git clone https://github.com/hapifhir/hapi-fhir-jpaserver-starter ~/hapi-fhir-src
cd ~/hapi-fhir-src
# Requires JDK 17 + Maven (self-contained installs are fine, e.g. under ~/tools)
mvn clean install -DskipTests -Djdk.lang.Process.launchMechanism=vfork
mvn package -DskipTests spring-boot:repackage -Pboot
cp target/ROOT.war ~/hapi-fhir-local/main.war
```

To run pieces individually instead of the script:

```bash
docker compose up -d                           # stub payer services (CDS/DTR/PAS)
uvicorn src.api.main:app --reload --port 8000  # EHR API
python -m src.cli.main                         # legacy terminal CLI
cd ui && npm install && npm run dev            # React SPA
```

## Commands

| Task | Command |
|------|---------|
| Start full stack (idempotent) | `./scripts/dev-up.sh` |
| Lint (Python) | `ruff check src/ tests/` |
| Format (Python) | `ruff format src/ tests/` |
| Type check (Python) | `mypy src/` |
| Unit tests | `pytest tests/unit/ -v` |
| Integration tests | `pytest tests/integration/ -v` |
| All tests | `pytest -v` |
| Start stub payer services only | `docker compose up -d` |
| Lint (UI) | `cd ui && npm run lint` |
| Build (UI) | `cd ui && npm run build` |
| E2E tests (UI) | `cd ui && npm run test:e2e` |

## Service Ports

| Service | Port | Runs in |
|---------|------|---------|
| HAPI FHIR R4 | 8080 | Host |
| CDS Hooks stub (CRD) | 3001 | Docker |
| DTR stub | 3002 | Docker |
| PAS stub | 3003 | Docker |
| EHR API (FastAPI BFF) | 8000 | Host |
| React SPA (Vite dev / preview) | 5173 | Host |

HAPI FHIR is the EHR's own clinical data store (Patient/Coverage/Encounter/
Practitioner fixtures) — it's used by the EHR API to build CDS Hooks prefetch
and PAS bundles regardless of which payer (stub or real) is on the other end.
Swapping the stub payer services for a real payer only requires changing
`PAYER_CDS_BASE_URL` / `PAYER_DTR_BASE_URL` / `PAYER_PAS_BASE_URL` in `.env`;
HAPI FHIR keeps running independently of that choice.

## Project Layout

```
src/
  cli/          # Legacy terminal CLI entry point + questionary prompts
  api/          # EHR API (FastAPI BFF): routers/, services/, db.py, main.py — serves the React SPA
  ehr/          # EHR-side: context builders, CDS client, DTR client, PAS submitter
  payer/        # Stub payer: CDS Hooks server, DTR server, PAS server, card builders
  hooks/        # Per-hook context builder functions
  models/       # Pydantic models: CDS Hooks 2.0, CRD extensions, PAS types
  fhir/         # FHIR fixture loader + fixtures/
ui/             # React 18 + TypeScript SPA: pages/, components/, api/, hooks/, types/
specs/
  init-requirements.md   # Original CLI implementation spec
  ui-requirements.md     # EHR API + React SPA spec (sessions persisted to SQLite)
```

The EHR API (`src/api/`) reuses `src/hooks/*`, `src/ehr/*`, `src/fhir/*`, `src/models/*`
as-is; it does not duplicate CRD/DTR/PAS orchestration logic, only exposes it over REST.
Session, CRD result, questionnaire, and PAS submission state is persisted to `sessions.db`
(SQLite, project root) — separate from the FHIR resources held in HAPI FHIR.

## Spec

- `specs/init-requirements.md` — original architecture, sprint plan, and payer/CLI API reference.
- `specs/ui-requirements.md` — EHR API + React SPA architecture, DB schema, endpoint reference, component layout, and sprint plan (Sprints 7–15).
