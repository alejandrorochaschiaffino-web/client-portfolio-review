"""
Duration and the bond rate-shock test.

Macaulay duration = the weighted-average time until you get your money
back, where each payment's weight is its share of the bond's present value.
This is the same Weight x Time method from the class Excel sheet.

Divide it by (1 + yield per period) to get MODIFIED duration, which is the
rule of thumb for interest-rate risk:

    % change in bond price  ~=  -modified duration x change in yield

Bond funds publish an effective duration that works the same way, so a fund
with a 5.8-year duration loses about 5.8% if rates rise 1 percentage point.
"""

from .allocation import Allocation
from .portfolios import FUND_DURATIONS


def cash_flows(face, coupon_rate, years, freq):
    """List of (period, payment). The last period also repays the face value."""
    n = round(years * freq)
    coupon = face * coupon_rate / freq
    return [(t, coupon + (face if t == n else 0)) for t in range(1, n + 1)]


def bond_price(face, coupon_rate, ytm, years, freq=2):
    rate = ytm / freq
    return sum(cf / (1 + rate) ** t for t, cf in cash_flows(face, coupon_rate, years, freq))


def macaulay_duration(face, coupon_rate, ytm, years, freq=2):
    """Duration in YEARS: sum of (weight x period), divided by payments per year."""
    rate = ytm / freq
    price = bond_price(face, coupon_rate, ytm, years, freq)
    periods = sum((cf / (1 + rate) ** t) / price * t
                  for t, cf in cash_flows(face, coupon_rate, years, freq))
    return periods / freq


def modified_duration(face, coupon_rate, ytm, years, freq=2):
    """Macaulay duration adjusted for compounding; this is the price-sensitivity number."""
    return macaulay_duration(face, coupon_rate, ytm, years, freq) / (1 + ytm / freq)


def rate_shock(alloc: Allocation, change_in_rates: float) -> dict:
    """
    Estimate the dollar change in a portfolio's bond and cash holdings if
    interest rates move by `change_in_rates` (0.01 = +1 percentage point).
    """
    lines = []
    for h in alloc.holdings:
        d = FUND_DURATIONS.get(h.ticker)
        if d is None:
            continue
        pct = -d * change_in_rates
        lines.append({"ticker": h.ticker, "dollars": h.dollars,
                      "duration": d, "pct_change": pct,
                      "dollar_change": round(h.dollars * pct, 2)})
    total = round(sum(l["dollar_change"] for l in lines), 2)
    return {"change_in_rates": change_in_rates, "lines": lines,
            "total_dollar_change": total,
            "pct_of_portfolio": total / alloc.amount}
