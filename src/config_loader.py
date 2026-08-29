from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.settings import AppSettings, load_settings


def load_config(path: Path | str = "config.yaml") -> dict[str, Any]:
    """Backward-compatible dict-style config loader."""
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)
