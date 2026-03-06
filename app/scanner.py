from __future__ import annotations

from typing import Any, Dict, List

from .data_loader import InstrumentSeries, aggregate_timeframe
from .indicators import ut_bot_alerts

DEFAULT_LOOKBACK = {
    "daily": 180,
    "weekly": 24,
    "monthly": 6,
}


def _timeframe_state(tf_data: Dict[str, Any]) -> str:
    buy_recent = bool(tf_data.get("buy_recent", False))
    sell_recent = bool(tf_data.get("sell_recent", False))

    if not buy_recent and not sell_recent:
        return "neutral"
    if buy_recent and not sell_recent:
        return "buy"
    if sell_recent and not buy_recent:
        return "sell"

    bars_since_buy = tf_data.get("bars_since_buy")
    bars_since_sell = tf_data.get("bars_since_sell")

    if bars_since_buy is None and bars_since_sell is None:
        return "neutral"
    if bars_since_buy is None:
        return "sell"
    if bars_since_sell is None:
        return "buy"

    if bars_since_buy < bars_since_sell:
        return "buy"
    if bars_since_sell < bars_since_buy:
        return "sell"
    return "mixed"


def _overall_state(timeframe_states: Dict[str, str]) -> str:
    states = set(timeframe_states.values())
    states.discard("neutral")

    if not states:
        return "neutral"
    if states == {"buy"}:
        return "buy"
    if states == {"sell"}:
        return "sell"
    return "mixed"


def scan_signals(series_list: List[InstrumentSeries], strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
    key_value = float(strategy.get("key_value", 2))
    atr_period = int(strategy.get("atr_period", 6))
    timeframes = strategy.get("timeframes", ["daily", "weekly", "monthly"])
    lookbacks = {**DEFAULT_LOOKBACK, **strategy.get("lookback_candles", {})}

    results: List[Dict[str, Any]] = []

    for series in series_list:
        if len(series.candles) < 40:
            continue

        tf_signals: Dict[str, Dict[str, Any]] = {}
        tf_states: Dict[str, str] = {}

        for tf in timeframes:
            agg = aggregate_timeframe(series.candles, tf)
            tf_signals[tf] = ut_bot_alerts(agg, key_value, atr_period, int(lookbacks.get(tf, DEFAULT_LOOKBACK.get(tf, 3))))
            tf_states[tf] = _timeframe_state(tf_signals[tf])

        has_buy = any(state == "buy" for state in tf_states.values())
        has_sell = any(state == "sell" for state in tf_states.values())

        results.append(
            {
                "symbol": series.symbol,
                "asset_type": series.asset_type,
                "market": series.market,
                "last_close": round(series.candles[-1].close, 6),
                "has_buy": has_buy,
                "has_sell": has_sell,
                "state": _overall_state(tf_states),
                "timeframes": {
                    tf: {
                        "state": tf_states[tf],
                        "buy_signal": bool(data["buy_signal"]),
                        "sell_signal": bool(data["sell_signal"]),
                        "buy_recent": bool(data["buy_recent"]),
                        "sell_recent": bool(data["sell_recent"]),
                        "bars_since_buy": data["bars_since_buy"],
                        "bars_since_sell": data["bars_since_sell"],
                        "lookback": int(data["lookback"]),
                        "close": round(float(data["close"]), 6),
                        "trailing_stop": round(float(data["trailing_stop"]), 6),
                        "atr": round(float(data["atr"]), 6),
                    }
                    for tf, data in tf_signals.items()
                },
            }
        )

    return results
