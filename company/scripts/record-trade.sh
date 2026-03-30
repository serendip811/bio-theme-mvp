#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 'BUY|종목명|체결가|수량'" >&2
  exit 1
fi

"$PYTHON_BIN" "$COMPANY_DIR/scripts/update-ledger.py" --trade "$1"
"$SCRIPT_DIR/employees/run-bookkeeper.sh" afternoon
"$PYTHON_BIN" "$COMPANY_DIR/scripts/build-pages.py" --date "$(date +%F)"
notify_discord "[체결 반영] $1"
