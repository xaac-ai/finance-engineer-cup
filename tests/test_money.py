from decimal import Decimal

from workbench.money import cents_to_usd, day_share, round_cents, round_whole


def test_half_up_not_bankers():
    assert round_cents(Decimal("2.345")) == Decimal("2.35")
    assert round_cents(Decimal("2.335")) == Decimal("2.34")  # banker's would give 2.34 too; check a tie that differs:
    assert round_cents(Decimal("0.125")) == Decimal("0.13")  # banker's -> 0.12
    assert round_whole(Decimal("37741.5")) == 37742
    assert round_whole(Decimal("2.5")) == 3


def test_cents_and_day_share():
    assert cents_to_usd(143736) == Decimal("1437.36")
    # AM-OF-2026-164 states: USD 12,000 x 16 / 365, half up = 526.03
    assert day_share(Decimal("12000"), 16) == Decimal("526.03")
