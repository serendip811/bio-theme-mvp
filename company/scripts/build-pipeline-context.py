#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "reports" / "input"
SOURCE_NOTES_PATH = INPUT_DIR / "daily-source-notes.md"
WATCHLIST_PATH = INPUT_DIR / "watchlist.json"
OUTPUT_JSON = INPUT_DIR / "pipeline-context.json"
OUTPUT_MD = INPUT_DIR / "pipeline-context.md"
KST = timezone(timedelta(hours=9))

KEYWORDS = {
    "biosimilar": {"patterns": ["바이오시밀러", "시밀러"], "milestone": "식약처 가이드라인 해석과 개발기간 단축 수혜 확인", "risk": "정책 기대가 실제 승인속도 단축으로 이어지는지 불확실"},
    "adc": {"patterns": ["ADC"], "milestone": "전임상/임상 진입 및 파트너십 확인", "risk": "초기 파이프라인은 상업화 거리 멈"},
    "obesity": {"patterns": ["비만"], "milestone": "후속 임상 설계와 글로벌 경쟁약 대비 차별성 확인", "risk": "글로벌 경쟁이 매우 치열"},
    "cdmo": {"patterns": ["CDMO", "계약", "공급"], "milestone": "수주 공시의 매출 인식 여부 확인", "risk": "단발 뉴스가 반복 매출로 이어지지 않을 수 있음"},
    "cell_therapy": {"patterns": ["세포치료", "임상연구"], "milestone": "임상 연구 채택 후 실제 데이터 공개 시점 확인", "risk": "초기 임상은 표본 수와 재현성 한계가 큼"},
    "largest_holder": {"patterns": ["최대주주 변경"], "milestone": "경영 방향 변화와 자금 조달 계획 확인", "risk": "지배구조 이슈가 실체 없는 이벤트로 끝날 수 있음"},
}


def build_items(source_text: str, watchlist_payload):
    items = []
    symbols = {item["name"]: item for item in watchlist_payload.get("items", [])}
    for name, meta in symbols.items():
        snippets = []
        for line in source_text.splitlines():
            if name in line:
                snippets.append(line.strip("- "))
        snippet_text = " ".join(snippets)
        matched_keys = []
        for key, config in KEYWORDS.items():
            if any(pattern in snippet_text for pattern in config["patterns"]):
                matched_keys.append(key)
        if not matched_keys:
            continue
        next_milestones = []
        risks = []
        themes = []
        for key in matched_keys:
            cfg = KEYWORDS[key]
            next_milestones.append(cfg["milestone"])
            risks.append(cfg["risk"])
            themes.append(key)
        items.append({
            "name": name,
            "code": meta.get("code"),
            "score": meta.get("score"),
            "themes": themes,
            "evidence": snippets[:3],
            "next_milestones": list(dict.fromkeys(next_milestones)),
            "risks": list(dict.fromkeys(risks)),
        })
    return items


def build_markdown(items, updated_at: str):
    lines = ["# Pipeline Context", "", f"- 생성 시각: {updated_at}", f"- 대상 종목 수: {len(items)}", ""]
    if not items:
        lines.append("- 데이터 미입력")
        return "\n".join(lines) + "\n"
    for item in items:
        lines.append(f"## {item['name']} ({item['code']})")
        lines.append(f"- 테마 키: {', '.join(item['themes'])}")
        lines.append(f"- 근거: {' | '.join(item['evidence']) if item['evidence'] else '데이터 미입력'}")
        lines.append(f"- 다음 마일스톤: {' / '.join(item['next_milestones'])}")
        lines.append(f"- 실패 민감 포인트: {' / '.join(item['risks'])}")
        lines.append("")
    return "\n".join(lines)


def main():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_text = SOURCE_NOTES_PATH.read_text(encoding="utf-8") if SOURCE_NOTES_PATH.exists() else ""
    watchlist_payload = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8")) if WATCHLIST_PATH.exists() else {"items": []}
    items = build_items(source_text, watchlist_payload)
    updated_at = datetime.now(KST).isoformat(timespec="seconds")
    OUTPUT_JSON.write_text(json.dumps({"updated_at": updated_at, "items": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(build_markdown(items, updated_at), encoding="utf-8")


if __name__ == "__main__":
    main()
