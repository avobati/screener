from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

TIMEFRAME_ALIASES = {
    "d": "daily",
    "1d": "daily",
    "daily": "daily",
    "w": "weekly",
    "1w": "weekly",
    "weekly": "weekly",
    "m": "monthly",
    "1m": "monthly",
    "monthly": "monthly",
}


@dataclass
class NormalizedSignal:
    symbol: str
    market: str
    asset_type: str
    timeframe: str
    action: str
    signal_time: datetime
    close: float
    payload_json: str


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tradingview_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                market TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                action TEXT NOT NULL,
                signal_time TEXT NOT NULL,
                close REAL NOT NULL DEFAULT 0,
                received_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tv_symbol_tf_action_time
            ON tradingview_signals(symbol, timeframe, action, signal_time)
            """
        )


def _parse_signal_time(value: Any) -> datetime:
    if value is None or value == "":
        return datetime.now(timezone.utc)

    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1_000_000_000_000:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)

    text = str(value).strip()

    if text.isdigit():
        return _parse_signal_time(int(text))

    text = text.replace("Z", "+00:00")
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _infer_market_asset(symbol: str) -> tuple[str, str]:
    up = symbol.upper()
    if "USDT" in up or "USDTPERP" in up or "BINANCE:" in up:
        return "crypto", "crypto"
    if up.startswith("XAU") or up.startswith("XAG") or "GOLD" in up or "SILVER" in up:
        return "metals", "metal"
    if any(up.startswith(prefix) for prefix in ["SPY", "QQQ", "IWM", "VTI"]):
        return "us-etfs", "etf"
    return "us-stocks", "stock"


def normalize_payload(payload: Dict[str, Any]) -> NormalizedSignal:
    raw_symbol = str(payload.get("symbol") or payload.get("ticker") or payload.get("tv_symbol") or "").strip()
    if not raw_symbol:
        raise ValueError("Missing symbol/ticker")

    symbol = raw_symbol.upper()

    raw_tf = str(payload.get("timeframe") or payload.get("tf") or "").strip().lower()
    timeframe = TIMEFRAME_ALIASES.get(raw_tf)
    if timeframe is None:
        raise ValueError("Invalid timeframe. Use D/W/M or daily/weekly/monthly")

    raw_action = str(payload.get("action") or payload.get("signal") or "").strip().lower()
    if raw_action not in {"buy", "sell"}:
        raise ValueError("Invalid action. Use buy or sell")

    market = str(payload.get("market") or "").strip().lower()
    asset_type = str(payload.get("asset_type") or payload.get("asset") or "").strip().lower()

    inferred_market, inferred_asset = _infer_market_asset(symbol)
    if not market:
        market = inferred_market
    if not asset_type:
        asset_type = inferred_asset

    signal_time = _parse_signal_time(payload.get("signal_time") or payload.get("time") or payload.get("bar_time"))

    try:
        close = float(payload.get("close") or payload.get("price") or 0)
    except (TypeError, ValueError):
        close = 0.0

    return NormalizedSignal(
        symbol=symbol,
        market=market,
        asset_type=asset_type,
        timeframe=timeframe,
        action=raw_action,
        signal_time=signal_time,
        close=close,
        payload_json=json.dumps(payload),
    )


def store_signal(db_path: Path, signal: NormalizedSignal) -> None:
    received_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO tradingview_signals
            (symbol, market, asset_type, timeframe, action, signal_time, close, received_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal.symbol,
                signal.market,
                signal.asset_type,
                signal.timeframe,
                signal.action,
                signal.signal_time.isoformat(),
                signal.close,
                received_at,
                signal.payload_json,
            ),
        )


def _months_between(a: datetime, b: datetime) -> int:
    return (a.year - b.year) * 12 + (a.month - b.month)


def _bars_since(now: datetime, signal_time: datetime, timeframe: str) -> int:
    delta = now - signal_time
    if timeframe == "daily":
        return max(0, int(delta.total_seconds() // 86400))
    if timeframe == "weekly":
        return max(0, int(delta.total_seconds() // (7 * 86400)))
    if timeframe == "monthly":
        return max(0, _months_between(now, signal_time))
    return 0


def _recent(bars_since: int | None, lookback: int) -> bool:
    return bars_since is not None and bars_since < lookback


def _tf_state(buy_recent: bool, sell_recent: bool, bars_since_buy: int | None, bars_since_sell: int | None) -> str:
    if not buy_recent and not sell_recent:
        return "neutral"
    if buy_recent and not sell_recent:
        return "buy"
    if sell_recent and not buy_recent:
        return "sell"
    if bars_since_buy is None:
        return "sell"
    if bars_since_sell is None:
        return "buy"
    if bars_since_buy < bars_since_sell:
        return "buy"
    if bars_since_sell < bars_since_buy:
        return "sell"
    return "mixed"


def load_tradingview_signals(db_path: Path, lookback_candles: Dict[str, int]) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT symbol, market, asset_type, timeframe, action, signal_time, close, received_at
            FROM tradingview_signals
            ORDER BY signal_time DESC
            """
        ).fetchall()

    latest_by_key: Dict[tuple[str, str, str], sqlite3.Row] = {}
    latest_received: str | None = None

    for row in rows:
        key = (row["symbol"], row["timeframe"], row["action"])
        if key not in latest_by_key:
            latest_by_key[key] = row
        if latest_received is None or row["received_at"] > latest_received:
            latest_received = row["received_at"]

    symbols = sorted({row["symbol"] for row in latest_by_key.values()})
    result: List[Dict[str, Any]] = []

    for symbol in symbols:
        market = "other"
        asset_type = "other"
        tfs: Dict[str, Dict[str, Any]] = {}

        for tf in ["daily", "weekly", "monthly"]:
            lookback = int(lookback_candles.get(tf, 1))
            buy_row = latest_by_key.get((symbol, tf, "buy"))
            sell_row = latest_by_key.get((symbol, tf, "sell"))

            if buy_row is not None:
                market = buy_row["market"]
                asset_type = buy_row["asset_type"]
            elif sell_row is not None:
                market = sell_row["market"]
                asset_type = sell_row["asset_type"]

            buy_time = datetime.fromisoformat(buy_row["signal_time"]) if buy_row else None
            sell_time = datetime.fromisoformat(sell_row["signal_time"]) if sell_row else None

            bars_since_buy = _bars_since(now, buy_time, tf) if buy_time else None
            bars_since_sell = _bars_since(now, sell_time, tf) if sell_time else None

            buy_recent = _recent(bars_since_buy, lookback)
            sell_recent = _recent(bars_since_sell, lookback)

            latest_close = 0.0
            if buy_row and sell_row:
                latest_close = float(buy_row["close"] if buy_time >= sell_time else sell_row["close"])
            elif buy_row:
                latest_close = float(buy_row["close"])
            elif sell_row:
                latest_close = float(sell_row["close"])

            tfs[tf] = {
                "state": _tf_state(buy_recent, sell_recent, bars_since_buy, bars_since_sell),
                "buy_signal": bars_since_buy == 0,
                "sell_signal": bars_since_sell == 0,
                "buy_recent": buy_recent,
                "sell_recent": sell_recent,
                "bars_since_buy": bars_since_buy,
                "bars_since_sell": bars_since_sell,
                "lookback": lookback,
                "close": latest_close,
                "trailing_stop": 0.0,
                "atr": 0.0,
            }

        states = {tfs[tf]["state"] for tf in ["daily", "weekly", "monthly"]}
        states.discard("neutral")
        if not states:
            overall = "neutral"
        elif states == {"buy"}:
            overall = "buy"
        elif states == {"sell"}:
            overall = "sell"
        else:
            overall = "mixed"

        has_buy = any(tfs[tf]["state"] == "buy" for tf in tfs)
        has_sell = any(tfs[tf]["state"] == "sell" for tf in tfs)

        result.append(
            {
                "symbol": symbol,
                "market": market,
                "asset_type": asset_type,
                "last_close": tfs["daily"]["close"] or tfs["weekly"]["close"] or tfs["monthly"]["close"],
                "has_buy": has_buy,
                "has_sell": has_sell,
                "state": overall,
                "last_received_at": latest_received,
                "timeframes": tfs,
            }
        )

    return result
