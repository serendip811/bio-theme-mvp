#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <employee> <shift>" >&2
  exit 1
fi

EMPLOYEE="$1"
SHIFT="$2"
DATE_STR="$(date +%F)"
STATE_PATH="$STATE_DIR/employees/$EMPLOYEE.json"
ROLE_PATH="$COMPANY_DIR/employees/$EMPLOYEE/role.md"
LATEST_PATH="$COMPANY_DIR/employees/$EMPLOYEE/latest.md"
OUTPUT_PATH="$COMPANY_DIR/reports/raw/${DATE_STR}-${EMPLOYEE}-${SHIFT}.md"
PROMPT_PATH="$COMPANY_DIR/state/${EMPLOYEE}-${SHIFT}-prompt.txt"
SOURCE_NOTES_PATH="$COMPANY_DIR/reports/input/daily-source-notes.md"
MARKET_SNAPSHOT_PATH="$COMPANY_DIR/reports/input/market-snapshot.md"
WATCHLIST_PATH="$COMPANY_DIR/reports/input/watchlist.md"

with_lock "$EMPLOYEE"

cat > "$PROMPT_PATH" <<EOF
당신은 회사의 $EMPLOYEE 담당 직원입니다.

오늘 날짜: $DATE_STR
근무 구간: $SHIFT

다음 역할 정의를 엄격히 따르세요.
--- role start ---
$(cat "$ROLE_PATH")
--- role end ---

회사 운영 원칙:
- 실제 매매를 실행하지 않는다.
- 국내 바이오 테마만 다룬다.
- 파일 상태가 세션보다 우선이다.
- 한국어로 작성한다.
- 라이브 웹 검색을 하지 않는다. 아래 로컬 파일과 장부 정보만 사용한다.

로컬 소스 노트:
$(cat "$SOURCE_NOTES_PATH")

시장 스냅샷:
$(cat "$MARKET_SNAPSHOT_PATH")

감시 종목:
$(cat "$WATCHLIST_PATH")

참고 장부 요약:
$(cat "$COMPANY_DIR/portfolio/performance.json")

출력 형식:
- 최종 답변만 작성한다.
- Markdown으로 작성한다.
- 제목 1개와 핵심 bullet 위주로 정리한다.
- 사실과 해석을 구분한다.
- 정보가 비어 있으면 추정하지 말고 '데이터 미입력'이라고 적는다.
EOF

if "$CODEX_BIN" exec --skip-git-repo-check -C "$ROOT_DIR" --full-auto -o "$OUTPUT_PATH" - < "$PROMPT_PATH"; then
  cp "$OUTPUT_PATH" "$LATEST_PATH"
  state_write "$STATE_PATH" "success" "$OUTPUT_PATH" ""
else
  state_write "$STATE_PATH" "failed" "" "codex exec failed"
  exit 1
fi
