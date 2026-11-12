from workbench.messages import parse_billing_messages
from workbench.pdf import extract_text

from conftest import REPO


def test_parse_all_messages_including_wrapped_headers():
    msgs = parse_billing_messages(extract_text(REPO / "data" / "raw" / "2026-10" / "billing_followups.pdf"))
    assert len(msgs) == 10
    m = {x["message_id"]: x for x in msgs}
    assert m["MSG-2026-104"]["recipient"] == "Billing and Revenue Accounting"
    assert m["MSG-2026-104"]["subject"] == "Signed amendments"
    assert m["MSG-2026-109"]["sender"] == "Priya Shah, Controller"
    assert m["MSG-2026-125"]["body"].endswith("supported by opening balances and plan references.")
    assert "Page 1 of 2" not in m["MSG-2026-125"]["body"]
