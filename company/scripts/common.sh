#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPANY_DIR="$ROOT_DIR/company"
STATE_DIR="$COMPANY_DIR/state"
LOG_DIR="$COMPANY_DIR/logs"
LOCK_DIR="$STATE_DIR/locks"
CODEX_BIN="${CODEX_BIN:-/usr/local/bin/codex}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "$LOG_DIR" "$LOCK_DIR" "$COMPANY_DIR/reports/morning" "$COMPANY_DIR/reports/afternoon" "$COMPANY_DIR/reports/raw" "$COMPANY_DIR/output/assets" "$COMPANY_DIR/output/morning" "$COMPANY_DIR/output/afternoon" "$COMPANY_DIR/output/portfolio"

timestamp() {
  date +"%Y-%m-%dT%H:%M:%S%z"
}

state_write() {
  local path="$1"
  local status="$2"
  local output_path="$3"
  local error_message="$4"
  "$PYTHON_BIN" - "$path" "$status" "$output_path" "$error_message" <<'PY'
import json
import sys
from datetime import datetime

path, status, output_path, error_message = sys.argv[1:5]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
data["last_run_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
data["last_status"] = status
data["last_output"] = output_path or None
data["last_error"] = error_message or None
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY
}

ceo_state_write() {
  local report_name="$1"
  local status="$2"
  local error_message="$3"
  "$PYTHON_BIN" - "$STATE_DIR/ceo.json" "$report_name" "$status" "$error_message" <<'PY'
import json
import sys
from datetime import datetime

path, report_name, status, error_message = sys.argv[1:5]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
data["last_run_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
data["last_report"] = report_name or None
data["last_status"] = status
data["last_error"] = error_message or None
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY
}

with_lock() {
  local name="$1"
  local lock_path="$LOCK_DIR/$name.lock"
  if ! mkdir "$lock_path" 2>/dev/null; then
    echo "Lock already held: $name" >&2
    exit 1
  fi
  trap "rmdir '$lock_path'" EXIT
}

notify_discord() {
  local message="$1"
  if [ -z "${DISCORD_WEBHOOK_URL:-}" ]; then
    return 0
  fi
  local payload
  payload="$($PYTHON_BIN -c 'import json,sys; print(json.dumps({"content": sys.argv[1]}))' "$message")"
  curl -fsS -X POST "$DISCORD_WEBHOOK_URL" -H "Content-Type: application/json" -d "$payload" >/dev/null
}
