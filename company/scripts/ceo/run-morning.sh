#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

with_lock "ceo-morning"

DATE_STR="$(date +%F)"
REPORT_PATH="$COMPANY_DIR/reports/morning/${DATE_STR}.md"
PROMPT_PATH="$COMPANY_DIR/state/ceo-morning-prompt.txt"

"$SCRIPT_DIR/employees/run-news.sh" morning
"$SCRIPT_DIR/employees/run-chart.sh" morning
"$SCRIPT_DIR/employees/run-strategy.sh" morning

cat > "$PROMPT_PATH" <<EOF
당신은 국내 바이오 테마 투자 운영회사의 대표입니다.

오늘 날짜: $DATE_STR
보고 유형: 오전 보고

대표 지침:
$(cat "$COMPANY_DIR/ceo/instructions.md")

뉴스 담당 결과:
$(cat "$COMPANY_DIR/employees/news/latest.md")

차트 담당 결과:
$(cat "$COMPANY_DIR/employees/chart/latest.md")

전략 담당 결과:
$(cat "$COMPANY_DIR/employees/strategy/latest.md")

포트폴리오 성과:
$(cat "$COMPANY_DIR/portfolio/performance.json")

반드시 포함할 것:
- 오늘의 바이오 핵심 테마
- 장 시작 전 주목 종목
- 전일 대비 포트폴리오 요약

추가 제약:
- 라이브 웹 검색을 하지 않는다.
- 위에 제공된 직원 결과와 장부 정보만 사용한다.
- 비어 있는 정보는 '데이터 미입력'으로 표시한다.

최종 답변만 Markdown으로 출력하세요.
EOF

if "$CODEX_BIN" exec --skip-git-repo-check -C "$ROOT_DIR" --full-auto -o "$REPORT_PATH" - < "$PROMPT_PATH"; then
  ceo_state_write "morning" "success" ""
  "$PYTHON_BIN" "$COMPANY_DIR/scripts/build-pages.py" --date "$DATE_STR"
  notify_discord "[오전 보고 완료] ${DATE_STR} 오전 보고와 포트폴리오 페이지를 갱신했습니다."
else
  ceo_state_write "morning" "failed" "codex exec failed"
  exit 1
fi
