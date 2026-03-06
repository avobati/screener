from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .data_loader import load_market_data
from .scanner import scan_signals
from .strategy import load_strategy, save_strategy
from .tradingview_store import init_db, load_tradingview_signals, normalize_payload, store_signal

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STRATEGY_PATH = BASE_DIR / "config" / "strategy.json"
STATIC_DIR = BASE_DIR / "static"
TV_DB_PATH = Path(os.getenv("TV_DB_PATH", str(DATA_DIR / "tradingview_signals.db")))
SUPPORTED_TIMEFRAMES = {"all", "daily", "weekly", "monthly"}
SUPPORTED_SOURCES = {"local", "tradingview", "combined"}
DEFAULT_LOOKBACKS = {"daily": 180, "weekly": 24, "monthly": 6}

init_db(TV_DB_PATH)


def _allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGIN", "*").strip()
    if not raw:
        return ["*"]
    return [item.strip() for item in raw.split(",") if item.strip()]


def _origin_for_request(request_origin: str | None) -> str:
    allowed = _allowed_origins()
    if "*" in allowed:
        return "*"
    if request_origin and request_origin in allowed:
        return request_origin
    return allowed[0] if allowed else "*"


def _set_common_headers(handler: BaseHTTPRequestHandler, content_type: str, content_length: int) -> None:
    request_origin = handler.headers.get("Origin")
    allow_origin = _origin_for_request(request_origin)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(content_length))
    handler.send_header("Access-Control-Allow-Origin", allow_origin)
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, X-TV-Secret")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Vary", "Origin")


