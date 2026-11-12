"""PDF text extraction. The extracted text is written out so reviewers see exactly what was parsed."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader


def extract_text(path: Path) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(path).pages)


def extract_to(path: Path, out_dir: Path) -> str:
    """Extract one PDF's text and save it as <out_dir>/<stem>.txt. Returns the text."""
    text = extract_text(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{path.stem}.txt").write_text(text, encoding="utf-8")
    return text


def normalize(text: str) -> str:
    """Collapse all whitespace runs to single spaces (PDF prose wraps at arbitrary points)."""
    return re.sub(r"\s+", " ", text).strip()
