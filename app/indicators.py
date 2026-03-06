from __future__ import annotations

from typing import Dict, List

from .data_loader import Candle


def _true_range(current: Candle, prev_close: float) -> float:
    return max(
        current.high - current.low,
        abs(current.high - prev_close),
        abs(current.low - prev_close),
    )


def atr(candles: List[Candle], period: int) -> List[float]:
    if len(candles) < 2:
        return [0.0 for _ in candles]

    tr_values: List[float] = [0.0]
    for i in range(1, len(candles)):
        tr_values.append(_true_range(candles[i], candles[i - 1].close))

    atr_values: List[float] = [0.0 for _ in candles]
    if len(candles) <= period:
        return atr_values

    seed = sum(tr_values[1 : period + 1]) / period
    atr_values[period] = seed

    for i in range(period + 1, len(candles)):
        atr_values[i] = ((atr_values[i - 1] * (period - 1)) + tr_values[i]) / period

    return atr_values


def _last_true_index(values: List[bool]) -> int | None:
    for i in range(len(values) - 1, -1, -1):
        if values[i]:
            return i
    return None


def ut_bot_alerts(candles: List[Candle], key_value: float, atr_period: int, lookback: int) -> Dict[str, float | bool | int | None]:
    if len(candles) < atr_period + 3:
        return {
            "buy_signal": False,
            "sell_signal": False,
            "buy_recent": False,
            "sell_recent": False,
            "bars_since_buy": None,
            "bars_since_sell": None,
            "atr": 0.0,
            "trailing_stop": 0.0,
            "close": candles[-1].close if candles else 0.0,
            "lookback": lookback,
        }

    closes = [c.close for c in candles]
    atr_values = atr(candles, atr_period)
    trails: List[float] = [closes[0]]

    for i in range(1, len(candles)):
        n_loss = key_value * atr_values[i]
        prev_trail = trails[-1]
        prev_close = closes[i - 1]
        close = closes[i]

        if close > prev_trail and prev_close > prev_trail:
            next_trail = max(prev_trail, close - n_loss)
        elif close < prev_trail and prev_close < prev_trail:
            next_trail = min(prev_trail, close + n_loss)
        elif close > prev_trail:
            next_trail = close - n_loss
        else:
            next_trail = close + n_loss

        trails.append(next_trail)

    buy_flags = [False for _ in closes]
    sell_flags = [False for _ in closes]

    for i in range(1, len(closes)):
        buy_flags[i] = closes[i] > trails[i] and closes[i - 1] <= trails[i - 1]
        sell_flags[i] = closes[i] < trails[i] and closes[i - 1] >= trails[i - 1]

    buy_signal = buy_flags[-1]
    sell_signal = sell_flags[-1]

    last_buy_idx = _last_true_index(buy_flags)
    last_sell_idx = _last_true_index(sell_flags)

    bars_since_buy = None if last_buy_idx is None else (len(closes) - 1 - last_buy_idx)
    bars_since_sell = None if last_sell_idx is None else (len(closes) - 1 - last_sell_idx)

    buy_recent = bars_since_buy is not None and bars_since_buy < lookback
    sell_recent = bars_since_sell is not None and bars_since_sell < lookback

    return {
        "buy_signal": buy_signal,
        "sell_signal": sell_signal,
        "buy_recent": buy_recent,
        "sell_recent": sell_recent,
        "bars_since_buy": bars_since_buy,
        "bars_since_sell": bars_since_sell,
        "atr": atr_values[-1],
        "trailing_stop": trails[-1],
        "close": closes[-1],
        "lookback": lookback,
    }
