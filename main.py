#!/usr/bin/env python3
"""
Bitcoin Power Law Trade System
================================
DCA inteligente guiado pela Power Law do Bitcoin.

Uso:
  python main.py                          # relatório diário + sinal
  python main.py --buy                    # registra compra de hoje
  python main.py --buy --amount 25.50     # registra compra com valor personalizado
  python main.py --portfolio              # extrato da carteira
  python main.py --chart                  # gera gráfico PNG
  python main.py --simulate               # simula DCA desde 2020
  python main.py --forecast               # projeção de preço futuro
"""

import argparse
import math
import sys
from datetime import date, timedelta

from price_feed import get_btc_prices
from power_law import fair_value, band_prices, future_fair_value, days_since_genesis
from strategy import get_signal
from portfolio import record_buy, get_summary

# ─── ANSI colors ──────────────────────────────────────────────────────────────
R = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ORANGE = "\033[38;5;214m"
GREEN = "\033[38;5;82m"
RED = "\033[38;5;196m"
BLUE = "\033[38;5;33m"
YELLOW = "\033[38;5;220m"
CYAN = "\033[38;5;51m"
GRAY = "\033[38;5;244m"

ZONE_COLORS = {
    "FLOOR": GREEN + BOLD,
    "SUPPORT": GREEN,
    "FAIR VALUE": YELLOW,
    "OVERBOUGHT": ORANGE,
    "CEILING": RED + BOLD,
}

ZONE_EMOJI = {
    "FLOOR": "🟢",
    "SUPPORT": "💚",
    "FAIR VALUE": "🟡",
    "OVERBOUGHT": "🟠",
    "CEILING": "🔴",
}


def fmt_brl(v: float) -> str:
    return f"R${v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_usd(v: float) -> str:
    return f"${v:,.0f}"


def fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    color = RED if v > 0 else GREEN
    return f"{color}{sign}{v:.1f}%{R}"


def progress_bar(pos: float, width: int = 40) -> str:
    filled = int(pos * width)
    bar = "█" * filled + "░" * (width - filled)
    # Color gradient: green → yellow → red
    if pos < 0.4:
        color = GREEN
    elif pos < 0.6:
        color = YELLOW
    elif pos < 0.8:
        color = ORANGE
    else:
        color = RED
    return f"{color}[{bar}]{R} {pos*100:.0f}%"


def print_header():
    print()
    print(f"{ORANGE}{BOLD}  ₿  Bitcoin · Power Law Trade System  ₿{R}")
    print(f"{GRAY}  {'─' * 44}{R}")
    print(f"{DIM}  {date.today().strftime('%d/%m/%Y')}  ·  Dias desde o bloco gênesis: {days_since_genesis():,}{R}")
    print()


def print_signal(signal, prices):
    zcolor = ZONE_COLORS.get(signal.zone, YELLOW)
    zemoji = ZONE_EMOJI.get(signal.zone, "")

    print(f"{BOLD}  📡 SINAL DO DIA{R}")
    print(f"  {'─' * 44}")
    print(f"  BTC/USD        {BOLD}{fmt_usd(signal.btc_usd)}{R}")
    print(f"  BTC/BRL        {BOLD}{fmt_brl(signal.btc_brl)}{R}")
    print(f"  Câmbio USD/BRL {GRAY}{prices['usd_brl']:.3f}{R}")
    print()
    print(f"  Valor Justo (Power Law)  {CYAN}{fmt_usd(signal.fair_value_usd)}{R}")
    print(f"  Desvio do modelo         {fmt_pct(signal.deviation_pct)}")
    print()
    print(f"  Posição nas bandas:")
    print(f"  {progress_bar(signal.position)}")
    print()
    print(f"  Zona atual    {zcolor}{zemoji}  {signal.zone}{R}")
    print(f"  Racional      {DIM}{signal.rationale}{R}")
    print()

    # Bands table
    bands = signal.bands
    print(f"  {'Banda':<14} {'USD':>12}  {'BRL':>14}")
    print(f"  {'─'*14} {'─'*12}  {'─'*14}")
    band_labels = [
        ("ceiling",    "Teto",         RED),
        ("overbought", "Sobrecomprado",ORANGE),
        ("fair_value", "Valor Justo",  CYAN),
        ("support",    "Suporte",      GREEN),
        ("floor",      "Piso",         BLUE),
    ]
    usd_brl = prices.get("usd_brl") or 5.7
    for key, label, color in band_labels:
        usd_p = bands[key]
        brl_p = usd_p * usd_brl
        marker = " ◄" if (
            (key == "ceiling" and signal.zone == "CEILING") or
            (key == "overbought" and signal.zone == "OVERBOUGHT") or
            (key == "fair_value" and signal.zone == "FAIR VALUE") or
            (key == "support" and signal.zone == "SUPPORT") or
            (key == "floor" and signal.zone == "FLOOR")
        ) else ""
        print(f"  {color}{label:<14}{R} {fmt_usd(usd_p):>12}  {fmt_brl(brl_p):>14}{zcolor if marker else ''}{marker}{R}")
    print()


