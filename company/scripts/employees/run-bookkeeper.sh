#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

DATE_STR="$(date +%F)"
OUTPUT_PATH="$COMPANY_DIR/reports/raw/${DATE_STR}-bookkeeper-${1:-afternoon}.md"
STATE_PATH="$STATE_DIR/employees/bookkeeper.json"

with_lock "bookkeeper"

"$PYTHON_BIN" - "$COMPANY_DIR/portfolio/performance.json" "$COMPANY_DIR/portfolio/positions.json" "$COMPANY_DIR/portfolio/trades.json" > "$OUTPUT_PATH" <<'PY'
import json
import sys
from pathlib import Path

performance = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
positions = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
trades = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))[-5:]

print("# 장부 요약")
print()
print("## 손익 요약")
print(f"- 현금: {performance.get('cash', 0):,.0f}")
print(f"- 평가금액: {performance.get('market_value', 0):,.0f}")
print(f"- 실현손익: {performance.get('realized_pnl', 0):,.0f}")
print(f"- 총 손익: {performance.get('total_pnl', 0):,.0f}")
print()
print("## 보유 종목")
if positions.get('positions'):
    for item in positions['positions']:
        print(f"- {item['name']}: {item['quantity']}주, 평균단가 {item['avg_cost']:,.0f}, 평가손익 {item['unrealized_pnl']:,.0f}")
else:
    print("- 보유 종목 없음")
print()
print("## 최근 거래")
if trades:
    for item in reversed(trades):
        print(f"- {item['timestamp']} {item['side']} {item['name']} {item['price']:,.0f} x {item['quantity']}")
else:
    print("- 최근 거래 없음")
PY

cp "$OUTPUT_PATH" "$COMPANY_DIR/employees/bookkeeper/latest.md"
state_write "$STATE_PATH" "success" "$OUTPUT_PATH" ""
