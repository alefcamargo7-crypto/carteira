"""
Bitcoin price feed via CoinGecko public API (no key required).
Falls back to a manual price if the request fails.
"""

import requests
from datetime import datetime

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
EXCHANGE_RATE_URL = "https://api.coingecko.com/api/v3/simple/price"


def _get_json(url: str, params: dict) -> dict | None:
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def get_btc_price_usd() -> float | None:
    data = _get_json(COINGECKO_URL, {"ids": "bitcoin", "vs_currencies": "usd"})
    if data and "bitcoin" in data:
        return float(data["bitcoin"]["usd"])
    return None


def get_usd_to_brl() -> float | None:
    """Fetch USD→BRL exchange rate via CoinGecko tether proxy."""
    # Use BRL as a vs_currency directly
    data = _get_json(COINGECKO_URL, {"ids": "bitcoin", "vs_currencies": "brl,usd"})
    if data and "bitcoin" in data:
        usd = data["bitcoin"].get("usd")
        brl = data["bitcoin"].get("brl")
        if usd and brl:
            return brl / usd
    return None


def get_btc_prices() -> dict:
    """Return BTC price in USD and BRL, plus USD/BRL rate."""
    data = _get_json(COINGECKO_URL, {"ids": "bitcoin", "vs_currencies": "usd,brl"})
    if data and "bitcoin" in data:
        usd = float(data["bitcoin"].get("usd", 0))
        brl = float(data["bitcoin"].get("brl", 0))
        rate = brl / usd if usd else 5.7
        return {"usd": usd, "brl": brl, "usd_brl": rate}
    return {"usd": None, "brl": None, "usd_brl": None}
