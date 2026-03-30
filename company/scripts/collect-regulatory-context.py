#!/usr/bin/env python3
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "reports" / "input"
SOURCE_NOTES_PATH = INPUT_DIR / "daily-source-notes.md"
OUTPUT_JSON = INPUT_DIR / "regulatory-context.json"
OUTPUT_MD = INPUT_DIR / "regulatory-context.md"
USER_AGENT = "Mozilla/5.0 (compatible; BioThemeMVP/1.0)"
KST = timezone(timedelta(hours=9))
FDA_BIOLOGICS_RSS = "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/biologics/rss.xml"
GOOGLE_RSS = "https://news.google.com/rss/search"

THEME_TERMS = {
    "biosimilar": ["바이오시밀러", "biosimilar"],
    "adc": ["ADC", "antibody drug conjugate"],
    "obesity": ["비만", "obesity", "GLP-1"],
    "cdmo": ["CDMO", "CMO biologics"],
    "cell_therapy": ["세포치료", "cell therapy"],
}


def source_themes(source_text: str):
    active = []
    for theme, patterns in THEME_TERMS.items():
        if any(pattern in source_text for pattern in patterns[:1]):
            active.append(theme)
    return active or ["biosimilar", "adc"]


def fetch_xml(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def parse_rss(payload: bytes, source: str, theme: str):
    root = ET.fromstring(payload)
    items = []
    for item in root.findall("./channel/item")[:10]:
        title = html.unescape(item.findtext("title", default="")).strip()
        link = item.findtext("link", default="").strip()
        pub_date = item.findtext("pubDate", default="").strip()
        try:
            published_at = parsedate_to_datetime(pub_date).astimezone(KST).isoformat(timespec="seconds")
        except Exception:
            published_at = None
        if title:
            items.append({"source": source, "theme": theme, "title": title, "link": link, "published_at": published_at})
    return items


def google_query(query: str):
    params = urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    return fetch_xml(f"{GOOGLE_RSS}?{params}")


def collect(source_text: str):
    themes = source_themes(source_text)
    results = []
    seen = set()

    try:
        fda_items = parse_rss(fetch_xml(FDA_BIOLOGICS_RSS), "FDA", "biosimilar")
    except Exception:
        fda_items = []
    for item in fda_items:
        if any(term.lower() in item["title"].lower() for term in THEME_TERMS["biosimilar"] + THEME_TERMS["cell_therapy"]):
            key = item["title"].lower()
            if key not in seen:
                seen.add(key)
                results.append(item)

    for theme in themes:
        query = None
        if theme == "biosimilar":
            query = "site:ema.europa.eu biosimilar approval"
        elif theme == "adc":
            query = "site:fda.gov ADC trial hold approval"
        elif theme == "obesity":
            query = "site:fda.gov obesity GLP-1 approval"
        elif theme == "cell_therapy":
            query = "site:fda.gov cell therapy hold approval"
        if not query:
            continue
        try:
            items = parse_rss(google_query(query), "official-search", theme)
        except Exception:
            items = []
        for item in items[:3]:
            key = item["title"].lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
    return results


def build_markdown(items, updated_at: str):
    lines = ["# Regulatory Context", "", f"- 생성 시각: {updated_at}", f"- 항목 수: {len(items)}", ""]
    if not items:
        lines.append("- 데이터 미입력")
        return "\n".join(lines) + "\n"
    grouped = {}
    for item in items:
        grouped.setdefault(item["theme"], []).append(item)
    for theme, theme_items in grouped.items():
        lines.append(f"## {theme}")
        for item in theme_items[:4]:
            lines.append(f"- [{item['source']}] {item['title']} | {item['published_at'] or '시각 미확인'}")
        lines.append("")
    return "\n".join(lines)


def main():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_text = SOURCE_NOTES_PATH.read_text(encoding="utf-8") if SOURCE_NOTES_PATH.exists() else ""
    items = collect(source_text)
    updated_at = datetime.now(KST).isoformat(timespec="seconds")
    OUTPUT_JSON.write_text(json.dumps({"updated_at": updated_at, "items": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(build_markdown(items, updated_at), encoding="utf-8")


if __name__ == "__main__":
    main()
