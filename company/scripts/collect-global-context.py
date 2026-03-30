#!/usr/bin/env python3
import argparse
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
OUTPUT_JSON = INPUT_DIR / "global-context.json"
OUTPUT_MD = INPUT_DIR / "global-context.md"
RSS_BASE = "https://news.google.com/rss/search"
USER_AGENT = "Mozilla/5.0 (compatible; BioThemeMVP/1.0)"
KST = timezone(timedelta(hours=9))

THEME_QUERIES = {
    "biosimilar": ["biosimilar FDA guidance biotech", "biosimilar Europe approval biotech"],
    "adc": ["ADC biotech approval trial failure", "antibody drug conjugate biotech deal"],
    "obesity": ["obesity biotech trial approval", "GLP-1 biotech licensing deal"],
    "cdmo": ["biotech CDMO supply agreement expansion"],
    "cell_therapy": ["cell therapy trial approval setback biotech"],
}


def active_themes(source_text: str):
    picks = []
    mapping = {
        "biosimilar": ["바이오시밀러"],
        "adc": ["ADC"],
        "obesity": ["비만"],
        "cdmo": ["CDMO"],
        "cell_therapy": ["세포치료"],
    }
    for theme, patterns in mapping.items():
        if any(pattern in source_text for pattern in patterns):
            picks.append(theme)
    return picks or ["biosimilar", "adc"]


def fetch_rss(query: str):
    params = urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    req = urllib.request.Request(f"{RSS_BASE}?{params}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def parse_items(payload: bytes, theme: str, query: str):
    root = ET.fromstring(payload)
    items = []
    for item in root.findall("./channel/item")[:4]:
        title = html.unescape(item.findtext("title", default="")).strip()
        title = re.sub(r"\s+-\s+[^-]+$", "", title)
        link = item.findtext("link", default="").strip()
        pub_date = item.findtext("pubDate", default="").strip()
        try:
            published_at = parsedate_to_datetime(pub_date).astimezone(KST).isoformat(timespec="seconds")
        except Exception:
            published_at = None
        if title:
            items.append({"theme": theme, "query": query, "title": title, "link": link, "published_at": published_at})
    return items


def build_markdown(themes, items, updated_at: str):
    lines = ["# Global Context", "", f"- 생성 시각: {updated_at}", f"- 활성 테마: {', '.join(themes)}", ""]
    if not items:
        lines.append("- 데이터 미입력")
        return "\n".join(lines) + "\n"
    for theme in themes:
        theme_items = [item for item in items if item["theme"] == theme][:4]
        lines.append(f"## {theme}")
        if not theme_items:
            lines.append("- 데이터 미입력")
            lines.append("")
            continue
        for item in theme_items:
            lines.append(f"- {item['title']} | {item['published_at'] or '시각 미확인'}")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.parse_args()
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_text = SOURCE_NOTES_PATH.read_text(encoding="utf-8") if SOURCE_NOTES_PATH.exists() else ""
    themes = active_themes(source_text)
    items = []
    seen = set()
    for theme in themes:
        for query in THEME_QUERIES.get(theme, []):
            try:
                payload = fetch_rss(query)
            except Exception:
                continue
            for item in parse_items(payload, theme, query):
                key = item["title"].lower()
                if key in seen:
                    continue
                seen.add(key)
                items.append(item)
    updated_at = datetime.now(KST).isoformat(timespec="seconds")
    OUTPUT_JSON.write_text(json.dumps({"updated_at": updated_at, "themes": themes, "items": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(build_markdown(themes, items, updated_at), encoding="utf-8")


if __name__ == "__main__":
    main()
