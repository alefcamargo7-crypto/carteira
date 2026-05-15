"""
ASCII chart of Bitcoin price vs Power Law bands (terminal-friendly).
Uses matplotlib to save a PNG when a display is available.
"""

import math
from datetime import date, timedelta
from power_law import power_law_price, days_since_genesis, BAND_OFFSETS, GENESIS


def _price_to_bar(log_price: float, log_min: float, log_max: float, width: int = 50) -> int:
    if log_max <= log_min:
        return 0
    return int((log_price - log_min) / (log_max - log_min) * width)


def print_ascii_chart(current_price_usd: float, years: int = 4):
    """Print a simple ASCII chart showing past + future power law bands."""
    today = date.today()
    start = today - timedelta(days=years * 365)

    # Collect sample points (one per quarter)
    points = []
    d = start
    while d <= today + timedelta(days=365 * 2):
        days = days_since_genesis(d)
        fv = power_law_price(days, 0)
        floor = power_law_price(days, BAND_OFFSETS["floor"])
        ceiling = power_law_price(days, BAND_OFFSETS["ceiling"])
        points.append((d, fv, floor, ceiling))
        d += timedelta(days=91)  # quarterly

    prices = [current_price_usd]
    for _, fv, fl, ce in points:
        prices += [fv, fl, ce]
    log_min = math.log10(min(p for p in prices if p > 0)) - 0.1
    log_max = math.log10(max(prices)) + 0.1

    width = 55
    print("\n  Bitcoin · Power Law Chart")
    print("  " + "─" * (width + 20))
    print(f"  {'Data':<12} {'Piso':>10} {'Valor Justo':>12} {'Teto':>12}  Barra")
    print("  " + "─" * (width + 20))

    for d, fv, floor, ceiling in points:
        fv_bar = _price_to_bar(math.log10(fv), log_min, log_max, width)
        marker = "◆" if d >= today else "·"
        label = " ← HOJE" if abs((d - today).days) < 50 else ""
        print(
            f"  {d.isoformat():<12} "
            f"${floor:>9,.0f} "
            f"${fv:>11,.0f} "
            f"${ceiling:>11,.0f}  "
            f"{'·' * fv_bar}{marker}{label}"
        )

    # Current price line
    cur_bar = _price_to_bar(math.log10(current_price_usd), log_min, log_max, width)
    print("  " + "─" * (width + 20))
    print(f"  {'PREÇO ATUAL':<12} {'':>10} ${current_price_usd:>11,.0f} {'':>12}  {'─' * cur_bar}▶ ${current_price_usd:,.0f}")
    print("  " + "─" * (width + 20))


def save_chart_png(current_price_usd: float, output_path: str = "btc_power_law.png"):
    """Save a proper chart as PNG using matplotlib."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        import numpy as np
        from datetime import datetime

        today = date.today()
        start = date(2013, 1, 1)
        end = today + timedelta(days=365 * 3)

        dates = []
        d = start
        while d <= end:
            dates.append(d)
            d += timedelta(days=30)

        fv_prices = []
        floor_prices = []
        ceiling_prices = []
        support_prices = []
        overbought_prices = []

        for d in dates:
            days = days_since_genesis(d)
            fv_prices.append(power_law_price(days, 0))
            floor_prices.append(power_law_price(days, BAND_OFFSETS["floor"]))
            ceiling_prices.append(power_law_price(days, BAND_OFFSETS["ceiling"]))
            support_prices.append(power_law_price(days, BAND_OFFSETS["support"]))
            overbought_prices.append(power_law_price(days, BAND_OFFSETS["overbought"]))

        dt_dates = [datetime(d.year, d.month, d.day) for d in dates]

        fig, ax = plt.subplots(figsize=(14, 7))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#0d1117")

        ax.fill_between(dt_dates, floor_prices, ceiling_prices, alpha=0.08, color="#f7931a")
        ax.plot(dt_dates, ceiling_prices, "--", color="#ef4444", linewidth=1.2, label="Teto (bolha)")
        ax.plot(dt_dates, overbought_prices, ":", color="#f97316", linewidth=1.0, label="Sobrecomprado")
        ax.plot(dt_dates, fv_prices, "-", color="#f7931a", linewidth=2.0, label="Valor Justo (Power Law)")
        ax.plot(dt_dates, support_prices, ":", color="#22c55e", linewidth=1.0, label="Suporte")
        ax.plot(dt_dates, floor_prices, "--", color="#3b82f6", linewidth=1.2, label="Piso (fundo de ciclo)")

        # Mark today
        today_dt = datetime(today.year, today.month, today.day)
        ax.axvline(today_dt, color="#ffffff", linewidth=0.8, alpha=0.4, linestyle=":")
        ax.axhline(current_price_usd, color="#ffffff", linewidth=0.8, alpha=0.4, linestyle=":")
        ax.scatter([today_dt], [current_price_usd], color="#ffffff", zorder=5, s=60, label=f"Preço atual ${current_price_usd:,.0f}")

        ax.set_yscale("log")
        ax.set_xlabel("Data", color="#9ca3af")
        ax.set_ylabel("Preço BTC (USD, escala log)", color="#9ca3af")
        ax.set_title("Bitcoin · Power Law de Preços", color="#f7931a", fontsize=14, fontweight="bold")
        ax.tick_params(colors="#9ca3af")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        for spine in ax.spines.values():
            spine.set_edgecolor("#374151")
        ax.grid(True, color="#1f2937", linewidth=0.5)
        legend = ax.legend(facecolor="#1f2937", edgecolor="#374151", labelcolor="#d1d5db", fontsize=9)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close()
        return output_path
    except Exception as e:
        return None
