"""Approved concessions: curated from Billing Messages, verified against the message text.

Decision (wayfinder: "How is usage validated and attributed?"): the expected October usage accrual
is the expected invoice less approved concessions (START_HERE · CREDITS: "Approved reductions of
October consideration affect October where not already reflected"). Approval is a judgment read
from a message, so it is curated in data/curated/<period>/approvals.yaml with the exact quote,
and the run fails if the quote is not in a Controller-sent message.
"""

from __future__ import annotations

from decimal import Decimal

import duckdb
import yaml

from workbench.errors import InputError
from workbench.pdf import normalize
from workbench.period import Period


def load_approvals(con: duckdb.DuckDBPyConnection, period: Period) -> int:
    """Create `approved_concessions` and `concession_requests`. Requires `billing_messages`.
    Returns the number of quotes checked."""
    path = period.curated_dir / "approvals.yaml"
    curated = (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}
    con.execute("CREATE OR REPLACE TABLE approved_concessions (customer_id VARCHAR, stream VARCHAR, "
                "service_period VARCHAR, amount DECIMAL(18,2), message_id VARCHAR, quote VARCHAR)")
    messages = {r[0]: (r[1], r[2]) for r in con.execute("SELECT message_id, sender, body FROM billing_messages").fetchall()}
    con.execute("CREATE OR REPLACE TABLE concession_requests AS SELECT * FROM approved_concessions LIMIT 0")
    checked = 0
    for kind, table, controller_only in (("concessions", "approved_concessions", True),
                                         ("requests", "concession_requests", False)):
        rows = [_checked(c, messages, kind, controller_only) for c in curated.get(kind) or []]
        if rows:
            con.executemany(f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?, ?)", rows)
        checked += len(rows)
    return checked


def _checked(c: dict, messages: dict, kind: str, controller_only: bool) -> list:
    for key in ("customer_id", "stream", "service_period", "amount", "message_id", "quote"):
        if not c.get(key):
            raise InputError(f"approvals.yaml: an entry under {kind} is missing '{key}'.")
    if c["message_id"] not in messages:
        raise InputError(f"approvals.yaml cites {c['message_id']}, which is not in billing_followups.pdf.")
    sender, body = messages[c["message_id"]]
    if controller_only and "controller" not in sender.lower():
        raise InputError(f"approvals.yaml: {c['message_id']} is from {sender!r}, not the Controller.")
    if normalize(c["quote"]) not in normalize(body):
        raise InputError(f"approvals.yaml: quote for {c['message_id']} is not in the message:\n  {c['quote']!r}")
    return [str(c["customer_id"]), c["stream"], str(c["service_period"]), Decimal(str(c["amount"])),
            c["message_id"], c["quote"]]


def message_evidence(ctx, message_id: str, role: str):
    """A Billing Message cited as evidence, with its full body."""
    from workbench.findings import Evidence
    r = ctx.rows("SELECT message_id, sender, body FROM billing_messages WHERE message_id = ?", [message_id])[0]
    return Evidence("billing_message", f"data/raw/{ctx.period.key}/billing_followups.pdf", None,
                    f"{r['message_id']} ({r['sender']}): {r['body']}", role)
