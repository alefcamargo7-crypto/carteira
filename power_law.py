"""
Bitcoin Power Law model.

Based on Harold Christopher Burger's research: Bitcoin price follows a power law
against time (days since genesis block). The relationship is:

  log10(price) = A * log10(days_since_genesis) + B

Which in linear space means: price = 10^B * days^A

Fair value sits on the regression line. The model also defines a "support floor"
(lower bound) and a "bubble ceiling" (upper bound) using known historical offsets.
"""

from datetime import date, datetime
import math

# Genesis block: 2009-01-03
GENESIS = date(2009, 1, 3)

# Power law coefficients (Burger/community consensus, fitted to all BTC history)
# log10(price) = A * log10(days) + B
POWER_LAW_A = 5.82
POWER_LAW_B = -17.01

# Offsets from fair value (in log10 space) for bands
BAND_OFFSETS = {
    "ceiling": +0.9,   # historical bubble top
    "overbought": +0.6,
    "fair_value": 0.0,
    "support": -0.4,
    "floor": -0.8,     # historical cycle bottom
}


def days_since_genesis(d: date | None = None) -> int:
    if d is None:
        d = date.today()
    return (d - GENESIS).days


def power_law_price(days: int, offset: float = 0.0) -> float:
    """Return the model price for a given number of days since genesis."""
    if days <= 0:
        return 0.0
    log_price = POWER_LAW_A * math.log10(days) + POWER_LAW_B + offset
    return 10 ** log_price


def fair_value(d: date | None = None) -> float:
    return power_law_price(days_since_genesis(d))


def band_prices(d: date | None = None) -> dict[str, float]:
    days = days_since_genesis(d)
    return {name: power_law_price(days, offset) for name, offset in BAND_OFFSETS.items()}


def price_position(current_price: float, d: date | None = None) -> float:
    """
    Returns a normalized position of the current price relative to the model bands.
    0.0 = floor, 0.5 = fair value, 1.0 = ceiling.
    """
    bands = band_prices(d)
    floor_p = bands["floor"]
    ceiling_p = bands["ceiling"]
    if ceiling_p <= floor_p:
        return 0.5
    pos = (math.log10(current_price) - math.log10(floor_p)) / (
        math.log10(ceiling_p) - math.log10(floor_p)
    )
    return max(0.0, min(1.0, pos))


def model_deviation_pct(current_price: float, d: date | None = None) -> float:
    """How far (%) is current price from the power-law fair value?"""
    fv = fair_value(d)
    return ((current_price - fv) / fv) * 100


def future_fair_value(years_from_now: float) -> float:
    future_date = date.today()
    days = days_since_genesis(future_date) + int(years_from_now * 365.25)
    return power_law_price(days)
