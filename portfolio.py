"""
Simple portfolio tracker. Stores DCA entries in a JSON file.
Each entry: date, brl_invested, btc_usd_price, btc_brl_price, btc_amount
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import date, datetime
from typing import Optional

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio.json")


@dataclass
class Entry:
    date: str
    brl_invested: float
    btc_usd_price: float
    btc_brl_price: float
    btc_amount: float
    zone: str
    multiplier: float


def _load() -> list[dict]:
    if not os.path.exists(PORTFOLIO_FILE):
        return []
    with open(PORTFOLIO_FILE) as f:
        return json.load(f)


def _save(entries: list[dict]):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def record_buy(brl_invested: float, btc_usd: float, btc_brl: float, zone: str, multiplier: float):
    entries = _load()
    btc_amount = brl_invested / btc_brl if btc_brl else 0
    entry = Entry(
        date=date.today().isoformat(),
        brl_invested=brl_invested,
        btc_usd_price=btc_usd,
        btc_brl_price=btc_brl,
        btc_amount=btc_amount,
        zone=zone,
        multiplier=multiplier,
    )
    entries.append(asdict(entry))
    _save(entries)
    return entry


def get_summary(current_btc_brl: Optional[float] = None) -> dict:
    entries = _load()
    if not entries:
        return {
            "total_entries": 0,
            "total_brl_invested": 0.0,
            "total_btc": 0.0,
            "avg_cost_brl": 0.0,
            "current_value_brl": None,
            "pnl_brl": None,
            "pnl_pct": None,
        }

    total_brl = sum(e["brl_invested"] for e in entries)
    total_btc = sum(e["btc_amount"] for e in entries)
    avg_cost = total_brl / total_btc if total_btc else 0

    current_value = total_btc * current_btc_brl if current_btc_brl else None
    pnl = (current_value - total_brl) if current_value is not None else None
    pnl_pct = (pnl / total_brl * 100) if (pnl is not None and total_brl) else None

    return {
        "total_entries": len(entries),
        "total_brl_invested": total_brl,
        "total_btc": total_btc,
        "avg_cost_brl": avg_cost,
        "current_value_brl": current_value,
        "pnl_brl": pnl,
        "pnl_pct": pnl_pct,
        "entries": entries,
    }
