from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


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
                error_message TEXT,
                scan_group TEXT
            )
            """
        )

        cols = {row[1] for row in conn.execute("PRAGMA table_info(scan_runs)").fetchall()}
        if "scan_group" not in cols:
            conn.execute("ALTER TABLE scan_runs ADD COLUMN scan_group TEXT")

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
            CREATE TABLE IF NOT EXISTS latest_signals (
                symbol TEXT PRIMARY KEY,
                market TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scan_signals_run_id
            ON scan_signals(run_id)
            """
        )


def start_run(db_path: Path, scan_group: str | None = None) -> str:
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO scan_runs (run_id, started_at, ended_at, status, scanned_symbols, error_message, scan_group) VALUES (?, ?, NULL, 'running', 0, NULL, ?)",
            (run_id, started_at, scan_group),
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
    now = datetime.now(timezone.utc).isoformat()
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
        conn.executemany(
            """
            INSERT INTO latest_signals(symbol, market, asset_type, payload_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
              market=excluded.market,
              asset_type=excluded.asset_type,
              payload_json=excluded.payload_json,
              updated_at=excluded.updated_at
            """,
            [
                (
                    str(s.get("symbol", "")),
                    str(s.get("market", "")),
                    str(s.get("asset_type", "")),
                    json.dumps(s),
                    now,
                )
                for s in signals
            ],
        )


def load_latest_scan_status(db_path: Path) -> Dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT run_id, started_at, ended_at, status, scanned_symbols, error_message, scan_group FROM scan_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()

    if not row:
        return {
            "run_id": None,
            "started_at": None,
            "ended_at": None,
            "status": "never_run",
            "scanned_symbols": 0,
            "error_message": None,
            "scan_group": None,
        }

    return dict(row)


def load_latest_signals(db_path: Path) -> List[Dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT payload_json FROM latest_signals ORDER BY symbol ASC").fetchall()
    return [json.loads(r["payload_json"]) for r in rows]
