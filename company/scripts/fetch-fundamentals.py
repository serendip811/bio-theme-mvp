#!/usr/bin/env python3
import json
import math
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "reports" / "input"
WATCHLIST_PATH = INPUT_DIR / "watchlist.json"
SOURCE_NOTES_PATH = INPUT_DIR / "daily-source-notes.md"
NEWS_PATH = ROOT / "employees" / "news" / "latest.md"
OUTPUT_JSON = INPUT_DIR / "fundamentals.json"
OUTPUT_MD = INPUT_DIR / "fundamentals.md"
NAVER_URL = "https://finance.naver.com/item/main.naver?code={code}"
USER_AGENT = "Mozilla/5.0 (compatible; BioThemeMVP/1.0)"
KST = timezone(timedelta(hours=9))
FINANCING_KEYWORDS = ("유상증자", "CB", "BW", "전환사채", "신주인수권부사채", "자금조달")


def strip_urls(text: str) -> str:
    return re.sub(r"https?://\S+", "", text)


def fetch_html(code: str) -> str:
    req = urllib.request.Request(NAVER_URL.format(code=code), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", "ignore")


def clean_number(value: str):
    value = value.replace(",", "").replace("배", "").replace("원", "").replace("주", "").replace("%", "").strip()
    if value in {"", "N/A", "-", "적자", "적지", "흑전", "흑지"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def extract_single(pattern: str, text: str):
    match = re.search(pattern, text, re.S)
    return match.group(1).strip() if match else None


def extract_row_values(label: str, text: str):
    pattern = rf"<th[^>]*>\s*<strong>{re.escape(label)}</strong>.*?</th>(.*?)</tr>"
    match = re.search(pattern, text, re.S)
    if not match:
        return []
    row_html = match.group(1)
    cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
    values = []
    for cell in cells:
        stripped = re.sub(r"<.*?>", "", cell)
        stripped = re.sub(r"\s+", " ", stripped).strip()
        if stripped:
            values.append(stripped)
    return values


def extract_latest_ratio(label: str, text: str):
    values = extract_row_values(label, text)
    numeric = [clean_number(v) for v in values]
    numeric = [v for v in numeric if v is not None and not math.isnan(v)]
    return numeric[-1] if numeric else None


def extract_quarter_headers(text: str):
    anchor = text.find("최근 분기 실적")
    if anchor == -1:
        return []
    segment = text[anchor : anchor + 5000]
    raw_headers = re.findall(r"<th scope=\"col\"[^>]*>\s*([0-9]{4}\.[0-9]{2}(?:<em>&#40;E&#41;</em>)?)\s*</th>", segment)
    result = []
    for raw in raw_headers:
        label = unescape(re.sub(r"<.*?>", "", raw))
        result.append({"label": label.replace("(E)", "").strip(), "estimated": "&#40;E&#41;" in raw or "(E)" in label})
    return result


def extract_metric_series(label: str, text: str):
    headers = extract_quarter_headers(text)
    values = extract_row_values(label, text)
    series = []
    for header, value in zip(headers, values):
        numeric = clean_number(value)
        if numeric is None:
            continue
        series.append({"label": header["label"], "estimated": header["estimated"], "value": numeric})
    return series


def latest_actual(series, cutoff_label=None):
    filtered = [item for item in series if not item["estimated"]]
    if cutoff_label is not None:
        filtered = [item for item in filtered if item["label"] >= cutoff_label]
    return filtered[-1] if filtered else None


def latest_numeric(values):
    numeric = [clean_number(v) for v in values]
    numeric = [v for v in numeric if v is not None and not math.isnan(v)]
    return numeric[-1] if numeric else None


def parse_company(code: str):
    html = fetch_html(code)
    name = extract_single(r"<dt><strong>([^<]+)</strong></dt>", html) or code
    market_cap = clean_number(extract_single(r"시가총액\(억\)</span></th>.*?<td>([^<]+)</td>", html) or "")
    listed_shares = clean_number(extract_single(r"상장주식수</th>\s*<td><em>([^<]+)</em></td>", html) or "")
    foreign_ratio = clean_number(extract_single(r"외국인비율\(%\)</span></th>.*?<td>([^<]+)</td>", html) or "")
    debt_ratio = extract_latest_ratio("부채비율", html)
    quick_ratio = extract_latest_ratio("당좌비율", html)
    reserve_ratio = extract_latest_ratio("유보율", html)
    per = latest_numeric(extract_row_values("PER(배)", html))
    pbr = latest_numeric(extract_row_values("PBR(배)", html))

    sales_series = extract_metric_series("매출액", html)
    op_income_series = extract_metric_series("영업이익", html)
    net_income_series = extract_metric_series("당기순이익", html)

    latest_quarter_sales = latest_actual(sales_series, "2024.12")
    latest_quarter_op_income = latest_actual(op_income_series, "2024.12")
    latest_quarter_net_income = latest_actual(net_income_series, "2024.12")

    sales = latest_quarter_sales["value"] if latest_quarter_sales else latest_numeric(extract_row_values("매출액", html))
    op_income = latest_quarter_op_income["value"] if latest_quarter_op_income else latest_numeric(extract_row_values("영업이익", html))
    net_income = latest_quarter_net_income["value"] if latest_quarter_net_income else latest_numeric(extract_row_values("당기순이익", html))

    financial_strength = []
    if sales is not None:
        financial_strength.append(f"매출 {sales:,.0f}억")
    if op_income is not None:
        financial_strength.append(f"영업이익 {op_income:,.0f}억")
    if net_income is not None:
        financial_strength.append(f"순이익 {net_income:,.0f}억")

    interpretation = []
    if op_income is not None:
        if op_income > 0:
            interpretation.append("영업흑자 기반")
        elif op_income < 0:
            interpretation.append("영업적자 상태")
    if per is not None and per > 50:
        interpretation.append("고PER 구간")
    if pbr is not None and pbr > 3:
        interpretation.append("고PBR 구간")
    if market_cap is not None and market_cap > 100000:
        interpretation.append("대형주 체급")
    if debt_ratio is not None and debt_ratio > 100:
        interpretation.append("부채비율 경계")
    if quick_ratio is not None and quick_ratio < 100:
        interpretation.append("유동성 보수 확인 필요")

    return {
        "name": name,
        "code": code,
        "market_cap_okr": market_cap,
        "listed_shares": listed_shares,
        "foreign_ratio": foreign_ratio,
        "debt_ratio": debt_ratio,
        "quick_ratio": quick_ratio,
        "reserve_ratio": reserve_ratio,
        "per": per,
        "pbr": pbr,
        "sales_okr": sales,
        "operating_income_okr": op_income,
        "net_income_okr": net_income,
        "latest_quarter_label": latest_quarter_sales["label"] if latest_quarter_sales else None,
        "financial_strength": financial_strength,
        "interpretation_flags": interpretation,
        "cash_like_assets_okr": None,
        "debt_total_okr": None,
        "financing_risk_flags": [],
        "source_url": NAVER_URL.format(code=code),
    }


def format_num(value, suffix=""):
    if value is None:
        return "데이터 미입력"
    if abs(value - int(value)) < 1e-9:
        return f"{int(value):,}{suffix}"
    return f"{value:,.2f}{suffix}"


def build_markdown(items, updated_at: str):
    lines = [
        "# Fundamentals Snapshot",
        "",
        f"- 조회 시각: {updated_at}",
        f"- 종목 수: {len(items)}",
        "",
    ]
    if not items:
        lines.append("- 데이터 미입력")
        return "\n".join(lines) + "\n"
    for item in items:
        lines.extend([
            f"## {item['name']} ({item['code']})",
            f"- 시가총액: {format_num(item['market_cap_okr'], '억')}",
            f"- 상장주식수: {format_num(item['listed_shares'], '주')}",
            f"- 외국인소진율: {format_num(item['foreign_ratio'], '%')}",
            f"- 부채비율 / 당좌비율 / 유보율: {format_num(item['debt_ratio'], '%')} / {format_num(item['quick_ratio'], '%')} / {format_num(item['reserve_ratio'], '%')}",
            f"- PER / PBR: {format_num(item['per'])} / {format_num(item['pbr'])}",
            f"- 최근 분기({item['latest_quarter_label'] or '기준 미상'}) 매출 / 영업이익 / 순이익: {format_num(item['sales_okr'], '억')} / {format_num(item['operating_income_okr'], '억')} / {format_num(item['net_income_okr'], '억')}",
            f"- 현금성자산: {format_num(item['cash_like_assets_okr'], '억')}",
            f"- 총차입금: {format_num(item['debt_total_okr'], '억')}",
            f"- 자금조달/희석 리스크: {', '.join(item['financing_risk_flags']) if item['financing_risk_flags'] else '데이터 미입력'}",
            f"- 재무 메모: {', '.join(item['financial_strength']) if item['financial_strength'] else '데이터 미입력'}",
            f"- 해석 플래그: {', '.join(item['interpretation_flags']) if item['interpretation_flags'] else '데이터 미입력'}",
            f"- 링크: {item['source_url']}",
            "",
        ])
    return "\n".join(lines)


def main():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    watchlist = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8")) if WATCHLIST_PATH.exists() else {"items": []}
    source_text = SOURCE_NOTES_PATH.read_text(encoding="utf-8") if SOURCE_NOTES_PATH.exists() else ""
    news_text = NEWS_PATH.read_text(encoding="utf-8") if NEWS_PATH.exists() else ""
    combined_text = strip_urls(f"{source_text}\n{news_text}")
    items = []
    for row in watchlist.get("items", []):
        code = row.get("code")
        name = row.get("name", code)
        if not code:
            continue
        try:
            parsed = parse_company(code)
        except Exception:
            parsed = {
                "name": name,
                "code": code,
                "market_cap_okr": None,
                "listed_shares": None,
                "foreign_ratio": None,
                "debt_ratio": None,
                "quick_ratio": None,
                "reserve_ratio": None,
                "per": None,
                "pbr": None,
                "sales_okr": None,
                "operating_income_okr": None,
                "net_income_okr": None,
                "latest_quarter_label": None,
                "financial_strength": [],
                "interpretation_flags": ["기초체력 데이터 파싱 실패"],
                "cash_like_assets_okr": None,
                "debt_total_okr": None,
                "financing_risk_flags": [],
                "source_url": NAVER_URL.format(code=code),
            }

        financing_hits = []
        for keyword in FINANCING_KEYWORDS:
            if keyword in {"CB", "BW"}:
                pattern = rf"{re.escape(name)}.*(?<![A-Za-z]){re.escape(keyword)}(?![A-Za-z])|(?<![A-Za-z]){re.escape(keyword)}(?![A-Za-z]).*{re.escape(name)}"
            else:
                pattern = rf"{re.escape(name)}.*{re.escape(keyword)}|{re.escape(keyword)}.*{re.escape(name)}"
            if re.search(pattern, combined_text):
                financing_hits.append(keyword)
        parsed["financing_risk_flags"] = financing_hits
        if financing_hits:
            parsed["interpretation_flags"] = parsed.get("interpretation_flags", []) + ["최근 자금조달 키워드 확인"]
        items.append(parsed)

    updated_at = datetime.now(KST).isoformat(timespec="seconds")
    OUTPUT_JSON.write_text(json.dumps({"updated_at": updated_at, "items": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(build_markdown(items, updated_at), encoding="utf-8")


if __name__ == "__main__":
    main()
