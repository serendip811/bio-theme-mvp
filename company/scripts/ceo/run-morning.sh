#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

with_lock "ceo-morning"

DATE_STR="$(date +%F)"
REPORT_PATH="$COMPANY_DIR/reports/morning/${DATE_STR}.md"
PROMPT_PATH="$COMPANY_DIR/state/ceo-morning-prompt.txt"

"$SCRIPT_DIR/refresh-source-notes.sh"
"$SCRIPT_DIR/employees/run-news.sh" morning
"$SCRIPT_DIR/refresh-watchlist-quotes.sh"
"$SCRIPT_DIR/refresh-watchlist-fundamentals.sh"
"$SCRIPT_DIR/refresh-pipeline-context.sh"
"$SCRIPT_DIR/refresh-global-context.sh"
"$SCRIPT_DIR/refresh-regulatory-context.sh"
"$SCRIPT_DIR/employees/run-chart.sh" morning
"$SCRIPT_DIR/employees/run-fundamental.sh" morning
"$SCRIPT_DIR/employees/run-pipeline.sh" morning
"$SCRIPT_DIR/employees/run-global.sh" morning
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

기업분석 담당 결과:
$(cat "$COMPANY_DIR/employees/fundamental/latest.md")

파이프라인 담당 결과:
$(cat "$COMPANY_DIR/employees/pipeline/latest.md")

해외 사례 담당 결과:
$(cat "$COMPANY_DIR/employees/global/latest.md")

규제/임상 정밀 컨텍스트:
$(cat "$COMPANY_DIR/reports/input/regulatory-context.md")

시장 스냅샷:
$(cat "$COMPANY_DIR/reports/input/market-snapshot.md")

감시 종목:
$(cat "$COMPANY_DIR/reports/input/watchlist.md")

포트폴리오 성과:
$(cat "$COMPANY_DIR/portfolio/performance.json")

반드시 포함할 것:
- 오늘의 바이오 핵심 테마
- 장 시작 전 주목 종목
- 매수 후보 / 관찰 후보 / 추격 금지 구분
- 전일 대비 포트폴리오 요약
- 직전 종가 대비 시가 갭과 거래대금 해석
- 기업 체력이나 밸류에이션 한 줄 코멘트
- 파이프라인 가능성과 해외 선행사례 한 줄 코멘트
- 규제/임상 정밀 소스(FDA/EMA/임상) 기반 확인 한 줄 코멘트

추가 제약:
- 라이브 웹 검색을 하지 않는다.
- 위에 제공된 직원 결과와 장부 정보만 사용한다.
- 비어 있는 정보는 '데이터 미입력'으로 표시한다.
- 전일 종가, 시가 갭, 거래대금이 있으면 이를 근거로 추천 구분을 명확히 적는다.
- 각 주목 종목에는 `체력/밸류`, `파이프라인`, `해외선행사례` 줄을 각각 1개씩 넣는다.
- `파이프라인 / 해외 선행사례 체크` 섹션에서 글로벌 지지/약화 요인을 3줄 이내로 정리한다.

섹션 형식:
- 오늘의 바이오 핵심 테마
- 장 시작 전 주목 종목
- 파이프라인 / 해외 선행사례 체크
- 매수 후보 / 관찰 후보 / 추격 금지
- 전일 대비 포트폴리오 요약
- 한 줄 결론

최종 답변만 Markdown으로 출력하세요.
EOF

if "$CODEX_BIN" exec --skip-git-repo-check -C "$ROOT_DIR" --full-auto -o "$REPORT_PATH" - < "$PROMPT_PATH"; then
  ceo_state_write "morning" "success" ""
  "$PYTHON_BIN" "$COMPANY_DIR/scripts/build-pages.py" --date "$DATE_STR"
  publish_reports "morning" "$DATE_STR"
  notify_discord "[오전 보고 완료] ${DATE_STR} 오전 보고와 포트폴리오 페이지를 갱신했습니다."
else
  ceo_state_write "morning" "failed" "codex exec failed"
  exit 1
fi