def _json(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    raw = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    _set_common_headers(handler, "application/json; charset=utf-8", len(raw))
    handler.end_headers()
    handler.wfile.write(raw)


def _matches_action(signal: dict, action: str, timeframe: str) -> bool:
    if timeframe == "all":
        states = [tf.get("state", "neutral") for tf in signal["timeframes"].values()]
    else:
        state = signal["timeframes"].get(timeframe, {}).get("state", "neutral")
        states = [state]

    if action == "buy":
        return any(s == "buy" for s in states)
    if action == "sell":
        return any(s == "sell" for s in states)
    if action == "neutral":
        return all(s == "neutral" for s in states)
    if action == "all":
        return True
    raise ValueError("Unsupported action filter")


def _merge_signals(local_signals: list[dict], tv_signals: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {s["symbol"]: s for s in local_signals}

    for tv in tv_signals:
        symbol = tv["symbol"]
        if symbol not in merged:
            merged[symbol] = tv
            continue

        base = merged[symbol]
        for tf in ["daily", "weekly", "monthly"]:
            tv_tf = tv["timeframes"].get(tf)
            if not tv_tf:
                continue
            if tv_tf.get("state") != "neutral":
                base["timeframes"][tf] = tv_tf

        states = {base["timeframes"][tf].get("state", "neutral") for tf in ["daily", "weekly", "monthly"]}
        states.discard("neutral")
        if not states:
            base["state"] = "neutral"
        elif states == {"buy"}:
            base["state"] = "buy"
        elif states == {"sell"}:
            base["state"] = "sell"
        else:
            base["state"] = "mixed"

        base["has_buy"] = any(base["timeframes"][tf].get("state") == "buy" for tf in base["timeframes"])
        base["has_sell"] = any(base["timeframes"][tf].get("state") == "sell" for tf in base["timeframes"])

    return list(merged.values())


def _filter_signals(signals: list[dict], market: str | None, action: str, timeframe: str) -> list[dict]:
    if market:
        signals = [s for s in signals if s.get("market", "").lower() == market.lower()]

    return [s for s in signals if _matches_action(s, action, timeframe)]


class AppHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        _set_common_headers(self, "text/plain; charset=utf-8", 0)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            _json(
                self,
                {
                    "status": "ok",
                    "service": "screener-backend",
                    "db_path": str(TV_DB_PATH),
                    "cors_allow_origin": _allowed_origins(),
                },
            )
            return

        if parsed.path == "/":
            self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return

        if parsed.path == "/app.js":
            self._serve_file(STATIC_DIR / "app.js", "text/javascript; charset=utf-8")
            return

        if parsed.path == "/styles.css":
            self._serve_file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
            return

        if parsed.path == "/api/strategy":
            strategy = load_strategy(STRATEGY_PATH)
            _json(self, strategy)
            return

        if parsed.path == "/api/signals":
            params = parse_qs(parsed.query)
            market = params.get("market", [None])[0]
            action = params.get("action", ["buy"])[0].lower()
            timeframe = params.get("timeframe", ["all"])[0].lower()
            source = params.get("source", ["combined"])[0].lower()

            if timeframe not in SUPPORTED_TIMEFRAMES:
                _json(self, {"error": "Unsupported timeframe filter"}, status=HTTPStatus.BAD_REQUEST)
                return

            if source not in SUPPORTED_SOURCES:
                _json(self, {"error": "Unsupported source filter"}, status=HTTPStatus.BAD_REQUEST)
                return

            strategy = load_strategy(STRATEGY_PATH)
            lookbacks = strategy.get("lookback_candles", DEFAULT_LOOKBACKS)

            local_signals: list[dict] = []
            tv_signals: list[dict] = []

            if source in {"local", "combined"}:
                series = load_market_data(DATA_DIR)
                local_signals = scan_signals(series, strategy)

            if source in {"tradingview", "combined"}:
                tv_signals = load_tradingview_signals(TV_DB_PATH, lookbacks)

            if source == "local":
                signals = local_signals
            elif source == "tradingview":
                signals = tv_signals
            else:
                signals = _merge_signals(local_signals, tv_signals)

            try:
                signals = _filter_signals(signals, market, action, timeframe)
            except ValueError:
                _json(self, {"error": "Unsupported action filter"}, status=HTTPStatus.BAD_REQUEST)
                return

            _json(self, {"count": len(signals), "signals": signals, "source": source})
            return

        if parsed.path == "/api/markets":
            strategy = load_strategy(STRATEGY_PATH)
            lookbacks = strategy.get("lookback_candles", DEFAULT_LOOKBACKS)
            local_series = load_market_data(DATA_DIR)
            local_markets = {s.market for s in local_series}
            tv_markets = {s["market"] for s in load_tradingview_signals(TV_DB_PATH, lookbacks)}
            markets = sorted(local_markets | tv_markets)
            _json(self, {"markets": markets})
            return

        if parsed.path == "/api/tradingview/status":
            secret_set = bool(os.getenv("TV_WEBHOOK_SECRET"))
            _json(self, {"status": "ok", "secret_configured": secret_set, "db_path": str(TV_DB_PATH)})
            return

        _json(self, {"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/api/strategy":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)

            try:
                payload = json.loads(raw.decode("utf-8"))
                save_strategy(STRATEGY_PATH, payload)
                _json(self, {"status": "ok"})
            except Exception as exc:  # noqa: BLE001
                _json(self, {"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/tradingview/webhook":
            secret = os.getenv("TV_WEBHOOK_SECRET", "")
            provided = self.headers.get("X-TV-Secret", "")
            params = parse_qs(urlparse(self.path).query)
            provided_query = params.get("secret", [""])[0]

            if secret and provided not in {secret, ""} and provided_query != secret:
                _json(self, {"error": "Unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
                return
            if secret and not provided and provided_query != secret:
                _json(self, {"error": "Unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
                return

            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)

            try:
                payload = json.loads(raw.decode("utf-8"))
                signal = normalize_payload(payload)
                store_signal(TV_DB_PATH, signal)
                _json(
                    self,
                    {
                        "status": "ok",
                        "stored": {
                            "symbol": signal.symbol,
                            "timeframe": signal.timeframe,
                            "action": signal.action,
                            "signal_time": signal.signal_time.isoformat(),
                        },
                    },
                )
            except Exception as exc:  # noqa: BLE001
                _json(self, {"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        _json(self, {"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            _json(self, {"error": "File not found"}, status=HTTPStatus.NOT_FOUND)
            return
        raw = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        _set_common_headers(self, content_type, len(raw))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format: str, *args: object) -> None:
        return


def run_server() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Server running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
