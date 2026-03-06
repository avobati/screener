const grid = document.getElementById("signal-grid");
const countEl = document.getElementById("count");
const sourceEl = document.getElementById("source");
const marketEl = document.getElementById("market");
const actionEl = document.getElementById("action");
const timeframeEl = document.getElementById("timeframe");
const refreshBtn = document.getElementById("refresh");
const tvStatusEl = document.getElementById("tv-status");

const TF_ORDER = ["daily", "weekly", "monthly"];
let scanRetryTimer = null;

async function fetchJson(path) {
  const res = await fetch(path);
  let data = null;
  try {
    data = await res.json();
  } catch {
    // Ignore JSON parse errors and use HTTP status fallback.
  }
  if (!res.ok) {
    throw new Error(data?.error || `HTTP ${res.status}`);
  }
  return data;
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

function showEmpty(message) {
  grid.innerHTML = `<div class="empty">${message}</div>`;
}

function scheduleRetry(ms = 15000) {
  if (scanRetryTimer) {
    clearTimeout(scanRetryTimer);
  }
  scanRetryTimer = setTimeout(() => {
    loadSignals().catch(() => {
      // Load errors are already surfaced in loadSignals.
    });
  }, ms);
}

async function loadTradingViewStatus() {
  try {
    const data = await fetchJson("/api/tradingview/status");
    tvStatusEl.textContent = data.secret_configured
      ? "TradingView webhook security: enabled"
      : "TradingView webhook security: not set (configure TV_WEBHOOK_SECRET)";
  } catch (err) {
    tvStatusEl.textContent = `TradingView webhook status unavailable: ${err.message}`;
  }
}

async function loadMarkets() {
  const current = marketEl.value;
  try {
    const data = await fetchJson("/api/markets");
    marketEl.innerHTML = "";
    const allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = "All markets";
    marketEl.appendChild(allOption);

    for (const market of data.markets || []) {
      const op = document.createElement("option");
      op.value = market;
      op.textContent = market;
      marketEl.appendChild(op);
    }
    marketEl.value = [...marketEl.options].some((o) => o.value === current) ? current : "";
  } catch (err) {
    tvStatusEl.textContent = `Market list unavailable: ${err.message}`;
  }
}

async function isScanRunning() {
  try {
    const status = await fetchJson("/api/scans/status");
    return status.status === "running";
  } catch {
    return false;
  }
}

async function loadSignals() {
  const source = sourceEl.value || "backend";
  const market = marketEl.value;
  const action = actionEl.value || "all";
  const timeframe = timeframeEl.value || "all";

  const params = new URLSearchParams();
  params.set("source", source);
  if (market) params.set("market", market);
  params.set("action", action);
  params.set("timeframe", timeframe);

  try {
    const data = await fetchJson(`/api/signals?${params.toString()}`);
    countEl.textContent = String(data.count || 0);
    grid.innerHTML = "";

    for (const signal of data.signals || []) {
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

    if ((data.count || 0) === 0) {
      if (await isScanRunning()) {
        showEmpty("Scan is running. Results will appear automatically in ~15 seconds.");
        scheduleRetry(15000);
        return;
      }
      showEmpty("No symbols match this source/market/signal/timeframe filter right now.");
    }
  } catch (err) {
    countEl.textContent = "0";
    showEmpty(`Failed to load symbols: ${err.message}`);
  }
}

refreshBtn.addEventListener("click", loadSignals);
sourceEl.addEventListener("change", loadSignals);
marketEl.addEventListener("change", loadSignals);
actionEl.addEventListener("change", loadSignals);
timeframeEl.addEventListener("change", loadSignals);

async function init() {
  sourceEl.value = "backend";
  if (!actionEl.value) actionEl.value = "all";
  await loadTradingViewStatus();
  await loadMarkets();
  await loadSignals();
}

init();
