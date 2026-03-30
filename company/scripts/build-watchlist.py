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
NAVER_URL = "https://finance.naver.com/item/main.naver?code={code}"
USER_AGENT = "Mozilla/5.0 (compatible; BioThemeMVP/1.0)"
KST = timezone(timedelta(hours=9))
BIO_HINTS = ("바이오", "제약", "헬스", "의약", "의료", "진단", "세포", "백신", "펩")
IGNORE_NAMES = {"한국바이오의약품협회", "식약처", "FDA", "K바이오"}
CATALYST_KEYWORDS = ("임상", "승인", "허가", "계약", "기술수출", "CDMO", "ADC", "비만", "최대주주", "유상증자", "CB", "BW")


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


def fetch_quote_html(code: str) -> str:
    req = urllib.request.Request(NAVER_URL.format(code=code), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", "ignore")


def extract_number(pattern: str, text: str):
    match = re.search(pattern, text, re.S)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def load_quote_summary(code: str):
    try:
        html = fetch_quote_html(code)
    except Exception:
        return {"market_cap_okr": None, "trading_value_million_krw": None}
    return {
        "market_cap_okr": extract_number(r"시가총액\(억\)</span></th>.*?<td>([0-9,]+)</td>", html),
        "trading_value_million_krw": extract_number(r"거래대금\s*([0-9,]+)백만</dd>", html),
    }


def count_mentions(name: str, text: str) -> int:
    pattern = rf"(?<![가-힣A-Za-z0-9]){re.escape(name)}(?![가-힣A-Za-z0-9])"
    return len(re.findall(pattern, text))


def score_symbol(symbol, text_blocks, catalyst_text, quote_summary):
    name = symbol["name"]
    if name in IGNORE_NAMES:
        return 0
    score = 0
    reasons = []
    for label, text, weight in text_blocks:
        count = count_mentions(name, text)
        if count:
            score += count * weight
            reasons.append(f"{label} {count}회")

    catalyst_hits = 0
    for keyword in CATALYST_KEYWORDS:
        if re.search(rf"{re.escape(name)}.*{re.escape(keyword)}|{re.escape(keyword)}.*{re.escape(name)}", catalyst_text):
            catalyst_hits += 1
    if catalyst_hits:
        score += catalyst_hits * 4
        reasons.append(f"직접 재료 {catalyst_hits}개")

    sector = symbol.get("sector", "")
    if any(hint in sector for hint in BIO_HINTS):
        score += 2
        reasons.append("바이오 업종")

    trading_value = quote_summary.get("trading_value_million_krw")
    if trading_value is not None:
        if trading_value >= 50000:
            score += 5
            reasons.append("거래대금 상위")
        elif trading_value >= 10000:
            score += 3
            reasons.append("거래대금 유의미")
        elif trading_value >= 1000:
            score += 1

    market_cap = quote_summary.get("market_cap_okr")
    if market_cap is not None:
        if 3000 <= market_cap <= 200000:
            score += 2
            reasons.append("시총 적정")
        elif market_cap < 500:
            score -= 2
            reasons.append("초소형 경계")

    return score, reasons


def main():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    news_text = NEWS_PATH.read_text(encoding="utf-8") if NEWS_PATH.exists() else ""
    notes_text = SOURCE_NOTES_PATH.read_text(encoding="utf-8") if SOURCE_NOTES_PATH.exists() else ""
    symbols = load_symbols()
    text_blocks = [("뉴스 브리핑", news_text, 3), ("소스 노트", notes_text, 2)]
    catalyst_text = f"{news_text}\n{notes_text}"

    ranked = []
    for symbol in symbols:
        mentions = count_mentions(symbol["name"], catalyst_text)
        if mentions == 0:
            continue
        quote_summary = load_quote_summary(symbol["code"])
        scored = score_symbol(symbol, text_blocks, catalyst_text, quote_summary)
        if isinstance(scored, tuple):
            score, reasons = scored
        else:
            score, reasons = 0, []
        if score <= 0:
            continue
        ranked.append({
            "name": symbol["name"],
            "code": symbol["code"],
            "score": score,
            "reasons": reasons,
            "market_cap_okr": quote_summary.get("market_cap_okr"),
            "trading_value_million_krw": quote_summary.get("trading_value_million_krw"),
        })

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
            market_cap = f", 시총 {item['market_cap_okr']:,}억" if item.get("market_cap_okr") is not None else ""
            trading_value = f", 거래대금 {item['trading_value_million_krw']:,}백만" if item.get("trading_value_million_krw") is not None else ""
            lines.append(f"- {item['name']} ({item['code']}): 점수 {item['score']} | 근거: {', '.join(item['reasons'])}{market_cap}{trading_value}")
    else:
        lines.append("- 감시 종목 없음")
    WATCHLIST_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