def print_recommendation(signal):
    print(f"{BOLD}  💰 RECOMENDAÇÃO DE HOJE{R}")
    print(f"  {'─' * 44}")
    print(f"  Base diária         {fmt_brl(signal.daily_base_brl)}")
    print(f"  Multiplicador       {BOLD}×{signal.multiplier}{R}")
    print(f"  {BOLD}Comprar hoje        {ORANGE}{fmt_brl(signal.recommended_buy_brl)}{R}")

    if signal.recommended_buy_brl == 0:
        print(f"\n  {RED}⚠  Zona de bolha: recomendado aguardar ou realizar lucros.{R}")
    elif signal.multiplier > 1:
        print(f"\n  {GREEN}✓  BTC abaixo do modelo: bom momento para acumular mais.{R}")
    else:
        print(f"\n  {YELLOW}→  DCA padrão: preço alinhado com o modelo.{R}")

    if signal.btc_brl > 0 and signal.recommended_buy_brl > 0:
        sats = int((signal.recommended_buy_brl / signal.btc_brl) * 1e8)
        print(f"  Sats recebidos      {GRAY}≈ {sats:,} sats{R}")
    print()


def print_portfolio(current_brl: float):
    summary = get_summary(current_brl)
    print(f"{BOLD}  📊 CARTEIRA{R}")
    print(f"  {'─' * 44}")
    if summary["total_entries"] == 0:
        print(f"  {GRAY}Nenhuma compra registrada ainda.{R}")
        print(f"  Use --buy para registrar sua primeira compra.\n")
        return

    print(f"  Compras registradas {summary['total_entries']}")
    print(f"  Total investido     {fmt_brl(summary['total_brl_invested'])}")
    print(f"  Total BTC           {summary['total_btc']:.8f} BTC")
    print(f"  Preço médio         {fmt_brl(summary['avg_cost_brl'])}")
    if summary["current_value_brl"] is not None:
        print(f"  Valor atual         {BOLD}{fmt_brl(summary['current_value_brl'])}{R}")
        pnl = summary["pnl_brl"]
        pnl_pct = summary["pnl_pct"]
        color = GREEN if pnl >= 0 else RED
        sign = "+" if pnl >= 0 else ""
        print(f"  P&L                 {color}{BOLD}{sign}{fmt_brl(pnl)} ({sign}{pnl_pct:.1f}%){R}")
    print()

    if summary.get("entries"):
        print(f"  {GRAY}Histórico de compras:{R}")
        print(f"  {GRAY}{'Data':<12} {'R$ Invest':>10} {'BTC/BRL':>12} {'Zona':<12} {'Sats':>10}{R}")
        print(f"  {GRAY}{'─'*12} {'─'*10} {'─'*12} {'─'*12} {'─'*10}{R}")
        for e in summary["entries"][-15:]:
            sats = int(e["btc_amount"] * 1e8)
            zcolor = ZONE_COLORS.get(e.get("zone", ""), GRAY)
            print(
                f"  {GRAY}{e['date']:<12}{R} "
                f"{fmt_brl(e['brl_invested']):>10} "
                f"{fmt_brl(e['btc_brl_price']):>12} "
                f"{zcolor}{e.get('zone','?'):<12}{R} "
                f"{GRAY}{sats:>10,}{R}"
            )
        if len(summary["entries"]) > 15:
            print(f"  {GRAY}... e mais {len(summary['entries'])-15} entradas anteriores{R}")
    print()


