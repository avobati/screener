# Stock/ETF/Crypto/Metals UT Bot Scanner

This repository contains:

- Deployable backend API (Python): `app/server.py`
- Deployable frontend website (GitHub Pages): `docs/`

Your website target:

- https://avobati.github.io/screener/

## Backend: complete deploy-ready service

### Features

- `GET /api/health` (health check)
- `GET /api/signals`
- `GET /api/markets`
- `GET /api/strategy`
- `GET /api/tradingview/status`
- `POST /api/tradingview/webhook`
- CORS support for GitHub Pages origin
- Production host/port via env (`HOST`, `PORT`)

### Required environment variables

Use `.env.example` as reference:

- `TV_WEBHOOK_SECRET`
- `CORS_ALLOW_ORIGIN=https://avobati.github.io`
- `HOST=0.0.0.0`
- `PORT=8080` (set by platform automatically on most PaaS)

### Local run

```powershell
cd C:\Users\avoba\stock-super-app
$env:TV_WEBHOOK_SECRET="change-this"
$env:CORS_ALLOW_ORIGIN="https://avobati.github.io"
$env:HOST="0.0.0.0"
$env:PORT="8080"
python -m app.server
```

Health check:

- `http://localhost:8080/api/health`

## Deploy backend (Render example)

`render.yaml` is included. Create service from repo and set secret env vars.

After deploy, confirm:

- `https://<your-backend-domain>/api/health`

## Connect website to backend

Edit:

- `docs/config.js`

Set:

```js
window.APP_CONFIG = {
  API_BASE_URL: "https://<your-backend-domain>"
};
```

Important: no trailing slash.

## Deploy website (GitHub Pages)

1. GitHub repo -> `Settings` -> `Pages`
2. Source: `Deploy from a branch`
3. Branch: `main`
4. Folder: `/docs`
5. Save

Then open:

- `https://avobati.github.io/screener/`

## TradingView webhook setup

Webhook URL:

```text
https://<your-backend-domain>/api/tradingview/webhook?secret=<TV_WEBHOOK_SECRET>
```

Webhook payload:

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

Timeframe accepted: `D`, `W`, `M` (or daily/weekly/monthly).

## Quick diagnostics

If website loads but no data:

1. Check browser network call to `/api/health`
2. Confirm backend `CORS_ALLOW_ORIGIN` exactly matches `https://avobati.github.io`
3. Confirm `docs/config.js` points to deployed backend URL
4. Confirm backend is reachable publicly over HTTPS

## Note

This is a screening tool, not financial advice.
