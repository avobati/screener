from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class ScanRun:
    run_id: str
    started_at: str
    ended_at: str | None
    status: str
    scanned_symbols: int
    error_message: str | None


def init_scan_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                status TEXT NOT NULL,
                scanned_symbols INTEGER NOT NULL DEFAULT 0,
                error_message TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                market TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES scan_runs(run_id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scan_signals_run_id
            ON scan_signals(run_id)
            """
        )


def start_run(db_path: Path) -> str:
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO scan_runs (run_id, started_at, ended_at, status, scanned_symbols, error_message) VALUES (?, ?, NULL, 'running', 0, NULL)",
            (run_id, started_at),
        )
    return run_id


def finish_run(db_path: Path, run_id: str, status: str, scanned_symbols: int, error_message: str | None = None) -> None:
    ended_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE scan_runs SET ended_at=?, status=?, scanned_symbols=?, error_message=? WHERE run_id=?",
            (ended_at, status, scanned_symbols, error_message, run_id),
        )


def save_run_signals(db_path: Path, run_id: str, signals: List[Dict[str, Any]]) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM scan_signals WHERE run_id=?", (run_id,))
        conn.executemany(
            "INSERT INTO scan_signals (run_id, symbol, market, asset_type, payload_json) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    run_id,
                    str(s.get("symbol", "")),
                    str(s.get("market", "")),
                    str(s.get("asset_type", "")),
                    json.dumps(s),
                )
                for s in signals
            ],
        )


def load_latest_scan_status(db_path: Path) -> Dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT run_id, started_at, ended_at, status, scanned_symbols, error_message FROM scan_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()

    if not row:
        return {
            "run_id": None,
            "started_at": None,
            "ended_at": None,
            "status": "never_run",
            "scanned_symbols": 0,
            "error_message": None,
        }

    return dict(row)


def load_latest_signals(db_path: Path) -> List[Dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        latest = conn.execute("SELECT run_id FROM scan_runs WHERE status='ok' ORDER BY started_at DESC LIMIT 1").fetchone()
        if not latest:
            return []

        run_id = latest["run_id"]
        rows = conn.execute("SELECT payload_json FROM scan_signals WHERE run_id=?", (run_id,)).fetchall()

    return [json.loads(r["payload_json"]) for r in rows]
