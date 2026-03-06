# Stock/ETF/Crypto/Metals UT Bot Scanner

This repo includes:

- Backend API + scheduled scanner (`app/server.py`)
- GitHub Pages frontend (`docs/`)

Website:

- https://avobati.github.io/screener/

## Scalable backend scanning

- Universe config: `config/universe.json` (currently 200 symbols)
- Grouped symbols for staggered runs: `group` field on each symbol
- Background modes:
  - `full`: scan whole universe each run
  - `staggered`: scan one group per run, rotate groups
- Persistent snapshots in `SCAN_DB_PATH`

## Core endpoints

- `GET /api/health`
- `GET /api/signals?source=backend|combined|tradingview|local`
- `GET /api/markets`
- `GET /api/scans/status`
- `GET /api/scans/groups`
- `POST /api/scans/run` (full)
- `POST /api/scans/run?mode=staggered` (next group)
- `POST /api/scans/run?group=crypto-major` (specific group)
- `GET /api/universe`
- `POST /api/universe`
- `POST /api/tradingview/webhook`

## Env vars

- `TV_WEBHOOK_SECRET`
- `CORS_ALLOW_ORIGIN=https://avobati.github.io`
- `TV_DB_PATH=/var/data/tradingview_signals.db`
- `SCAN_DB_PATH=/var/data/scanner_results.db`
- `ENABLE_BACKGROUND_SCANNER=true`
- `SCAN_MODE=staggered`
- `SCAN_STAGGER_GROUPS=us-stocks-a,us-stocks-b,us-stocks-c,us-stocks-d,us-etfs,crypto-major,crypto-alt,metals`
- `SCAN_INTERVAL_MINUTES=60`
- `SCAN_REQUEST_DELAY_MS=1300`
- `RUN_SCAN_ON_START=true`
- `HOST=0.0.0.0`
- `PORT=8080`

## Render

Use `render.yaml` (already configured with persistent disk + staggered mode).

## Frontend API URL

`docs/config.js`:

```js
window.APP_CONFIG = {
  API_BASE_URL: "https://avo-screener.onrender.com"
};
```

## TradingView webhook

```text
https://avo-screener.onrender.com/api/tradingview/webhook?secret=<TV_WEBHOOK_SECRET>
```

## Note

This is a screening tool, not financial advice.
