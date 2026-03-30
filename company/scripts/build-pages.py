#!/usr/bin/env python3
import argparse
import html
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
PORTFOLIO_DIR = ROOT / "portfolio"
OUTPUT_DIR = ROOT / "output"


def ensure_dirs():
    for path in [OUTPUT_DIR, OUTPUT_DIR / "morning", OUTPUT_DIR / "afternoon", OUTPUT_DIR / "portfolio", OUTPUT_DIR / "assets"]:
        path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def md_to_html(text: str) -> str:
    blocks = []
    in_list = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            if in_list:
                blocks.append("</ul>")
                in_list = False
            continue
        escaped = html.escape(line)
        if line.startswith("# "):
            if in_list:
                blocks.append("</ul>")
                in_list = False
            blocks.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_list:
                blocks.append("</ul>")
                in_list = False
            blocks.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("- "):
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{html.escape(line[2:])}</li>")
        else:
            if in_list:
                blocks.append("</ul>")
                in_list = False
            blocks.append(f"<p>{escaped}</p>")
    if in_list:
        blocks.append("</ul>")
    return "\n".join(blocks)


def page(title: str, body: str, stylesheet_href: str) -> str:
    return f"""<!DOCTYPE html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{html.escape(title)}</title>
  <link rel=\"stylesheet\" href=\"{html.escape(stylesheet_href)}\">
</head>
<body>
  <main class=\"page\">
    {body}
  </main>
</body>
</html>
"""


def build_report_page(kind: str, report_date: str):
    source = REPORTS_DIR / kind / f"{report_date}.md"
    if source.exists():
        content = source.read_text(encoding="utf-8")
    else:
        label = "오전 보고" if kind == "morning" else "오후 보고"
        content = f"# {label}\n\n- 아직 생성되지 않았습니다.\n- `company/reports/templates/{kind}-template.md`를 기준으로 대표 보고를 생성하세요."
    body = f"<nav><a href=\"../index.html\">Home</a> <a href=\"../portfolio/index.html\">Portfolio</a></nav>{md_to_html(content)}"
    target = OUTPUT_DIR / kind / f"{report_date}.html"
    target.write_text(page(f"{kind} report {report_date}", body, "../assets/styles.css"), encoding="utf-8")


def format_money(value):
    return f"{value:,.0f}"


def build_portfolio_page():
    positions = load_json(PORTFOLIO_DIR / "positions.json", {"positions": []})
    performance = load_json(PORTFOLIO_DIR / "performance.json", {})
    trades = load_json(PORTFOLIO_DIR / "trades.json", [])[-10:]

    rows = []
    for item in positions.get("positions", []):
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['name'])}</td>"
            f"<td>{item['quantity']}</td>"
            f"<td>{format_money(item['avg_cost'])}</td>"
            f"<td>{format_money(item['market_price'])}</td>"
            f"<td>{format_money(item['unrealized_pnl'])}</td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='5'>보유 종목이 없습니다.</td></tr>")

    trade_rows = []
    for item in reversed(trades):
        trade_rows.append(
            "<tr>"
            f"<td>{html.escape(item['timestamp'])}</td>"
            f"<td>{html.escape(item['side'])}</td>"
            f"<td>{html.escape(item['name'])}</td>"
            f"<td>{format_money(item['price'])}</td>"
            f"<td>{item['quantity']}</td>"
            "</tr>"
        )
    if not trade_rows:
        trade_rows.append("<tr><td colspan='5'>최근 거래가 없습니다.</td></tr>")

    body = f"""
    <nav><a href=\"../index.html\">Home</a></nav>
    <h1>포트폴리오 현황</h1>
    <section class=\"cards\">
      <article class=\"card\"><strong>현금</strong><span>{format_money(performance.get('cash', 0))}</span></article>
      <article class=\"card\"><strong>평가금액</strong><span>{format_money(performance.get('market_value', 0))}</span></article>
      <article class=\"card\"><strong>실현손익</strong><span>{format_money(performance.get('realized_pnl', 0))}</span></article>
      <article class=\"card\"><strong>총 손익</strong><span>{format_money(performance.get('total_pnl', 0))}</span></article>
    </section>
    <h2>보유 종목</h2>
    <table>
      <thead><tr><th>종목명</th><th>수량</th><th>평균단가</th><th>현재가</th><th>평가손익</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <h2>최근 거래</h2>
    <table>
      <thead><tr><th>시각</th><th>구분</th><th>종목명</th><th>체결가</th><th>수량</th></tr></thead>
      <tbody>{''.join(trade_rows)}</tbody>
    </table>
    """
    (OUTPUT_DIR / "portfolio" / "index.html").write_text(page("Portfolio", body, "../assets/styles.css"), encoding="utf-8")


def build_index(report_date: str):
    body = f"""
    <h1>국내 바이오 테마 운영 대시보드</h1>
    <p>기준일: {html.escape(report_date)}</p>
    <section class=\"cards\">
      <a class=\"card link\" href=\"morning/{html.escape(report_date)}.html\">오전 보고</a>
      <a class=\"card link\" href=\"afternoon/{html.escape(report_date)}.html\">오후 보고</a>
      <a class=\"card link\" href=\"portfolio/index.html\">포트폴리오 현황</a>
    </section>
    """
    (OUTPUT_DIR / "index.html").write_text(page("Bio Theme Board", body, "assets/styles.css"), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build GitHub Pages output")
    parser.add_argument("--date", default=datetime.now().strftime("%F"))
    args = parser.parse_args()

    ensure_dirs()
    build_report_page("morning", args.date)
    build_report_page("afternoon", args.date)
    build_portfolio_page()
    build_index(args.date)


if __name__ == "__main__":
    main()
