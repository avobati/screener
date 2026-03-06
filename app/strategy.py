from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_strategy(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_strategy(path: Path, strategy: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(strategy, f, indent=2)
