#!/usr/bin/env bash
# Start the full local stack with one command:
#   - cds-server, dtr-server, pas-server  -> Docker (docker-compose.yml)
#   - HAPI FHIR R4                        -> host, native Java (no Docker)
#   - EHR API (FastAPI BFF)               -> host, uvicorn
#   - React SPA                           -> host, vite dev server
#
# Idempotent: re-running skips anything already listening on its port.
# Logs go to .dev/logs/*.log, PIDs to .dev/pids/*.pid (both gitignored).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DEV_DIR="$ROOT_DIR/.dev"
LOG_DIR="$DEV_DIR/logs"
PID_DIR="$DEV_DIR/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

HAPI_WAR_PATH="${HAPI_WAR_PATH:-$HOME/hapi-fhir-local/main.war}"
HAPI_PORT=8080
EHR_API_PORT=8000
UI_PORT=5173

port_up() {
  curl -s -o /dev/null --max-time 2 "http://localhost:$1$2"
}

wait_for() {
  local name="$1" port="$2" path="$3" timeout="$4"
  local waited=0
  until port_up "$port" "$path"; do
    if [ "$waited" -ge "$timeout" ]; then
      echo "✗ $name did not become ready within ${timeout}s — see $LOG_DIR/$name.log" >&2
      exit 1
    fi
    sleep 2
    waited=$((waited + 2))
  done
  echo "✓ $name ready on :$port (${waited}s)"
}

start_bg() {
  local name="$1"; shift
  nohup "$@" > "$LOG_DIR/$name.log" 2>&1 &
  echo $! > "$PID_DIR/$name.pid"
  disown
}

echo "==> Stub payer services (Docker: cds-server, dtr-server, pas-server)"
docker compose up -d

echo "==> HAPI FHIR R4 (native Java, :$HAPI_PORT)"
if port_up "$HAPI_PORT" "/fhir/metadata"; then
  echo "✓ HAPI FHIR already running on :$HAPI_PORT"
else
  if [ ! -f "$HAPI_WAR_PATH" ]; then
    echo "✗ HAPI FHIR WAR not found at $HAPI_WAR_PATH" >&2
    echo "  Set HAPI_WAR_PATH or extract it once via:" >&2
    echo "    docker create --name hapi-extract hapiproject/hapi:latest" >&2
    echo "    docker cp hapi-extract:/app/main.war $HAPI_WAR_PATH" >&2
    echo "    docker rm hapi-extract" >&2
    exit 1
  fi
  (
    cd "$(dirname "$HAPI_WAR_PATH")"
    start_bg hapi-fhir java --class-path "$(basename "$HAPI_WAR_PATH")" \
      -Dloader.path="$(basename "$HAPI_WAR_PATH")"'!/WEB-INF/classes/,'"$(basename "$HAPI_WAR_PATH")"'!/WEB-INF/' \
      -Dhapi.fhir.fhir_version=R4 \
      -Dhapi.fhir.allow_multiple_delete=true \
      -Dhapi.fhir.reuse_cached_search_results_millis=-1 \
      -Dserver.port="$HAPI_PORT" \
      org.springframework.boot.loader.PropertiesLauncher
  )
  wait_for hapi-fhir "$HAPI_PORT" "/fhir/metadata" 120
fi

echo "==> EHR API (uvicorn, :$EHR_API_PORT)"
if port_up "$EHR_API_PORT" "/docs"; then
  echo "✓ EHR API already running on :$EHR_API_PORT"
else
  start_bg ehr-api "$ROOT_DIR/.venv/bin/uvicorn" src.api.main:app --reload --port "$EHR_API_PORT"
  wait_for ehr-api "$EHR_API_PORT" "/docs" 30
fi

echo "==> Bootstrapping FHIR fixtures"
curl -s -X POST "http://localhost:$EHR_API_PORT/api/bootstrap" -o "$LOG_DIR/bootstrap.json"
echo "✓ fixtures loaded — see $LOG_DIR/bootstrap.json"

echo "==> React SPA (vite dev, :$UI_PORT)"
if port_up "$UI_PORT" "/"; then
  echo "✓ UI already running on :$UI_PORT"
else
  (cd "$ROOT_DIR/ui" && start_bg ui npm run dev)
  wait_for ui "$UI_PORT" "/" 30
fi

cat <<EOF

Stack is up:
  UI            http://localhost:$UI_PORT
  EHR API       http://localhost:$EHR_API_PORT/docs
  HAPI FHIR     http://localhost:$HAPI_PORT/fhir
  CDS stub      http://localhost:3001
  DTR stub      http://localhost:3002
  PAS stub      http://localhost:3003

Logs: $LOG_DIR/*.log   PIDs: $PID_DIR/*.pid
Stop host processes:  kill \$(cat $PID_DIR/*.pid) ; docker compose down
EOF
