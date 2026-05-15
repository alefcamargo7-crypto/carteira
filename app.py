"""
Web server simples para o Bitcoin Power Law Trade System.
Roda com: python app.py
Abre no navegador: http://localhost:8080
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import math
from datetime import date

from power_law import (
    fair_value, band_prices, future_fair_value,
    days_since_genesis, price_position, model_deviation_pct
)
from strategy import get_signal, ZONES
from portfolio import record_buy, get_summary
from price_feed import get_btc_prices


def build_api_response(path: str, params: dict) -> dict:
    # Fetch or use manual price
    manual_price = float(params.get("price", [0])[0] or 0)

    if manual_price:
        usd_brl = 5.75
        prices = {"usd": manual_price, "brl": manual_price * usd_brl, "usd_brl": usd_brl}
    else:
        prices = get_btc_prices()
        if not prices["usd"]:
            return {"error": "Não foi possível buscar a cotação. Tente informar o preço manualmente."}

    base = float(params.get("base", [10])[0] or 10)
    signal = get_signal(prices["usd"], prices["brl"], daily_base_brl=base)

    # Forecast
    forecast = []
    for label, years in [("6 meses", 0.5), ("1 ano", 1), ("2 anos", 2), ("3 anos", 3), ("5 anos", 5), ("10 anos", 10)]:
        fv_usd = future_fair_value(years)
        forecast.append({"label": label, "usd": fv_usd, "brl": fv_usd * (prices["usd_brl"] or 5.75)})

    # Chart data points
    from datetime import timedelta
    from power_law import power_law_price, BAND_OFFSETS, GENESIS
    chart_points = []
    today = date.today()
    start = date(2015, 1, 1)
    end = today + timedelta(days=365 * 3)
    d = start
    while d <= end:
        days = days_since_genesis(d)
        chart_points.append({
            "date": d.isoformat(),
            "fair_value": round(power_law_price(days, 0), 2),
            "floor": round(power_law_price(days, BAND_OFFSETS["floor"]), 2),
            "support": round(power_law_price(days, BAND_OFFSETS["support"]), 2),
            "overbought": round(power_law_price(days, BAND_OFFSETS["overbought"]), 2),
            "ceiling": round(power_law_price(days, BAND_OFFSETS["ceiling"]), 2),
            "is_future": d > today,
        })
        d += timedelta(days=60)

    return {
        "prices": prices,
        "signal": {
            "zone": signal.zone,
            "multiplier": signal.multiplier,
            "daily_base_brl": signal.daily_base_brl,
            "recommended_buy_brl": signal.recommended_buy_brl,
            "position": round(signal.position, 4),
            "deviation_pct": round(signal.deviation_pct, 2),
            "fair_value_usd": round(signal.fair_value_usd, 2),
            "bands": {k: round(v, 2) for k, v in signal.bands.items()},
            "rationale": signal.rationale,
        },
        "forecast": forecast,
        "chart": chart_points,
        "days_since_genesis": days_since_genesis(),
        "today": today.isoformat(),
    }


def handle_buy(params: dict) -> dict:
    manual_price = float(params.get("price", [0])[0] or 0)
    if manual_price:
        usd_brl = 5.75
        prices = {"usd": manual_price, "brl": manual_price * usd_brl, "usd_brl": usd_brl}
    else:
        prices = get_btc_prices()
        if not prices["usd"]:
            return {"error": "Sem cotação disponível."}

    base = float(params.get("base", [10])[0] or 10)
    amount = float(params.get("amount", [0])[0] or 0)
    signal = get_signal(prices["usd"], prices["brl"], daily_base_brl=base)
    buy_amount = amount if amount > 0 else signal.recommended_buy_brl

    if buy_amount <= 0:
        return {"error": "Zona de bolha — compra não recomendada."}

    entry = record_buy(buy_amount, prices["usd"], prices["brl"], signal.zone, signal.multiplier)
    sats = int(entry.btc_amount * 1e8)
    return {"ok": True, "brl": buy_amount, "sats": sats, "btc": entry.btc_amount, "zone": signal.zone}


def handle_portfolio(params: dict) -> dict:
    manual_price = float(params.get("price", [0])[0] or 0)
    if manual_price:
        brl = manual_price * 5.75
    else:
        p = get_btc_prices()
        brl = p.get("brl") or 0
    return get_summary(brl or None)


HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>₿ Bitcoin · Power Law</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #0d1117; --card: #161b22; --border: #30363d;
    --orange: #f7931a; --green: #22c55e; --red: #ef4444;
    --yellow: #eab308; --blue: #3b82f6; --purple: #a855f7;
    --text: #e6edf3; --muted: #8b949e;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }

  header { background: var(--card); border-bottom: 1px solid var(--border); padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 1.3rem; color: var(--orange); font-weight: 700; }
  header span { color: var(--muted); font-size: 0.85rem; }

  .container { max-width: 1100px; margin: 0 auto; padding: 24px 16px; display: flex; flex-direction: column; gap: 20px; }

  .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
  .card h2 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-bottom: 14px; }

  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  @media(max-width: 650px) { .grid-2, .grid-3 { grid-template-columns: 1fr; } }

  .stat { }
  .stat .label { font-size: 0.78rem; color: var(--muted); margin-bottom: 4px; }
  .stat .value { font-size: 1.5rem; font-weight: 700; }
  .stat .sub { font-size: 0.82rem; color: var(--muted); margin-top: 2px; }

  /* Zone badge */
  .zone-badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 0.9rem; }
  .zone-FLOOR      { background: #14532d44; color: #4ade80; border: 1px solid #16a34a55; }
  .zone-SUPPORT    { background: #14532d33; color: #86efac; border: 1px solid #16a34a33; }
  .zone-FAIR\ VALUE{ background: #78350f33; color: #fde047; border: 1px solid #a1620033; }
  .zone-OVERBOUGHT { background: #7c2d1233; color: #fb923c; border: 1px solid #c2410c33; }
  .zone-CEILING    { background: #7f1d1d44; color: #f87171; border: 1px solid #b91c1c55; }

  /* Progress bar */
  .progress-wrap { background: #1f2937; border-radius: 8px; height: 12px; overflow: hidden; margin: 10px 0 4px; }
  .progress-fill { height: 100%; border-radius: 8px; transition: width .6s ease; }

  /* Band table */
  .band-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
  .band-table td { padding: 7px 10px; border-bottom: 1px solid var(--border); }
  .band-table tr:last-child td { border-bottom: none; }
  .band-table .name { color: var(--muted); }
  .band-table .usd  { font-weight: 600; text-align: right; }
  .band-table .brl  { color: var(--muted); font-size: 0.8rem; text-align: right; }
  .band-table .active-row td { background: #ffffff08; }
  .band-table .active-row .name { color: var(--text); }

  /* Buy form */
  .buy-form { display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end; }
  .form-group { display: flex; flex-direction: column; gap: 4px; }
  .form-group label { font-size: 0.78rem; color: var(--muted); }
  .form-group input { background: #0d1117; border: 1px solid var(--border); border-radius: 8px; color: var(--text); padding: 8px 12px; font-size: 0.95rem; width: 130px; }
  .form-group input:focus { outline: none; border-color: var(--orange); }
  button { padding: 8px 20px; border-radius: 8px; border: none; cursor: pointer; font-weight: 600; font-size: 0.9rem; transition: opacity .15s; }
  button:hover { opacity: 0.85; }
  .btn-primary { background: var(--orange); color: #000; }
  .btn-ghost   { background: #1f2937; color: var(--text); }

  /* Recommendation box */
  .rec-box { border-radius: 10px; padding: 16px 20px; border: 1px solid; }
  .rec-FLOOR      { border-color: #16a34a55; background: #14532d22; }
  .rec-SUPPORT    { border-color: #16a34a33; background: #14532d11; }
  .rec-FAIR\ VALUE{ border-color: #a1620033; background: #78350f11; }
  .rec-OVERBOUGHT { border-color: #c2410c33; background: #7c2d1211; }
  .rec-CEILING    { border-color: #b91c1c55; background: #7f1d1d22; }

  /* Forecast */
  .forecast-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
  .forecast-table td { padding: 8px 10px; border-bottom: 1px solid var(--border); }
  .forecast-table tr:last-child td { border-bottom: none; }
  .forecast-table .horizon { color: var(--muted); }
  .forecast-table .usd { font-weight: 600; text-align: right; }
  .forecast-table .brl { color: var(--muted); font-size: 0.8rem; text-align: right; }

  /* Portfolio */
  .pnl-pos { color: var(--green); }
  .pnl-neg { color: var(--red); }
  .history-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
  .history-table th { color: var(--muted); text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); font-weight: 400; }
  .history-table td { padding: 7px 10px; border-bottom: 1px solid #21262d; }
  .history-table tr:last-child td { border-bottom: none; }

  /* Chart */
  .chart-wrap { position: relative; height: 340px; }

  /* Toast */
  #toast { position: fixed; bottom: 24px; right: 24px; background: #1f2937; border: 1px solid var(--border); border-radius: 10px; padding: 12px 20px; font-size: 0.9rem; opacity: 0; transition: opacity .3s; pointer-events: none; z-index: 999; }
  #toast.show { opacity: 1; }

  /* Loading */
  .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid var(--border); border-top-color: var(--orange); border-radius: 50%; animation: spin .7s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  .tag { font-size: 0.72rem; background: #1f2937; border-radius: 4px; padding: 2px 6px; color: var(--muted); }
  .disclaimer { font-size: 0.78rem; color: var(--muted); text-align: center; padding: 12px 0; }
</style>
</head>
<body>

<header>
  <span style="font-size:1.6rem">₿</span>
  <h1>Bitcoin · Power Law</h1>
  <span id="subtitle">carregando...</span>
</header>

<div class="container">

  <!-- Settings bar -->
  <div class="card" style="padding:14px 20px;">
    <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;">
      <div class="form-group">
        <label>Base diária (R$)</label>
        <input id="inputBase" type="number" value="10" min="1" step="1" style="width:100px">
      </div>
      <div class="form-group">
        <label>Preço manual (USD) — opcional</label>
        <input id="inputPrice" type="number" placeholder="ex: 104000" style="width:150px">
      </div>
      <div class="form-group" style="justify-content:flex-end">
        <label>&nbsp;</label>
        <button class="btn-primary" onclick="loadData()">🔄 Atualizar</button>
      </div>
      <span id="loadingSpinner" style="display:none"><span class="spinner"></span></span>
    </div>
  </div>

  <!-- Price + Signal -->
  <div class="grid-2">
    <div class="card">
      <h2>Preço Atual</h2>
      <div class="grid-3" style="gap:14px;">
        <div class="stat">
          <div class="label">BTC / USD</div>
          <div class="value" id="priceUSD" style="color:var(--orange)">—</div>
        </div>
        <div class="stat">
          <div class="label">BTC / BRL</div>
          <div class="value" id="priceBRL">—</div>
        </div>
        <div class="stat">
          <div class="label">Valor Justo (modelo)</div>
          <div class="value" id="fairValue" style="color:#38bdf8;font-size:1.2rem">—</div>
          <div class="sub" id="deviation">—</div>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>Zona Atual</h2>
      <div id="zoneBadge" style="margin-bottom:10px">—</div>
      <div id="rationale" style="font-size:0.85rem;color:var(--muted);margin-bottom:10px">—</div>
      <div class="progress-wrap">
        <div class="progress-fill" id="progressBar" style="width:0%"></div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:var(--muted)">
        <span>Piso</span><span>Valor Justo</span><span>Teto</span>
      </div>
    </div>
  </div>

  <!-- Chart -->
  <div class="card">
    <h2>Gráfico · Power Law <span class="tag">escala log</span></h2>
    <div class="chart-wrap">
      <canvas id="chartCanvas"></canvas>
    </div>
  </div>

  <!-- Recommendation + Bands -->
  <div class="grid-2">
    <div class="card">
      <h2>Recomendação de Hoje</h2>
      <div id="recBox" class="rec-box rec-FAIR\ VALUE" style="margin-bottom:16px">
        <div style="font-size:0.82rem;color:var(--muted);margin-bottom:4px">Base diária × multiplicador</div>
        <div style="font-size:2rem;font-weight:700;color:var(--orange)" id="recAmount">R$ —</div>
        <div style="font-size:0.85rem;margin-top:4px" id="recSats">≈ — sats</div>
        <div style="font-size:0.8rem;color:var(--muted);margin-top:6px" id="recMult">×— multiplicador</div>
      </div>

      <h2 style="margin-bottom:10px">Registrar Compra</h2>
      <div class="buy-form">
        <div class="form-group">
          <label>Valor (R$) — deixe 0 para usar o recomendado</label>
          <input id="buyAmount" type="number" value="0" min="0" step="0.01" style="width:150px">
        </div>
        <button class="btn-primary" onclick="doBuy()">💰 Comprar</button>
      </div>
    </div>

    <div class="card">
      <h2>Bandas de Preço (USD)</h2>
      <table class="band-table" id="bandTable">
        <tr><td class="name">Carregando...</td></tr>
      </table>
    </div>
  </div>

  <!-- Portfolio -->
  <div class="card">
    <h2>Minha Carteira</h2>
    <div id="portfolioSection">
      <div style="color:var(--muted);font-size:0.88rem">Nenhuma compra registrada ainda.</div>
    </div>
  </div>

  <!-- Forecast -->
  <div class="card">
    <h2>Projeção · Valor Justo Futuro <span class="tag">Power Law</span></h2>
    <table class="forecast-table" id="forecastTable">
      <tr><td style="color:var(--muted)">Carregando...</td></tr>
    </table>
    <div style="font-size:0.78rem;color:var(--muted);margin-top:10px">
      Projeção do "valor justo" do modelo — não é garantia de preço.
    </div>
  </div>

  <div class="disclaimer">⚠ Isto não é conselho financeiro. Invista apenas o que pode perder.</div>
</div>

<div id="toast"></div>

<script>
let chartInstance = null;
let currentSignal = null;
let currentPrices = null;

const fmtUSD = v => '$' + Math.round(v).toLocaleString('en-US');
const fmtBRL = v => 'R$ ' + v.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2});

function toast(msg, color='#22c55e') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.color = color;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 3500);
}

function progressColor(pos) {
  if (pos < 0.4) return '#22c55e';
  if (pos < 0.6) return '#eab308';
  if (pos < 0.8) return '#f97316';
  return '#ef4444';
}

function zoneEmoji(zone) {
  const map = {'FLOOR':'🟢','SUPPORT':'💚','FAIR VALUE':'🟡','OVERBOUGHT':'🟠','CEILING':'🔴'};
  return map[zone] || '⚪';
}

function buildChart(points, currentUSD) {
  const past = points.filter(p => !p.is_future);
  const future = points.filter(p => p.is_future);
  const all = points;

  const labels = all.map(p => p.date);
  const canvas = document.getElementById('chartCanvas');
  if (chartInstance) chartInstance.destroy();

  chartInstance = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {label:'Teto', data: all.map(p=>p.ceiling), borderColor:'#ef444488', borderWidth:1, borderDash:[4,4], pointRadius:0, fill:false},
        {label:'Sobrecomprado', data: all.map(p=>p.overbought), borderColor:'#f9731688', borderWidth:1, borderDash:[2,4], pointRadius:0, fill:false},
        {label:'Valor Justo', data: all.map(p=>p.fair_value), borderColor:'#f7931a', borderWidth:2, pointRadius:0, fill:false},
        {label:'Suporte', data: all.map(p=>p.support), borderColor:'#22c55e88', borderWidth:1, borderDash:[2,4], pointRadius:0, fill:false},
        {label:'Piso', data: all.map(p=>p.floor), borderColor:'#3b82f688', borderWidth:1, borderDash:[4,4], pointRadius:0, fill:false},
        {
          label:'Preço Atual',
          data: labels.map(l => l === points.find(p=>!p.is_future && Math.abs(new Date(l)-new Date())<1000*60*60*24*35)?.date ? currentUSD : null),
          borderColor:'#ffffff',
          pointBackgroundColor:'#ffffff',
          pointRadius: labels.map(l => {
            const today = new Date();
            const d = new Date(l);
            return Math.abs(d - today) < 1000*60*60*24*35 ? 6 : 0;
          }),
          pointHoverRadius:8,
          showLine:false,
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode:'index', intersect:false },
      scales: {
        x: {
          ticks: { color:'#6b7280', maxTicksLimit:10, callback(v,i){ return labels[i]?.slice(0,4); } },
          grid: { color:'#1f2937' }
        },
        y: {
          type:'logarithmic',
          ticks: { color:'#6b7280', callback(v){ return v>=1000?'$'+v/1000+'k':'$'+v; } },
          grid: { color:'#1f2937' }
        }
      },
      plugins: {
        legend: { labels:{ color:'#9ca3af', boxWidth:12, font:{size:11} } },
        tooltip: {
          backgroundColor:'#1f2937', borderColor:'#374151', borderWidth:1,
          callbacks: {
            label(ctx) { return ctx.dataset.label + ': ' + (ctx.parsed.y ? fmtUSD(ctx.parsed.y) : ''); }
          }
        }
      }
    }
  });
}

function renderBands(signal, prices) {
  const rate = prices.usd_brl || 5.75;
  const bandInfo = [
    {key:'ceiling',    label:'🔴 Teto'},
    {key:'overbought', label:'🟠 Sobrecomprado'},
    {key:'fair_value', label:'🟡 Valor Justo'},
    {key:'support',    label:'💚 Suporte'},
    {key:'floor',      label:'🟢 Piso'},
  ];
  const zoneKeyMap = {
    'CEILING':'ceiling', 'OVERBOUGHT':'overbought',
    'FAIR VALUE':'fair_value', 'SUPPORT':'support', 'FLOOR':'floor'
  };
  const activeKey = zoneKeyMap[signal.zone];

  const rows = bandInfo.map(b => {
    const usd = signal.bands[b.key];
    const brl = usd * rate;
    const isActive = b.key === activeKey;
    return `<tr class="${isActive?'active-row':''}">
      <td class="name">${b.label}</td>
      <td class="usd">${fmtUSD(usd)}</td>
      <td class="brl">${fmtBRL(brl)}</td>
    </tr>`;
  }).join('');
  document.getElementById('bandTable').innerHTML = rows;
}

function renderForecast(forecast, rate) {
  rate = rate || 5.75;
  const rows = forecast.map(f => `
    <tr>
      <td class="horizon">${f.label}</td>
      <td class="usd">${fmtUSD(f.usd)}</td>
      <td class="brl">${fmtBRL(f.brl)}</td>
    </tr>`).join('');
  document.getElementById('forecastTable').innerHTML = rows;
}

function renderPortfolio(portfolio) {
  const sec = document.getElementById('portfolioSection');
  if (!portfolio || portfolio.total_entries === 0) {
    sec.innerHTML = '<div style="color:var(--muted);font-size:0.88rem">Nenhuma compra registrada ainda. Use o botão 💰 para registrar.</div>';
    return;
  }

  const pnl = portfolio.pnl_brl;
  const pnlClass = pnl >= 0 ? 'pnl-pos' : 'pnl-neg';
  const pnlSign = pnl >= 0 ? '+' : '';

  let html = `<div class="grid-3" style="margin-bottom:18px">
    <div class="stat"><div class="label">Total Investido</div><div class="value" style="font-size:1.2rem">${fmtBRL(portfolio.total_brl_invested)}</div></div>
    <div class="stat"><div class="label">Total BTC</div><div class="value" style="font-size:1.2rem">${portfolio.total_btc.toFixed(8)}</div></div>
    <div class="stat"><div class="label">Preço Médio</div><div class="value" style="font-size:1.2rem">${fmtBRL(portfolio.avg_cost_brl)}</div></div>
  `;

  if (portfolio.current_value_brl != null) {
    html += `
    <div class="stat"><div class="label">Valor Atual</div><div class="value" style="font-size:1.2rem;color:var(--orange)">${fmtBRL(portfolio.current_value_brl)}</div></div>
    <div class="stat"><div class="label">P&L</div><div class="value ${pnlClass}" style="font-size:1.2rem">${pnlSign}${fmtBRL(pnl)}</div><div class="sub ${pnlClass}">${pnlSign}${portfolio.pnl_pct?.toFixed(1)}%</div></div>
    `;
  }
  html += '</div>';

  if (portfolio.entries?.length) {
    html += `<table class="history-table">
      <tr><th>Data</th><th>R$ Investido</th><th>BTC/BRL</th><th>Zona</th><th>Sats</th></tr>`;
    const show = portfolio.entries.slice(-20).reverse();
    for (const e of show) {
      const sats = Math.round(e.btc_amount * 1e8);
      html += `<tr>
        <td style="color:var(--muted)">${e.date}</td>
        <td>${fmtBRL(e.brl_invested)}</td>
        <td style="color:var(--muted)">${fmtBRL(e.btc_brl_price)}</td>
        <td>${zoneEmoji(e.zone)} ${e.zone}</td>
        <td style="color:var(--muted)">${sats.toLocaleString()}</td>
      </tr>`;
    }
    html += '</table>';
  }

  sec.innerHTML = html;
}

async function loadData() {
  const base = document.getElementById('inputBase').value || 10;
  const price = document.getElementById('inputPrice').value || '';
  const spinner = document.getElementById('loadingSpinner');
  spinner.style.display = 'inline-block';

  try {
    const qs = new URLSearchParams({base, ...(price ? {price} : {})});
    const res = await fetch('/api/data?' + qs);
    const data = await res.json();
    if (data.error) { toast('Erro: ' + data.error, '#ef4444'); return; }

    currentSignal = data.signal;
    currentPrices = data.prices;

    // Subtitle
    document.getElementById('subtitle').textContent = `${data.today} · Dia ${data.days_since_genesis.toLocaleString()} desde o bloco gênesis`;

    // Prices
    document.getElementById('priceUSD').textContent = fmtUSD(data.prices.usd);
    document.getElementById('priceBRL').textContent = fmtBRL(data.prices.brl);
    document.getElementById('fairValue').textContent = fmtUSD(data.signal.fair_value_usd);
    const dev = data.signal.deviation_pct;
    const devEl = document.getElementById('deviation');
    devEl.textContent = (dev >= 0 ? '+' : '') + dev.toFixed(1) + '% do modelo';
    devEl.style.color = dev > 0 ? '#ef4444' : '#22c55e';

    // Zone
    const z = data.signal.zone;
    document.getElementById('zoneBadge').innerHTML = `<span class="zone-badge zone-${z}">${zoneEmoji(z)} ${z}</span>`;
    document.getElementById('rationale').textContent = data.signal.rationale;
    const pos = data.signal.position;
    const bar = document.getElementById('progressBar');
    bar.style.width = (pos * 100) + '%';
    bar.style.background = progressColor(pos);

    // Recommendation
    const rec = data.signal.recommended_buy_brl;
    document.getElementById('recAmount').textContent = fmtBRL(rec);
    if (rec > 0 && data.prices.brl) {
      const sats = Math.round((rec / data.prices.brl) * 1e8);
      document.getElementById('recSats').textContent = '≈ ' + sats.toLocaleString() + ' satoshis';
    } else {
      document.getElementById('recSats').textContent = 'Zona de bolha — aguardar';
    }
    document.getElementById('recMult').textContent = '×' + data.signal.multiplier + ' multiplicador (base R$' + base + '/dia)';
    document.getElementById('recBox').className = 'rec-box rec-' + z;

    // Bands
    renderBands(data.signal, data.prices);

    // Forecast
    renderForecast(data.forecast, data.prices.usd_brl);

    // Chart
    buildChart(data.chart, data.prices.usd);

    // Portfolio
    await loadPortfolio();

  } catch(e) {
    toast('Erro de conexão com o servidor.', '#ef4444');
  } finally {
    spinner.style.display = 'none';
  }
}

async function loadPortfolio() {
  const price = document.getElementById('inputPrice').value || '';
  const qs = new URLSearchParams({...(price ? {price} : {})});
  const res = await fetch('/api/portfolio?' + qs);
  const data = await res.json();
  renderPortfolio(data);
}

async function doBuy() {
  if (!currentSignal) { toast('Carregue os dados primeiro.', '#eab308'); return; }
  const base = document.getElementById('inputBase').value || 10;
  const price = document.getElementById('inputPrice').value || '';
  const amount = document.getElementById('buyAmount').value || 0;
  const qs = new URLSearchParams({base, amount, ...(price ? {price} : {})});
  const res = await fetch('/api/buy?' + qs, {method:'POST'});
  const data = await res.json();
  if (data.error) { toast('Erro: ' + data.error, '#ef4444'); return; }
  toast(`✓ ${fmtBRL(data.brl)} → ${data.sats.toLocaleString()} sats (${data.zone})`);
  await loadPortfolio();
}

loadData();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence access logs

    def send_json(self, data: dict, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif parsed.path == "/api/data":
            self.send_json(build_api_response(parsed.path, params))

        elif parsed.path == "/api/portfolio":
            self.send_json(handle_portfolio(params))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/api/buy":
            self.send_json(handle_buy(params))
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    port = 8080
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"\n  ₿  Bitcoin Power Law · Servidor rodando")
    print(f"  Abra no navegador: http://localhost:{port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor encerrado.")