def print_forecast():
    print(f"{BOLD}  🔮 PROJEÇÃO POWER LAW (Valor Justo){R}")
    print(f"  {'─' * 44}")
    print(f"  {'Horizonte':<18} {'USD':>12}  {'BRL (≈5.7)':>14}")
    print(f"  {'─'*18} {'─'*12}  {'─'*14}")
    horizons = [
        ("6 meses", 0.5),
        ("1 ano", 1),
        ("2 anos", 2),
        ("3 anos", 3),
        ("5 anos", 5),
        ("10 anos", 10),
    ]
    for label, years in horizons:
        fv_usd = future_fair_value(years)
        fv_brl = fv_usd * 5.7
        print(f"  {label:<18} {fmt_usd(fv_usd):>12}  {fmt_brl(fv_brl):>14}")
    print()
    print(f"  {GRAY}Nota: projeção de 'valor justo' do modelo, não garantia de preço.{R}")
    print()


def simulate_dca(daily_base: float = 10.0, start_year: int = 2020):
    """Simulate daily DCA with power-law multiplier from start_year to today."""
    from power_law import price_position, model_deviation_pct
    from strategy import ZONES

    print(f"{BOLD}  🧪 SIMULAÇÃO DCA (R${daily_base:.0f}/dia desde {start_year}){R}")
    print(f"  {'─' * 44}")

    # Historical prices (rough monthly BTC/USD anchors for simulation)
    # We use a simplified model: assume price = power_law * random_factor
    # For a real backtest you'd need historical data — here we use the model itself
    # plus known cycle deviations as a stress test

    historical_scenarios = [
        # (label, price_usd) — represent different market conditions
        ("Jan/2020 (pré-bull)",   9_000),
        ("Mar/2020 (crash COVID)", 5_000),
        ("Dez/2020 (bull início)",30_000),
        ("Abr/2021 (ATH ciclo)",  60_000),
        ("Jul/2021 (correção)",   30_000),
        ("Nov/2021 (ATH)",        65_000),
        ("Jun/2022 (bear mínimo)", 19_000),
        ("Jan/2023 (recuperação)",23_000),
        ("Oct/2023 (ETF rumor)",  35_000),
        ("Mar/2024 (halving pre)", 70_000),
        ("Nov/2024 (pós-eleição)", 95_000),
    ]

    total_invested = 0.0
    total_btc = 0.0

    print(f"  {'Cenário':<28} {'Preço':>8} {'Zona':<12} {'R$':>7} {'BTC +':>12}")
    print(f"  {'─'*28} {'─'*8} {'─'*12} {'─'*7} {'─'*12}")

    for label, price in historical_scenarios:
        pos = price_position(price, date.today())
        zone = "FAIR VALUE"
        mult = 1.0
        for max_pos, name, m, _ in ZONES:
            if pos <= max_pos:
                zone, mult = name, m
                break
        invested = daily_base * mult * 30  # monthly equivalent
        btc = invested / (price * 5.7)  # rough BRL conversion
        total_invested += invested
        total_btc += btc
        zcolor = ZONE_COLORS.get(zone, YELLOW)
        print(
            f"  {label:<28} "
            f"{fmt_usd(price):>8} "
            f"{zcolor}{zone:<12}{R} "
            f"{fmt_brl(invested):>7} "
            f"{GRAY}{btc:.6f}{R}"
        )

    print(f"  {'─'*28} {'─'*8} {'─'*12} {'─'*7} {'─'*12}")
    print(f"  {'TOTAL SIMULADO':<28} {'':>8} {'':12} {fmt_brl(total_invested):>7} {GRAY}{total_btc:.6f}{R}")

    current_btc_brl = 550_000
    current_value = total_btc * current_btc_brl
    pnl = current_value - total_invested
    color = GREEN if pnl >= 0 else RED
    print()
    print(f"  Valor atual simulado  {color}{BOLD}{fmt_brl(current_value)}{R}  {GRAY}(BTC a R$550k){R}")
    print(f"  P&L simulado          {color}{BOLD}{'+' if pnl>=0 else ''}{fmt_brl(pnl)}{R}")
    print()
    print(f"  {GRAY}Simulação ilustrativa com preços históricos aproximados.{R}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Bitcoin Power Law Trade System")
    parser.add_argument("--buy", action="store_true", help="Registrar compra de hoje")
    parser.add_argument("--amount", type=float, help="Valor em BRL para registrar (default: recomendado)")
    parser.add_argument("--portfolio", action="store_true", help="Mostrar extrato da carteira")
    parser.add_argument("--chart", action="store_true", help="Gerar gráfico PNG")
    parser.add_argument("--simulate", action="store_true", help="Simular DCA histórico")
    parser.add_argument("--forecast", action="store_true", help="Projeção de valor justo futuro")
    parser.add_argument("--base", type=float, default=10.0, help="Valor base diário em BRL (default: 10)")
    parser.add_argument("--price", type=float, help="Forçar preço BTC/USD (offline)")
    args = parser.parse_args()

    print_header()

    # Fetch prices
    if args.price:
        usd_brl_rate = 5.75
        prices = {"usd": args.price, "brl": args.price * usd_brl_rate, "usd_brl": usd_brl_rate}
        print(f"  {GRAY}Usando preço manual: {fmt_usd(args.price)}{R}\n")
    else:
        print(f"  {DIM}Buscando cotações...{R}", end="\r")
        prices = get_btc_prices()
        if not prices["usd"]:
            print(f"  {RED}Erro ao buscar cotação. Use --price para modo offline.{R}")
            sys.exit(1)

    signal = get_signal(prices["usd"], prices["brl"], daily_base_brl=args.base)

    print_signal(signal, prices)
    print_recommendation(signal)

    # Optional modes
    if args.buy:
        amount = args.amount if args.amount else signal.recommended_buy_brl
        if amount <= 0:
            print(f"  {RED}Zona de bolha: compra não recomendada. Use --amount para forçar.{R}")
        else:
            entry = record_buy(amount, prices["usd"], prices["brl"], signal.zone, signal.multiplier)
            sats = int(entry.btc_amount * 1e8)
            print(f"  {GREEN}{BOLD}✓ Compra registrada!{R}")
            print(f"  {fmt_brl(amount)} → {sats:,} sats  ({entry.btc_amount:.8f} BTC)")
            print(f"  Zona: {ZONE_COLORS.get(signal.zone,'')}{signal.zone}{R}\n")

    if args.portfolio or args.buy:
        print_portfolio(prices["brl"])

    if args.forecast:
        print_forecast()

    if args.simulate:
        simulate_dca(daily_base=args.base)

    if args.chart:
        from chart import save_chart_png, print_ascii_chart
        print_ascii_chart(prices["usd"])
        path = save_chart_png(prices["usd"])
        if path:
            print(f"\n  {GREEN}✓ Gráfico salvo: {path}{R}\n")
        else:
            print(f"\n  {GRAY}(matplotlib não disponível para PNG){R}\n")

    if not any([args.buy, args.portfolio, args.forecast, args.simulate, args.chart]):
        print_forecast()

    print(f"  {GRAY}─────────────────────────────────────────────{R}")
    print(f"  {GRAY}⚠  Isto não é conselho financeiro.{R}")
    print(f"  {GRAY}   Invista apenas o que pode perder.{R}")
    print()


if __name__ == "__main__":
    main()
