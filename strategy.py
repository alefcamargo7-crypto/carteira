"""
Power-law-based DCA trading strategy.

Idea: invest a daily base amount (e.g. R$10), but scale the allocation up or down
depending on how cheap or expensive Bitcoin is relative to the power-law fair value.

Position bands (based on price vs model):
  FLOOR zone      (pos 0.00–0.20) → multiply by 3.0x  — extreme value, buy heavy
  SUPPORT zone    (pos 0.20–0.40) → multiply by 2.0x  — below fair value, buy more
  FAIR VALUE zone (pos 0.40–0.60) → multiply by 1.0x  — neutral DCA
  OVERBOUGHT zone (pos 0.60–0.80) → multiply by 0.5x  — above fair value, buy less
  CEILING zone    (pos 0.80–1.00) → multiply by 0.0x  — bubble territory, hold/skip

This keeps you buying more when BTC is cheap and less (or nothing) when it's
historically expensive. It is NOT financial advice.
"""

from dataclasses import dataclass
from power_law import price_position, band_prices, fair_value, model_deviation_pct
from datetime import date


@dataclass
class TradeSignal:
    zone: str
    multiplier: float
    daily_base_brl: float
    recommended_buy_brl: float
    btc_usd: float
    btc_brl: float
    position: float           # 0–1 within bands
    deviation_pct: float      # % above/below fair value
    fair_value_usd: float
    bands: dict[str, float]
    rationale: str


ZONES = [
    # (max_position, zone_name, multiplier, description)
    (0.20, "FLOOR",      3.0, "Fundo histórico — oportunidade extrema"),
    (0.40, "SUPPORT",    2.0, "Abaixo do valor justo — bom ponto de entrada"),
    (0.60, "FAIR VALUE", 1.0, "Próximo ao valor justo — DCA neutro"),
    (0.80, "OVERBOUGHT", 0.5, "Acima do valor justo — compra reduzida"),
    (1.01, "CEILING",    0.0, "Zona de bolha — aguardar correção"),
]


def get_signal(btc_usd: float, btc_brl: float, daily_base_brl: float = 10.0) -> TradeSignal:
    today = date.today()
    pos = price_position(btc_usd, today)
    dev = model_deviation_pct(btc_usd, today)
    fv = fair_value(today)
    bands = band_prices(today)

    zone_name, multiplier, rationale = "FAIR VALUE", 1.0, ""
    for max_pos, name, mult, desc in ZONES:
        if pos <= max_pos:
            zone_name, multiplier, rationale = name, mult, desc
            break

    recommended = round(daily_base_brl * multiplier, 2)

    return TradeSignal(
        zone=zone_name,
        multiplier=multiplier,
        daily_base_brl=daily_base_brl,
        recommended_buy_brl=recommended,
        btc_usd=btc_usd,
        btc_brl=btc_brl,
        position=pos,
        deviation_pct=dev,
        fair_value_usd=fv,
        bands=bands,
        rationale=rationale,
    )
