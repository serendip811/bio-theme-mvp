#!/usr/bin/env python3
import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "reports" / "input"
NEWS_PATH = ROOT / "employees" / "news" / "latest.md"
SOURCE_NOTES_PATH = INPUT_DIR / "daily-source-notes.md"
WATCHLIST_JSON_PATH = INPUT_DIR / "watchlist.json"
WATCHLIST_MD_PATH = INPUT_DIR / "watchlist.md"
CORP_LIST_URL = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"
USER_AGENT = "Mozilla/5.0 (compatible; BioThemeMVP/1.0)"
KST = timezone(timedelta(hours=9))
BIO_HINTS = ("바이오", "제약", "헬스", "의약", "의료", "진단", "세포", "백신", "펩")
IGNORE_NAMES = {"한국바이오의약품협회", "식약처", "FDA", "K바이오"}


def fetch_text(url: str, encoding: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode(encoding, "ignore")


def load_symbols():
    text = fetch_text(CORP_LIST_URL, "euc-kr")
    rows_html = re.findall(r"<tr>(.*?)</tr>", text, re.S)
    parsed_rows = []
    for row_html in rows_html:
        cells = [unescape(re.sub(r"<.*?>", "", cell)).strip() for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S)]
        if cells:
            parsed_rows.append(cells)

    header = parsed_rows[0]
    name_idx = header.index("회사명")
    code_idx = header.index("종목코드")
    sector_idx = header.index("업종") if "업종" in header else None

    rows = []
    for cols in parsed_rows[1:]:
        if len(cols) <= max(name_idx, code_idx):
            continue
        code = cols[code_idx].zfill(6)
        if not re.fullmatch(r"[0-9A-Z]{6}", code):
            continue
        sector = cols[sector_idx] if sector_idx is not None and len(cols) > sector_idx else ""
        if sector and not any(hint in sector for hint in BIO_HINTS) and not any(hint in cols[name_idx] for hint in BIO_HINTS):
            continue
        rows.append({"name": cols[name_idx], "code": code, "sector": sector})
    return rows


def score_symbol(symbol, text_blocks):
    name = symbol["name"]
    if name in IGNORE_NAMES:
        return 0
    score = 0
    reasons = []
    for label, text, weight in text_blocks:
        count = text.count(name)
        if count:
            score += count * weight
            reasons.append(f"{label} {count}회")
    if any(hint in name for hint in ("셀트리온", "HLB", "차백신", "알테오젠", "리가켐", "한미")):
        score += 1
    return score, reasons


def main():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    news_text = NEWS_PATH.read_text(encoding="utf-8") if NEWS_PATH.exists() else ""
    notes_text = SOURCE_NOTES_PATH.read_text(encoding="utf-8") if SOURCE_NOTES_PATH.exists() else ""
    symbols = load_symbols()
    text_blocks = [("뉴스 브리핑", news_text, 3), ("소스 노트", notes_text, 2)]

    ranked = []
    for symbol in symbols:
        scored = score_symbol(symbol, text_blocks)
        if isinstance(scored, tuple):
            score, reasons = scored
        else:
            score, reasons = 0, []
        if score <= 0:
            continue
        ranked.append({"name": symbol["name"], "code": symbol["code"], "score": score, "reasons": reasons})

    ranked.sort(key=lambda item: (item["score"], item["name"]), reverse=True)
    selected = ranked[:5]
    payload = {
        "updated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "symbols": [item["name"] for item in selected],
        "items": selected,
    }
    WATCHLIST_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Watchlist",
        "",
        f"- 생성 시각: {payload['updated_at']}",
        f"- 감시 종목 수: {len(selected)}",
        "",
    ]
    if selected:
        for item in selected:
            lines.append(f"- {item['name']} ({item['code']}): 점수 {item['score']} | 근거: {', '.join(item['reasons'])}")
    else:
        lines.append("- 감시 종목 없음")
    WATCHLIST_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
