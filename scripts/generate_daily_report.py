from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_URL = (os.getenv("BACKEND_URL") or "https://avo-screener.onrender.com").rstrip("/")
SOURCE = "backend"
POLL_SECONDS = int(os.getenv("SCAN_POLL_SECONDS", "10"))
POLL_TIMEOUT_SECONDS = int(os.getenv("SCAN_TIMEOUT_SECONDS", "1800"))
REPORT_ROOT = Path("reports")
DAILY_DIR = REPORT_ROOT / "daily"
LATEST_REPORT = REPORT_ROOT / "latest.md"


@dataclass
class ScanStatus:
    run_id: str | None
    status: str
    started_at: str | None
    ended_at: str | None
    scanned_symbols: int
    error_message: str | None


def _request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{BASE_URL}{path}"
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url=url, method=method.upper(), data=body, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method.upper()} {path} failed: HTTP {exc.code} - {raw}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method.upper()} {path} failed: {exc.reason}") from exc


def trigger_scan() -> dict[str, Any]:
    return _request_json("POST", "/api/scans/run", payload={})


def load_scan_status() -> ScanStatus:
    data = _request_json("GET", "/api/scans/status")
    return ScanStatus(
        run_id=data.get("run_id"),
        status=data.get("status", "unknown"),
        started_at=data.get("started_at"),
        ended_at=data.get("ended_at"),
        scanned_symbols=int(data.get("scanned_symbols", 0)),
        error_message=data.get("error_message"),
    )


def wait_for_scan_completion() -> ScanStatus:
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    while time.time() < deadline:
        status = load_scan_status()
        if status.status != "running":
            return status
        time.sleep(POLL_SECONDS)
    raise TimeoutError(f"Scan did not complete within {POLL_TIMEOUT_SECONDS} seconds")


def count_signals(action: str, timeframe: str) -> int:
    params = urllib.parse.urlencode({"source": SOURCE, "action": action, "timeframe": timeframe})
    data = _request_json("GET", f"/api/signals?{params}")
    return int(data.get("count", 0))


def top_symbols(action: str, timeframe: str, limit: int = 20) -> list[str]:
    params = urllib.parse.urlencode({"source": SOURCE, "action": action, "timeframe": timeframe})
    data = _request_json("GET", f"/api/signals?{params}")
    symbols = [str(item.get("symbol", "")).strip() for item in data.get("signals", [])]
    symbols = [s for s in symbols if s]
    return symbols[:limit]


def render_report(status: ScanStatus) -> str:
    now_utc = datetime.now(timezone.utc).isoformat()

    counts = {
        "all_all": count_signals("all", "all"),
        "buy_all": count_signals("buy", "all"),
        "sell_all": count_signals("sell", "all"),
        "buy_daily": count_signals("buy", "daily"),
        "buy_weekly": count_signals("buy", "weekly"),
        "buy_monthly": count_signals("buy", "monthly"),
        "sell_daily": count_signals("sell", "daily"),
        "sell_weekly": count_signals("sell", "weekly"),
        "sell_monthly": count_signals("sell", "monthly"),
    }

    buy_daily_symbols = ", ".join(top_symbols("buy", "daily")) or "none"
    sell_daily_symbols = ", ".join(top_symbols("sell", "daily")) or "none"

    return "\n".join(
        [
            "# Daily Screener Report",
            "",
            f"Generated (UTC): {now_utc}",
            f"Backend: {BASE_URL}",
            "",
            "## Scan Run",
            f"- run_id: {status.run_id}",
            f"- status: {status.status}",
            f"- started_at: {status.started_at}",
            f"- ended_at: {status.ended_at}",
            f"- scanned_symbols: {status.scanned_symbols}",
            f"- error_message: {status.error_message or 'none'}",
            "",
            "## Counts",
            f"- all (all timeframes): {counts['all_all']}",
            f"- buy (all timeframes): {counts['buy_all']}",
            f"- sell (all timeframes): {counts['sell_all']}",
            f"- buy daily: {counts['buy_daily']}",
            f"- buy weekly: {counts['buy_weekly']}",
            f"- buy monthly: {counts['buy_monthly']}",
            f"- sell daily: {counts['sell_daily']}",
            f"- sell weekly: {counts['sell_weekly']}",
            f"- sell monthly: {counts['sell_monthly']}",
            "",
            "## Top Daily Buys",
            buy_daily_symbols,
            "",
            "## Top Daily Sells",
            sell_daily_symbols,
            "",
        ]
    )


def main() -> None:
    DAILY_DIR.mkdir(parents=True, exist_ok=True)

    trigger_response = trigger_scan()
    print(f"Triggered scan response: {trigger_response}")

    final_status = wait_for_scan_completion()
    if final_status.status != "ok":
        raise RuntimeError(
            f"Scan finished with status={final_status.status}, error={final_status.error_message or 'none'}"
        )

    report = render_report(final_status)
    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dated_path = DAILY_DIR / f"{report_date}.md"

    dated_path.write_text(report, encoding="utf-8")
    LATEST_REPORT.write_text(report, encoding="utf-8")

    print(f"Wrote report: {dated_path}")
    print(f"Updated latest: {LATEST_REPORT}")


if __name__ == "__main__":
    main()

