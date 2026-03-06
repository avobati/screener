# Stock/ETF/Crypto/Metals UT Bot Scanner

This repository contains:

- Deployable backend API (Python): `app/server.py`
- Deployable frontend website (GitHub Pages): `docs/`

Website:

- https://avobati.github.io/screener/

## Backend market-wide scanner

The backend now supports full-universe scanning across markets without per-ticker TradingView alerts.

- Universe config: `config/universe.json`
- Market data source: Yahoo Finance chart API
- Scheduled scanner: background runs (default every 360 minutes)
- Result persistence: SQLite (`SCAN_DB_PATH`)

## API

- `GET /api/health`
- `GET /api/signals?source=backend|combined|tradingview|local`
- `GET /api/markets`
- `GET /api/strategy`
- `GET /api/tradingview/status`
- `GET /api/scans/status`
- `GET /api/universe`
- `POST /api/scans/run` (manual scan trigger)
- `POST /api/universe` (replace universe list)
- `POST /api/tradingview/webhook`

## Environment variables

- `TV_WEBHOOK_SECRET`
- `CORS_ALLOW_ORIGIN=https://avobati.github.io`
- `TV_DB_PATH=/var/data/tradingview_signals.db`
- `SCAN_DB_PATH=/var/data/scanner_results.db`
- `ENABLE_BACKGROUND_SCANNER=true`
- `SCAN_INTERVAL_MINUTES=360`
- `RUN_SCAN_ON_START=true`
- `HOST=0.0.0.0`
- `PORT=8080`

## Render deployment

Use `render.yaml` and set secret envs in dashboard. Keep persistent disk at `/var/data`.

## Universe format (`config/universe.json`)

```json
[
  {
    "symbol": "BTCUSDT",
    "provider_symbol": "BTC-USD",
    "market": "crypto",
    "asset_type": "crypto"
  }
]
```

## Frontend connection

`docs/config.js`:

```js
window.APP_CONFIG = {
  API_BASE_URL: "https://avo-screener.onrender.com"
};
```

## TradingView webhook

URL:

```text
https://avo-screener.onrender.com/api/tradingview/webhook?secret=<TV_WEBHOOK_SECRET>
```

Payload:

```json
{
  "symbol": "{{ticker}}",
  "timeframe": "D",
  "action": "buy",
  "signal_time": "{{time}}",
  "close": "{{close}}",
  "market": "crypto",
  "asset_type": "crypto"
}
```

## Note

This is a screening tool, not financial advice.
