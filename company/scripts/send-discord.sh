#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <message>" >&2
  exit 1
fi

notify_discord "$1"
