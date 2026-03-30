#!/usr/bin/env python3
import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "portfolio"
TRADES_PATH = PORTFOLIO_DIR / "trades.json"
POSITIONS_PATH = PORTFOLIO_DIR / "positions.json"
PERFORMANCE_PATH = PORTFOLIO_DIR / "performance.json"


@dataclass
class Trade:
    side: str
    name: str
    price: float
    quantity: int
    timestamp: str

    @property
    def amount(self) -> float:
        return self.price * self.quantity


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_trade(raw: str) -> Trade:
    pieces = [piece.strip() for piece in raw.split("|")]
    if len(pieces) != 4:
        raise ValueError("Trade format must be BUY|종목명|체결가|수량 or SELL|종목명|체결가|수량")
    side, name, price_text, quantity_text = pieces
    side = side.upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError("Trade side must be BUY or SELL")
    price = float(price_text)
    quantity = int(quantity_text)
    if price <= 0 or quantity <= 0:
        raise ValueError("Price and quantity must be positive")
    return Trade(side=side, name=name, price=price, quantity=quantity, timestamp=datetime.now().astimezone().isoformat(timespec="seconds"))


def update_positions(trades):
    positions = {}
    cash = 0.0
    total_realized = 0.0

    for item in trades:
        name = item["name"]
        pos = positions.setdefault(
            name,
            {
                "name": name,
                "quantity": 0,
                "avg_cost": 0.0,
                "market_price": item["price"],
                "market_value": 0.0,
                "cost_basis": 0.0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "unrealized_return": 0.0,
            },
        )

        side = item["side"]
        price = float(item["price"])
        quantity = int(item["quantity"])
        amount = price * quantity
        pos["market_price"] = price

        if side == "BUY":
            new_quantity = pos["quantity"] + quantity
            if new_quantity <= 0:
                raise ValueError(f"Invalid resulting quantity for {name}")
            pos["avg_cost"] = ((pos["avg_cost"] * pos["quantity"]) + amount) / new_quantity
            pos["quantity"] = new_quantity
            cash -= amount
        else:
            if pos["quantity"] < quantity:
                raise ValueError(f"Cannot sell more than holdings for {name}")
            realized = (price - pos["avg_cost"]) * quantity
            pos["realized_pnl"] += realized
            total_realized += realized
            pos["quantity"] -= quantity
            cash += amount
            if pos["quantity"] == 0:
                pos["avg_cost"] = 0.0

        pos["cost_basis"] = pos["avg_cost"] * pos["quantity"]
        pos["market_value"] = pos["market_price"] * pos["quantity"]
        pos["unrealized_pnl"] = pos["market_value"] - pos["cost_basis"]
        pos["unrealized_return"] = (pos["unrealized_pnl"] / pos["cost_basis"]) if pos["cost_basis"] else 0.0

    live_positions = [position for position in positions.values() if position["quantity"] > 0]
    live_positions.sort(key=lambda item: item["market_value"], reverse=True)

    invested_amount = sum(item["cost_basis"] for item in live_positions)
    market_value = sum(item["market_value"] for item in live_positions)
    unrealized_pnl = sum(item["unrealized_pnl"] for item in live_positions)
    total_pnl = total_realized + unrealized_pnl
    denominator = invested_amount if invested_amount else 1.0
    total_return = total_pnl / denominator if invested_amount else 0.0

    positions_payload = {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "positions": live_positions,
    }
    performance_payload = {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "cash": round(cash, 2),
        "invested_amount": round(invested_amount, 2),
        "market_value": round(market_value, 2),
        "realized_pnl": round(total_realized, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "total_pnl": round(total_pnl, 2),
        "total_return": round(total_return, 6),
    }
    return positions_payload, performance_payload


def main():
    parser = argparse.ArgumentParser(description="Update portfolio ledger from Discord trade strings")
    parser.add_argument("--trade", action="append", required=True, help="Trade string like BUY|종목명|체결가|수량")
    args = parser.parse_args()

    trades = load_json(TRADES_PATH, [])
    for raw_trade in args.trade:
      trade = parse_trade(raw_trade)
      trades.append(
          {
              "timestamp": trade.timestamp,
              "side": trade.side,
              "name": trade.name,
              "price": trade.price,
              "quantity": trade.quantity,
              "amount": trade.amount,
              "source": "discord-manual",
          }
      )

    positions_payload, performance_payload = update_positions(trades)

    save_json(TRADES_PATH, trades)
    save_json(POSITIONS_PATH, positions_payload)
    save_json(PERFORMANCE_PATH, performance_payload)


if __name__ == "__main__":
    main()
