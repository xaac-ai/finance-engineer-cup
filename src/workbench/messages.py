"""Parse billing_followups.pdf into Billing Messages (id, timestamp, from, to, subject, body).

Each message starts with a header `MSG-YYYY-NNN | <date> America/Denver | <from> -> <to> | <subject>`
that can wrap onto the next line; the body runs until the next header. Page footers are dropped.
"""

from __future__ import annotations

import re
from datetime import datetime

import duckdb

from workbench.errors import InputError
from workbench.pdf import extract_to
from workbench.period import Period

HEADER_START = re.compile(r"^MSG-\d{4}-\d{3} \|")
FOOTER = re.compile(r"^RelayCloud \| Fictional challenge material \| Page \d+ of \d+$")
HEADER = re.compile(r"^(MSG-\d{4}-\d{3}) \| (.+?) America/Denver \| (.+?) -> (.+?) \| (.+)$")


def parse_billing_messages(text: str) -> list[dict]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not FOOTER.match(ln.strip())]
    blocks, cur = [], None
    for ln in lines:
        if HEADER_START.match(ln):
            cur = [ln]
            blocks.append(cur)
        elif cur is not None:
            cur.append(ln)
    messages = []
    for block in blocks:
        header, i = block[0], 1
        while header.count(" | ") < 3 and i < len(block):  # header wrapped
            header += " " + block[i]
            i += 1
        m = HEADER.match(header)
        if not m:
            raise InputError(f"Could not parse Billing Message header: {header!r}")
        ts = datetime.strptime(m.group(2), "%B %d, %Y %H:%M")
        messages.append({
            "message_id": m.group(1),
            "sent_at_local": ts.strftime("%Y-%m-%d %H:%M"),
            "sender": m.group(3).strip(),
            "recipient": m.group(4).strip(),
            "subject": m.group(5).strip(),
            "body": " ".join(block[i:]),
        })
    return messages


def load_billing_messages(con: duckdb.DuckDBPyConnection, period: Period) -> int:
    text = extract_to(period.raw_dir / "billing_followups.pdf", period.extracted_dir)
    msgs = parse_billing_messages(text)
    if not msgs:
        raise InputError("billing_followups.pdf contains no recognisable Billing Messages.")
    con.execute(
        "CREATE OR REPLACE TABLE billing_messages (message_id VARCHAR, sent_at TIMESTAMPTZ, sender VARCHAR, "
        "recipient VARCHAR, subject VARCHAR, body VARCHAR)"
    )
    con.executemany(
        # Timestamps are stated in America/Denver; the session TimeZone is pinned to it (db.py).
        "INSERT INTO billing_messages VALUES (?, CAST(? AS TIMESTAMP)::TIMESTAMPTZ, ?, ?, ?, ?)",
        [[m["message_id"], m["sent_at_local"], m["sender"], m["recipient"], m["subject"], m["body"]] for m in msgs],
    )
    return len(msgs)
