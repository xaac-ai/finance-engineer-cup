"""A review period: where its inputs live, where its outputs go, and its curated parameters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from workbench.errors import InputError


@dataclass(frozen=True)
class Period:
    key: str  # "2026-10"
    root: Path  # repo root
    cutoff: str  # ISO timestamp with offset, from curated period.yaml
    expected_counts: dict[str, int] = field(default_factory=dict)

    @property
    def start(self) -> date:
        y, m = map(int, self.key.split("-"))
        return date(y, m, 1)

    @property
    def end_exclusive(self) -> date:
        s = self.start
        return date(s.year + (s.month == 12), s.month % 12 + 1, 1)

    @property
    def label(self) -> str:
        """NetSuite posting-period label, e.g. 'Oct 2026'."""
        return self.start.strftime("%b %Y")

    @property
    def raw_dir(self) -> Path:
        return self.root / "data" / "raw" / self.key

    @property
    def curated_dir(self) -> Path:
        return self.root / "data" / "curated" / self.key

    @property
    def reference_dir(self) -> Path:
        return self.root / "data" / "reference"

    @property
    def out_dir(self) -> Path:
        return self.root / "out" / self.key

    @property
    def extracted_dir(self) -> Path:
        return self.out_dir / "extracted"


def load_period(key: str, root: Path | None = None) -> Period:
    root = (root or Path.cwd()).resolve()
    cfg_path = root / "data" / "curated" / key / "period.yaml"
    if not cfg_path.exists():
        raise InputError(
            f"Missing curated period file {cfg_path.relative_to(root)}. "
            f"Create it with the period's cutoff and expected row counts (see data/curated/2026-10/period.yaml)."
        )
    cfg = yaml.safe_load(cfg_path.read_text())
    if str(cfg.get("period")) != key:
        raise InputError(f"{cfg_path.relative_to(root)} declares period {cfg.get('period')!r}, expected {key!r}.")
    return Period(
        key=key,
        root=root,
        cutoff=str(cfg["cutoff"]),
        expected_counts={str(k): int(v) for k, v in (cfg.get("expected_counts") or {}).items()},
    )
