# FHIR Prior Authorization Test Harness

Da Vinci CRD 2.1.0 · DTR 2.1.0 · PAS 2.1.0 · FHIR R4 (4.0.1) · Python 3.12 + FastAPI

## Setup

```bash
# Install dependencies (requires uv)
uv pip install -e ".[dev]"

# Copy env config
cp .env.example .env

# Start HAPI FHIR + stub payer services
docker compose up -d

# Run the EHR simulator CLI
python -m src.cli.main
```

## Commands

| Task | Command |
|------|---------|
| Lint | `ruff check src/ tests/` |
| Format | `ruff format src/ tests/` |
| Type check | `mypy src/` |
| Unit tests | `pytest tests/unit/ -v` |
| Integration tests | `pytest tests/integration/ -v` |
| All tests | `pytest -v` |
| Start HAPI FHIR only | `docker compose up hapi-fhir -d` |

## Service Ports

| Service | Port |
|---------|------|
| HAPI FHIR R4 | 8080 |
| CDS Hooks stub (CRD) | 3001 |
| DTR stub | 3002 |
| PAS stub | 3003 |

## Project Layout

```
src/
  cli/          # CLI entry point + questionary prompts
  ehr/          # EHR-side: context builders, CDS client, DTR client, PAS submitter
  payer/        # Stub payer: CDS Hooks server, DTR server, PAS server, card builders
  hooks/        # Per-hook context builder functions
  models/       # Pydantic models: CDS Hooks 2.0, CRD extensions, PAS types
  fhir/         # FHIR fixture loader + fixtures/
specs/
  init-requirements.md   # Full implementation spec
```

## Spec

See `specs/init-requirements.md` for the full architecture, sprint plan, and API endpoint reference.
