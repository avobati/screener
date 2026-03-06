from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List


@dataclass
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class InstrumentSeries:
    symbol: str
    asset_type: str
    market: str
    candles: List[Candle]


def _infer_market(asset_type: str) -> str:
    mapping = {
        "stock": "us-stocks",
        "etf": "us-etfs",
        "crypto": "crypto",
        "metal": "metals",
    }
    return mapping.get(asset_type, "other")


def load_market_data(data_dir: Path) -> List[InstrumentSeries]:
    grouped: Dict[str, InstrumentSeries] = {}

    for csv_path in sorted(data_dir.glob("*.csv")):
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol = row["symbol"].strip().upper()
                asset_type = row["asset_type"].strip().lower()
                market = row.get("market", "").strip().lower() or _infer_market(asset_type)
                candle = Candle(
                    timestamp=row["timestamp"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )

                if symbol not in grouped:
                    grouped[symbol] = InstrumentSeries(
                        symbol=symbol,
                        asset_type=asset_type,
                        market=market,
                        candles=[],
                    )

                grouped[symbol].candles.append(candle)

    for series in grouped.values():
        series.candles.sort(key=lambda c: c.timestamp)

    return list(grouped.values())


def aggregate_timeframe(candles: List[Candle], timeframe: str) -> List[Candle]:
    if timeframe == "daily":
        return candles

    bucketed: Dict[str, List[Candle]] = {}

    for candle in candles:
        dt = datetime.strptime(candle.timestamp, "%Y-%m-%d")
        if timeframe == "weekly":
            year, week, _ = dt.isocalendar()
            bucket = f"{year}-W{week:02d}"
        elif timeframe == "monthly":
            bucket = dt.strftime("%Y-%m")
        else:
            raise ValueError(f"Unsupported timeframe '{timeframe}'")

        bucketed.setdefault(bucket, []).append(candle)

    aggregated: List[Candle] = []
    for _, values in sorted(bucketed.items(), key=lambda x: x[0]):
        first = values[0]
        last = values[-1]
        aggregated.append(
            Candle(
                timestamp=last.timestamp,
                open=first.open,
                high=max(v.high for v in values),
                low=min(v.low for v in values),
                close=last.close,
                volume=sum(v.volume for v in values),
            )
        )

    return aggregated
