#!/usr/bin/env python3
import argparse
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "reports" / "input"
RAW_DIR = ROOT / "reports" / "raw"
SOURCE_NOTES_PATH = INPUT_DIR / "daily-source-notes.md"
MANUAL_NOTES_PATH = INPUT_DIR / "manual-notes.md"
NEWS_JSON_PATH = INPUT_DIR / "daily-news.json"

KST = timezone(timedelta(hours=9))
USER_AGENT = "Mozilla/5.0 (compatible; BioThemeMVP/1.0)"
RSS_BASE = "https://news.google.com/rss/search"

QUERIES = [
    "국내 바이오",
    "국내 제약바이오 임상",
    "국내 바이오 기술수출",
    "국내 바이오 품목허가",
    "국내 바이오 CDMO",
    "국내 바이오 ADC",
    "국내 바이오 비만 치료제",
]

IMPORTANT_KEYWORDS = {
    "기술수출": 5,
    "품목허가": 5,
    "승인": 4,
    "임상": 4,
    "계약": 4,
    "공급": 3,
    "FDA": 4,
    "식약처": 4,
    "유상증자": 3,
    "CB": 2,
    "BW": 2,
    "대표이사": 2,
    "최대주주": 2,
    "CDMO": 3,
    "ADC": 3,
    "비만": 2,
    "바이오시밀러": 3,
    "LO": 4,
}

THEME_KEYWORDS = ["ADC", "비만", "바이오시밀러", "CDMO", "면역항암", "진단", "mRNA", "세포치료", "유전자치료"]


def fetch_rss(query: str):
    params = urllib.parse.urlencode({"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
    url = f"{RSS_BASE}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def clean_title(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"\s+-\s+[^-]+$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_item(item, query: str):
    title = clean_title(item.findtext("title", default=""))
    link = item.findtext("link", default="").strip()
    pub_date = item.findtext("pubDate", default="").strip()
    try:
        published = parsedate_to_datetime(pub_date).astimezone(KST).isoformat(timespec="seconds")
    except Exception:
        published = None
    return {"title": title, "link": link, "published_at": published, "query": query}


def score_title(title: str) -> int:
    score = 0
    for keyword, weight in IMPORTANT_KEYWORDS.items():
        if keyword.lower() in title.lower():
            score += weight
    if any(char.isdigit() for char in title):
        score += 1
    return score


def infer_themes(items):
    counts = Counter()
    for item in items:
        title = item["title"]
        for keyword in THEME_KEYWORDS:
            if keyword.lower() in title.lower():
                counts[keyword] += 1
    return [name for name, _ in counts.most_common(5)]


def build_notes(items, manual_notes: str):
    generated_at = datetime.now(KST).isoformat(timespec="seconds")
    if not items:
        return f"""# Daily Source Notes

- 자동 수집 시각: {generated_at}
- 자동 뉴스 수집 결과가 없습니다.

## 핵심 뉴스 후보
- 데이터 미입력

## 공시/재료 체크 포인트
- 데이터 미입력

## 테마 메모
- 데이터 미입력

## 수동 메모
{manual_notes.strip()}
"""

    top_items = items[:8]
    catalyst_items = [item for item in items if score_title(item["title"]) >= 4][:8]
    themes = infer_themes(items)
    if not themes:
        themes = ["데이터 기반 뚜렷한 테마 없음"]

    lines = [
        "# Daily Source Notes",
        "",
        f"- 자동 수집 시각: {generated_at}",
        f"- 수집 기사 수: {len(items)}",
        f"- 주요 검색 묶음: {', '.join(QUERIES[:4])}",
        "",
        "## 핵심 뉴스 후보",
    ]
    for item in top_items:
        published = item["published_at"] or "시각 미확인"
        lines.append(f"- {item['title']} | {published} | query={item['query']}")

    lines.extend(["", "## 공시/재료 체크 포인트"])
    if catalyst_items:
        for item in catalyst_items:
            lines.append(f"- {item['title']}")
    else:
        lines.append("- 강한 재료 키워드 기사 미포착")

    lines.extend(["", "## 테마 메모"])
    for theme in themes:
        lines.append(f"- {theme}")

    lines.extend(["", "## 원문 링크", ""])
    for item in top_items[:5]:
        lines.append(f"- {item['title']}: {item['link']}")

    lines.extend(["", "## 수동 메모", manual_notes.strip()])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Collect Korea biotech news and build daily source notes")
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    collected = []
    seen = set()
    for query in QUERIES:
        try:
            payload = fetch_rss(query)
        except Exception:
            continue
        root = ET.fromstring(payload)
        for item in root.findall("./channel/item"):
            parsed = parse_item(item, query)
            title_key = parsed["title"].lower()
            if not parsed["title"] or title_key in seen:
                continue
            seen.add(title_key)
            parsed["score"] = score_title(parsed["title"])
            collected.append(parsed)

    now = datetime.now(KST)
    recent = []
    for item in collected:
        published_at = item.get("published_at")
        if not published_at:
            continue
        try:
            published_dt = datetime.fromisoformat(published_at)
        except ValueError:
            continue
        age = now - published_dt
        if timedelta(days=0) <= age <= timedelta(days=14):
            recent.append(item)

    working_set = recent if recent else collected
    working_set.sort(key=lambda item: (item["score"], item["published_at"] or ""), reverse=True)
    collected = working_set[: args.limit]

    NEWS_JSON_PATH.write_text(json.dumps(collected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manual_notes = MANUAL_NOTES_PATH.read_text(encoding="utf-8") if MANUAL_NOTES_PATH.exists() else "- 데이터 미입력\n"
    SOURCE_NOTES_PATH.write_text(build_notes(collected, manual_notes), encoding="utf-8")


if __name__ == "__main__":
    main()
