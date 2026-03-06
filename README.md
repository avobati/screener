# Stock/ETF/Crypto/Metals UT Bot Scanner

This repository contains:

- Deployable backend API (Python): `app/server.py`
- Deployable frontend website (GitHub Pages): `docs/`

Website:

- https://avobati.github.io/screener/

## Backend

### Features

- `GET /api/health`
- `GET /api/signals`
- `GET /api/markets`
- `GET /api/strategy`
- `GET /api/tradingview/status`
- `POST /api/tradingview/webhook`
- CORS support for GitHub Pages
- TradingView signal persistence via `TV_DB_PATH`

### Required env vars

- `TV_WEBHOOK_SECRET`
- `CORS_ALLOW_ORIGIN=https://avobati.github.io`
- `TV_DB_PATH=/var/data/tradingview_signals.db` (Render persistent disk)
- `HOST=0.0.0.0`
- `PORT=8080` (platform usually sets)

### Local run

```powershell
cd C:\Users\avoba\stock-super-app
$env:TV_WEBHOOK_SECRET="change-this"
$env:CORS_ALLOW_ORIGIN="https://avobati.github.io"
$env:TV_DB_PATH="./data/tradingview_signals.db"
$env:HOST="0.0.0.0"
$env:PORT="8080"
python -m app.server
```

Health:

- `http://localhost:8080/api/health`

## Render deploy

`render.yaml` is included with:

- start command
- env vars
- persistent disk mounted at `/var/data`

After deploy, confirm:

- `https://<backend-domain>/api/health`

## Connect frontend

Edit `docs/config.js`:

```js
window.APP_CONFIG = {
  API_BASE_URL: "https://<backend-domain>"
};
```

No trailing slash.

## GitHub Pages

1. Repo `Settings` -> `Pages`
2. Source: `Deploy from a branch`
3. Branch: `main`
4. Folder: `/docs`

Site URL:

- `https://avobati.github.io/screener/`

## TradingView webhook

URL:

```text
https://<backend-domain>/api/tradingview/webhook?secret=<TV_WEBHOOK_SECRET>
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

Timeframes accepted: `D`, `W`, `M`.

## Note

This is a screening tool, not financial advice.
