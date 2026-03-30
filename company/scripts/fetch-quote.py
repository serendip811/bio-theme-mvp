#!/usr/bin/env python3
import argparse
import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "reports" / "input"
SNAPSHOT_PATH = INPUT_DIR / "market-snapshot.md"
QUOTES_PATH = INPUT_DIR / "quotes.json"
USER_AGENT = "Mozilla/5.0 (compatible; BioThemeMVP/1.0)"
KST = timezone(timedelta(hours=9))
CORP_LIST_URL = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"
NAVER_URL = "https://finance.naver.com/item/main.naver?code={code}"


def fetch_text(url: str, encoding: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode(encoding, "ignore")


def load_symbols():
    text = fetch_text(CORP_LIST_URL, "euc-kr")
    rows_html = re.findall(r"<tr>(.*?)</tr>", text, re.S)
    rows = []
    parsed_rows = []
    for row_html in rows_html:
        cells = [unescape(re.sub(r"<.*?>", "", cell)).strip() for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S)]
        if cells:
            parsed_rows.append(cells)
    header = parsed_rows[0]
    name_idx = header.index("회사명")
    code_idx = header.index("종목코드")
    market_idx = header.index("시장구분") if "시장구분" in header else None
    rows = []
    for cols in parsed_rows[1:]:
        if len(cols) <= max(name_idx, code_idx):
            continue
        code = cols[code_idx].zfill(6)
        if not re.fullmatch(r"[0-9A-Z]{6}", code):
            continue
        rows.append(
            {
                "name": cols[name_idx],
                "code": code,
                "sector": cols[market_idx] if market_idx is not None and len(cols) > market_idx else "",
            }
        )
    return rows


def resolve_symbol(query: str, symbols):
    normalized = query.strip().lower()
    exact = [row for row in symbols if row["name"].lower() == normalized or row["code"] == query.strip()]
    if exact:
        return exact[0]
    partial = [row for row in symbols if normalized in row["name"].lower()]
    if partial:
        return partial[0]
    raise ValueError(f"종목을 찾을 수 없습니다: {query}")


def extract(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text, re.S)
    if not match:
        raise ValueError(f"시세 파싱 실패: {label}")
    return match.group(1).strip()


def to_number(value: str):
    cleaned = value.replace(",", "").replace("%", "").replace("백만", "")
    cleaned = cleaned.replace("+", "").replace("-", "")
    return float(cleaned)


def parse_quote(code: str):
    html = fetch_text(NAVER_URL.format(code=code), "utf-8")
    name = extract(r"<dt><strong>([^<]+)</strong></dt>", html, "name")
    current = extract(r"<p class=\"no_today\">.*?<span class=\"blind\">([^<]+)</span>", html, "current")
    change_match = re.search(r"<p class=\"no_exday\">.*?<span class=\"ico [^\"]+\">([^<]+)</span>.*?<span class=\"blind\">([0-9.,]+)</span>.*?<span class=\"blind\">([0-9.,]+)</span>", html, re.S)
    if not change_match:
        raise ValueError("시세 파싱 실패: change")
    direction_text = change_match.group(1).strip()
    change_value = change_match.group(2).strip()
    change_rate = change_match.group(3).strip()
    open_price = extract(r"시가\s*([0-9,]+)</dd>", html, "open")
    high = extract(r"고가\s*([0-9,]+)</dd>", html, "high")
    low = extract(r"저가\s*([0-9,]+)</dd>", html, "low")
    volume = extract(r"거래량\s*([0-9,]+)</dd>", html, "volume")
    trading_value = extract(r"거래대금\s*([0-9,]+)백만</dd>", html, "trading value")

    signed_change = to_number(change_value)
    if "하락" in direction_text:
        signed_change *= -1
    rate = to_number(change_rate)
    if "하락" in direction_text:
        rate *= -1
    previous_close = int(to_number(current) - signed_change)
    gap = ((int(to_number(open_price)) - previous_close) / previous_close * 100) if previous_close else 0.0
    return {
        "name": name,
        "code": code,
        "current_price": int(to_number(current)),
        "previous_close": previous_close,
        "change": int(signed_change),
        "change_direction": direction_text,
        "change_rate": round(rate, 2),
        "open": int(to_number(open_price)),
        "high": int(to_number(high)),
        "low": int(to_number(low)),
        "gap_rate": round(gap, 2),
        "volume": int(to_number(volume)),
        "trading_value_million_krw": int(to_number(trading_value)),
        "source_url": NAVER_URL.format(code=code),
    }


def build_snapshot(items):
    updated_at = datetime.now(KST).isoformat(timespec="seconds")
    lines = [
        "# Market Snapshot",
        "",
        f"- 조회 시각: {updated_at}",
        f"- 조회 종목 수: {len(items)}",
        "",
    ]
    if not items:
        lines.append("- 조회 데이터가 없습니다.")
        return "\n".join(lines) + "\n"

    for item in items:
        lines.extend(
            [
                f"## {item['name']} ({item['code']})",
                f"- 현재가: {item['current_price']:,}",
                f"- 전일 종가: {item['previous_close']:,}",
                f"- 전일대비: {item['change']:+,} ({item['change_rate']:+.2f}%)",
                f"- 시가 갭: {item['gap_rate']:+.2f}%",
                f"- 시가/고가/저가: {item['open']:,} / {item['high']:,} / {item['low']:,}",
                f"- 거래량: {item['volume']:,}",
                f"- 거래대금: {item['trading_value_million_krw']:,}백만 원",
                f"- 링크: {item['source_url']}",
                "",
            ]
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Fetch on-demand market quotes for Korea stocks")
    parser.add_argument("symbols", nargs="*", help="Stock names or 6-digit codes")
    parser.add_argument("--watchlist-file", help="Path to watchlist json with symbols array")
    args = parser.parse_args()

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    symbols = load_symbols()
    requested = list(args.symbols)
    if args.watchlist_file:
        watchlist_payload = json.loads(Path(args.watchlist_file).read_text(encoding="utf-8"))
        requested.extend(watchlist_payload.get("symbols", []))
    requested = [item for item in requested if item]
    seen = set()
    deduped = []
    for item in requested:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    if not deduped:
        raise SystemExit("조회할 종목이 없습니다")
    items = []
    for query in deduped:
        resolved = resolve_symbol(query, symbols)
        quote = parse_quote(resolved["code"])
        items.append(quote)

    payload = {
        "updated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "items": items,
    }
    QUOTES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SNAPSHOT_PATH.write_text(build_snapshot(items), encoding="utf-8")


if __name__ == "__main__":
    main()
