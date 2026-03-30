#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

"$PYTHON_BIN" "$COMPANY_DIR/scripts/build-watchlist.py"
"$PYTHON_BIN" "$COMPANY_DIR/scripts/fetch-quote.py" --watchlist-file "$COMPANY_DIR/reports/input/watchlist.json"
