# Stock/ETF/Crypto/Metals UT Bot Scanner

This project now has two deployable parts:

- API backend (Python): serves `/api/*` + accepts TradingView webhooks
- Website frontend (GitHub Pages): static UI in `docs/`

## Strategy

- Indicator: UT Bot Alerts by QuantNomad
- Settings: Key Value `2`, ATR Period `6`
- Timeframes: `daily`, `weekly`, `monthly`
- Recency windows:
  - Daily: last `180` candles
  - Weekly: last `24` candles
  - Monthly: last `6` candles

## 1) Deploy API (required)

Run locally or on a server/cloud VM:

```powershell
cd C:\Users\avoba\stock-super-app
$env:TV_WEBHOOK_SECRET="your-secret-token"
$env:CORS_ALLOW_ORIGIN="https://avobati.github.io"
python -m app.server
```

Notes:

- `TV_WEBHOOK_SECRET` secures `/api/tradingview/webhook`
- `CORS_ALLOW_ORIGIN` must be your GitHub Pages origin (or `*` for testing)

## 2) Deploy website to GitHub Pages

Frontend files are in `docs/`:

- `docs/index.html`
- `docs/app.js`
- `docs/styles.css`
- `docs/config.js`

Set your API URL in `docs/config.js`:

```js
window.APP_CONFIG = {
  API_BASE_URL: "https://your-api-domain.example.com"
};
```

Then in GitHub:

1. Open repo `Settings` -> `Pages`
2. Source: `Deploy from a branch`
3. Branch: `main`, Folder: `/docs`
4. Save

Your site will be available at:

`https://avobati.github.io/screener/`

## API endpoints

- `GET /api/signals?source=combined|local|tradingview`
- `GET /api/markets`
- `GET /api/strategy`
- `GET /api/tradingview/status`
- `POST /api/tradingview/webhook`

## TradingView webhook payload

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

Webhook URL:

```text
https://your-api-domain.example.com/api/tradingview/webhook?secret=your-secret-token
```

## Local static preview (optional)

You can open `docs/index.html` directly, but API calls require a reachable `API_BASE_URL`.

## Note

This is a screening tool, not financial advice.
