"""Settings from environment variables (and an optional local .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PREFIX = "SHELF_"


def load_env_file(path: str | os.PathLike = ".env") -> int:
    """Read KEY=VALUE lines into os.environ. Existing variables win. Returns the count of new keys."""
    p = Path(path)
    if not p.is_file():
        return 0
    added = 0
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        value = value.strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value
            added += 1
    return added


def _get(name: str, default: str = "") -> str:
    value = os.environ.get(PREFIX + name, "")
    return value.strip() if value.strip() else default


@dataclass(frozen=True)
class Settings:
    data_dir: str | None
    file_pattern: str
    output_dir: str
    seed: int
    published_totals: str | None
    indicator_csv: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=_get("DATA_DIR") or None,
            file_pattern=_get("FILE_PATTERN", "*LibraryDataset.csv"),
            output_dir=_get("OUTPUT", "reports/latest"),
            seed=int(_get("SEED", "42")),
            published_totals=_get("PUBLISHED_TOTALS") or None,
            indicator_csv=_get("INDICATOR_CSV") or None,
        )
