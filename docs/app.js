const grid = document.getElementById("signal-grid");
const countEl = document.getElementById("count");
const sourceEl = document.getElementById("source");
const marketEl = document.getElementById("market");
const actionEl = document.getElementById("action");
const timeframeEl = document.getElementById("timeframe");
const refreshBtn = document.getElementById("refresh");
const tvStatusEl = document.getElementById("tv-status");
const apiBaseEl = document.getElementById("api-base");

const TF_ORDER = ["daily", "weekly", "monthly"];
const API_BASE = String(window.APP_CONFIG?.API_BASE_URL || "").replace(/\/$/, "");
apiBaseEl.textContent = API_BASE || "(not configured)";

function apiUrl(path) {
  if (!API_BASE) {
    throw new Error("Set docs/config.js -> APP_CONFIG.API_BASE_URL");
  }
  return `${API_BASE}${path}`;
}

function badgeForState(state) {
  if (state === "buy") return "BUY";
  if (state === "sell") return "SELL";
  if (state === "mixed") return "MIXED";
  return "NEUTRAL";
}

function barsSinceText(value) {
  return value === null ? "none" : `${value} candles ago`;
}

function tfStatus(tf) {
  if (tf.state === "buy") return "latest in window: BUY";
  if (tf.state === "sell") return "latest in window: SELL";
  if (tf.state === "mixed") return "latest in window: MIXED";
  return "no alert in window";
}

function fmt(n) {
  return Number.isFinite(n) ? n.toFixed(4) : "-";
}

function timeframeBlock(name, tf) {
  return `
    <div class="tf-block tf-${name}">
      <div class="tf-head">
        <strong>${name.toUpperCase()}</strong>
        <span class="tf-window">Last ${tf.lookback} candles</span>
      </div>
      <p class="small tf-status">${tfStatus(tf)}</p>
      <p class="small">Buy recent: ${tf.buy_recent} (last: ${barsSinceText(tf.bars_since_buy)})</p>
      <p class="small">Sell recent: ${tf.sell_recent} (last: ${barsSinceText(tf.bars_since_sell)})</p>
      <p class="small">Close: ${fmt(tf.close)} | Stop: ${fmt(tf.trailing_stop)} | ATR: ${fmt(tf.atr)}</p>
    </div>
  `;
}

function timeframeBlocks(signal, selectedTimeframe) {
  const names = selectedTimeframe === "all" ? TF_ORDER : [selectedTimeframe];
  return names
    .filter((name) => Boolean(signal.timeframes[name]))
    .map((name) => timeframeBlock(name, signal.timeframes[name]))
    .join("");
}

function cardState(signal, selectedTimeframe) {
  if (selectedTimeframe === "all") {
    return signal.state;
  }
  return signal.timeframes[selectedTimeframe]?.state ?? "neutral";
}

async function loadTradingViewStatus() {
  try {
    const res = await fetch(apiUrl("/api/tradingview/status"));
    const data = await res.json();
    tvStatusEl.textContent = data.secret_configured
      ? "TradingView webhook security: enabled"
      : "TradingView webhook security: not set";
  } catch (err) {
    tvStatusEl.textContent = `API unreachable: ${err.message}`;
  }
}

async function loadMarkets() {
  const current = marketEl.value;
  const res = await fetch(apiUrl("/api/markets"));
  const data = await res.json();

  marketEl.innerHTML = "";
  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "All markets";
  marketEl.appendChild(allOption);

  for (const market of data.markets) {
    const op = document.createElement("option");
    op.value = market;
    op.textContent = market;
    marketEl.appendChild(op);
  }

  marketEl.value = [...marketEl.options].some((o) => o.value === current) ? current : "";
}

async function loadSignals() {
  const source = sourceEl.value;
  const market = marketEl.value;
  const action = actionEl.value;
  const timeframe = timeframeEl.value;

  const params = new URLSearchParams();
  if (source) params.set("source", source);
  if (market) params.set("market", market);
  if (action) params.set("action", action);
  if (timeframe) params.set("timeframe", timeframe);

  const query = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(apiUrl(`/api/signals${query}`));
  const data = await res.json();

  countEl.textContent = data.count;
  grid.innerHTML = "";

  for (const signal of data.signals) {
    const blocks = timeframeBlocks(signal, timeframe);
    const state = cardState(signal, timeframe);

    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="row">
        <h3>${signal.symbol}</h3>
        <span class="pill ${state}">${badgeForState(state)}</span>
      </div>
      <p class="small">Market: ${signal.market} | Type: ${signal.asset_type}</p>
      <p>Last close: ${fmt(Number(signal.last_close))}</p>
      <div class="tf-grid">${blocks}</div>
    `;
    grid.appendChild(card);
  }

  if (data.count === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No symbols match this source/market/signal/timeframe filter right now.";
    grid.appendChild(empty);
  }
}

refreshBtn.addEventListener("click", loadSignals);
sourceEl.addEventListener("change", loadSignals);
marketEl.addEventListener("change", loadSignals);
actionEl.addEventListener("change", loadSignals);
timeframeEl.addEventListener("change", loadSignals);

loadTradingViewStatus();
loadMarkets().then(loadSignals).catch((err) => {
  grid.innerHTML = `<div class="empty">${err.message}</div>`;
});
