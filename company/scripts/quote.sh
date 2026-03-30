#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 '셀트리온' 'HLB펩'" >&2
  exit 1
fi

"$PYTHON_BIN" "$COMPANY_DIR/scripts/fetch-quote.py" "$@"
