"""Agent and model steps. They run outside `make run` (separate make targets, pinned models), and their
outputs are committed so the deterministic review and CI never need an API key.
Decision (wayfinder: "Accounting logic: the Round 1 deliverable" Notes, AI placement)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def api_key(name: str, root: Path) -> str | None:
    """A key from the environment, else from the repo's gitignored .env (KEY=value lines). Never logged."""
    if os.environ.get(name):
        return os.environ[name]
    env = root / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip() == name and v.strip():
                return v.strip().strip('"').strip("'")
    return None


def cache_key(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]


class ResponseCache:
    """Committed request -> response cache, so a rerun without a key replays the recorded answers."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict = json.loads(path.read_text()) if path.exists() else {}

    def get(self, key: str):
        return self.data.get(key)

    def put(self, key: str, value) -> None:
        self.data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
