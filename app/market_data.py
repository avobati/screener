from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from .data_loader import Candle


@dataclass
class UniverseInstrument:
    symbol: str
    provider_symbol: str
    market: str
    asset_type: str


def _dt_from_unix(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def fetch_yahoo_daily(provider_symbol: str, range_name: str = "2y") -> List[Candle]:
    encoded = urllib.parse.quote(provider_symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?interval=1d&range={range_name}"

    with urllib.request.urlopen(url, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))

    result = payload.get("chart", {}).get("result")
    if not result:
        return []

    data = result[0]
    timestamps = data.get("timestamp", [])
    quote = data.get("indicators", {}).get("quote", [{}])[0]

    opens = quote.get("open", [])
    highs = quote.get("high", [])
    lows = quote.get("low", [])
    closes = quote.get("close", [])
    volumes = quote.get("volume", [])

    candles: List[Candle] = []
    for i, ts in enumerate(timestamps):
        try:
            o = opens[i]
            h = highs[i]
            l = lows[i]
            c = closes[i]
            v = volumes[i] if i < len(volumes) and volumes[i] is not None else 0
            if None in {o, h, l, c}:
                continue
            candles.append(
                Candle(
                    timestamp=_dt_from_unix(int(ts)),
                    open=float(o),
                    high=float(h),
                    low=float(l),
                    close=float(c),
                    volume=float(v),
                )
            )
        except (IndexError, TypeError, ValueError):
            continue

    candles.sort(key=lambda c: c.timestamp)
    return candles


def load_universe(path: str) -> List[UniverseInstrument]:
    with open(path, "r", encoding="utf-8-sig") as f:
        raw = json.load(f)

    universe: List[UniverseInstrument] = []
    for item in raw:
        universe.append(
            UniverseInstrument(
                symbol=str(item["symbol"]).upper(),
                provider_symbol=str(item.get("provider_symbol") or item["symbol"]),
                market=str(item["market"]).lower(),
                asset_type=str(item["asset_type"]).lower(),
            )
        )
    return universe
