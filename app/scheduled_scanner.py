from __future__ import annotations

import os
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from .data_loader import InstrumentSeries
from .market_data import UniverseInstrument, fetch_yahoo_daily, load_universe
from .scan_store import finish_run, init_scan_db, load_latest_scan_status, save_run_signals, start_run
from .scanner import scan_signals
from .strategy import load_strategy


class ScheduledScanner:
    def __init__(self, strategy_path: Path, universe_path: Path, scan_db_path: Path) -> None:
        self.strategy_path = strategy_path
        self.universe_path = universe_path
        self.scan_db_path = scan_db_path
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._stagger_index = 0
        init_scan_db(scan_db_path)

    def _load_universe(self) -> List[UniverseInstrument]:
        return load_universe(str(self.universe_path))

    def groups(self) -> Dict[str, int]:
        counts: Dict[str, int] = defaultdict(int)
        for inst in self._load_universe():
            counts[inst.group] += 1
        return dict(sorted(counts.items(), key=lambda x: x[0]))

    def _sequence(self) -> List[str]:
        configured = os.getenv("SCAN_STAGGER_GROUPS", "").strip().lower()
        if configured:
            return [x.strip() for x in configured.split(",") if x.strip()]
        return list(self.groups().keys())

    def run_once(self, group: str | None = None) -> Dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            return {"status": "running", "message": "scan already in progress"}

        run_id = start_run(self.scan_db_path, scan_group=group)
        scanned_symbols = 0
        failures: List[str] = []
        delay_ms = int(os.getenv("SCAN_REQUEST_DELAY_MS", "1300"))

        try:
            strategy = load_strategy(self.strategy_path)
            universe = self._load_universe()
            if group:
                universe = [u for u in universe if u.group == group]

            series_list: List[InstrumentSeries] = []
            for idx, inst in enumerate(universe):
                try:
                    candles = fetch_yahoo_daily(inst.provider_symbol, range_name="2y")
                    if len(candles) < 40:
                        failures.append(f"{inst.symbol}: insufficient candles")
                        continue
                    scanned_symbols += 1
                    series_list.append(
                        InstrumentSeries(
                            symbol=inst.symbol,
                            asset_type=inst.asset_type,
                            market=inst.market,
                            candles=candles,
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{inst.symbol}: {exc}")
                finally:
                    if idx < len(universe) - 1 and delay_ms > 0:
                        time.sleep(delay_ms / 1000.0)

            signals = scan_signals(series_list, strategy)
            save_run_signals(self.scan_db_path, run_id, signals)

            status = "ok" if scanned_symbols > 0 else "error"
            error_message = "; ".join(failures[:20]) if failures else None
            finish_run(self.scan_db_path, run_id, status, scanned_symbols, error_message)

            return {
                "status": status,
                "run_id": run_id,
                "scan_group": group,
                "scanned_symbols": scanned_symbols,
                "signal_count": len(signals),
                "failed_symbols": len(failures),
                "failures_preview": failures[:10],
            }
        except Exception as exc:  # noqa: BLE001
            finish_run(self.scan_db_path, run_id, "error", scanned_symbols, str(exc))
            return {
                "status": "error",
                "run_id": run_id,
                "scan_group": group,
                "scanned_symbols": scanned_symbols,
                "error": str(exc),
            }
        finally:
            self._lock.release()

    def run_next_staggered(self) -> Dict[str, Any]:
        sequence = self._sequence()
        if not sequence:
            return {"status": "error", "error": "No scan groups configured"}
        group = sequence[self._stagger_index % len(sequence)]
        self._stagger_index += 1
        return self.run_once(group=group)

    def start_background(self, interval_minutes: int, run_on_start: bool) -> None:
        if self._running:
            return

        self._running = True

        def loop() -> None:
            mode = os.getenv("SCAN_MODE", "full").strip().lower()
            if run_on_start:
                if mode == "staggered":
                    self.run_next_staggered()
                else:
                    self.run_once()

            interval_seconds = max(60, interval_minutes * 60)
            while self._running:
                time.sleep(interval_seconds)
                if mode == "staggered":
                    self.run_next_staggered()
                else:
                    self.run_once()

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def status(self) -> Dict[str, Any]:
        status = load_latest_scan_status(self.scan_db_path)
        status["groups"] = self.groups()
        status["scan_mode"] = os.getenv("SCAN_MODE", "full").strip().lower()
        status["stagger_sequence"] = self._sequence()
        return status
