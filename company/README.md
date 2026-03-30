# Bio Theme MVP Company

This workspace bootstraps a small operating model for a Korea biotech theme investment company.

Core principles:
- no automated trading
- file state is the source of truth
- Codex CLI employees run on cron
- Discord webhook is used for outbound alerts

Main directories:
- `company/ceo/` - CEO instructions and notes
- `company/employees/` - employee role definitions
- `company/portfolio/` - trades, positions, performance
- `company/reports/` - internal raw reports
- `company/output/` - static files for GitHub Pages
- `company/scripts/` - cron-safe orchestration scripts
- `company/state/` - runtime state and locks

Quick start:
1. Export `DISCORD_WEBHOOK_URL` in your shell or cron environment.
2. Review role prompts in `company/employees/` and `company/ceo/`.
3. Optionally add manual notes to `company/reports/input/manual-notes.md`.
4. Run `company/scripts/refresh-source-notes.sh` to collect live web news.
5. Run `company/scripts/ceo/run-morning.sh` or `company/scripts/ceo/run-afternoon.sh`.
6. Run `company/scripts/quote.sh '셀트리온' 'HLB펩'` when you want on-demand price and volume data.
7. Or run `company/scripts/refresh-watchlist-quotes.sh` to auto-build a watchlist from news and fetch quotes.
8. Run `company/scripts/refresh-watchlist-fundamentals.sh` to fetch market cap and basic financials for watchlist names.
9. Point GitHub Pages at `company/output/` after committing to a repository.

Publication behavior:
- `company/scripts/ceo/run-morning.sh` auto-commits and pushes refreshed report artifacts after a successful run.
- `company/scripts/ceo/run-afternoon.sh` does the same for the afternoon cycle.
- GitHub Pages then redeploys automatically from the pushed commit.

Ledger update example:

```bash
python3 company/scripts/update-ledger.py --trade 'BUY|삼천당제약|125000|3'
python3 company/scripts/update-ledger.py --trade 'SELL|삼천당제약|128500|1'
```

Trade message format:
- `BUY|종목명|체결가|수량`
- `SELL|종목명|체결가|수량`
