# Stock/ETF/Crypto/Metals UT Bot Scanner

This app scans symbols and reports UT Bot buy/sell signals per candle.

## Implemented from your instructions

- Indicator: UT Bot Alerts by QuantNomad
- Settings: Key Value `2`, ATR Period `6`
- Timeframes: `daily`, `weekly`, `monthly`
- Recency windows:
  - Daily: alert within last `180` candles
  - Weekly: alert within last `24` candles
  - Monthly: alert within last `6` candles
- Buy condition: buy signal within timeframe lookback candles
- Sell condition: sell signal within timeframe lookback candles
- Filters: source + market + signal + timeframe

## Run

```powershell
cd C:\Users\avoba\stock-super-app
$env:TV_WEBHOOK_SECRET="your-secret-token"
python -m app.server
```

Open: `http://127.0.0.1:8080`

## API

- `GET /api/signals?source=combined|local|tradingview`
- `GET /api/signals?source=tradingview&action=buy&timeframe=daily`
- `GET /api/signals?source=combined&market=crypto&action=sell&timeframe=weekly`
- `GET /api/markets`
- `GET /api/strategy`
- `GET /api/tradingview/status`
- `POST /api/tradingview/webhook`

## TradingView webhook payload

Use this JSON in your TradingView alert message:

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

For timeframe, send `D`, `W`, or `M`. For action, send `buy` or `sell`.

Webhook URL:

```text
http://<your-host>:8080/api/tradingview/webhook?secret=<your-secret-token>
```

or send header `X-TV-Secret: <your-secret-token>`.

## Daily refresh/update model

TradingView updates this app whenever an alert fires. To get daily refresh behavior:

- Create Daily alerts (Once Per Bar Close) for your UT Bot buy and sell conditions.
- Do the same for Weekly and Monthly alerts.
- Use webhook payload above so each signal is stored immediately.

## Data format

CSV columns in `data/*.csv`:

`symbol,asset_type,market,timestamp,open,high,low,close,volume`

`market` examples: `us-stocks`, `us-etfs`, `crypto`, `metals`.

## Note

This is a scanner, not financial advice. Validate with your TradingView chart outputs before live use.
