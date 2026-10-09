"""
Three questions clients actually ask an advisor after a crash:

1. Recovery time   - "How long until I'm back to even?"
2. Panic-selling   - "What if I sell now and wait until things calm down?"
3. Timing risk     - "Does it matter WHEN a crash happens if I'm retired?"
"""

import pandas as pd

from .risk import SCENARIOS, _nearest, portfolio_index, stress_test

DAYS_PER_MONTH = 365.25 / 12


def _months(a: pd.Timestamp, b: pd.Timestamp) -> float:
    return (b - a).days / DAYS_PER_MONTH


# ---------------------------------------------------------------- 1. Recovery

def recovery_time(prices: pd.DataFrame, weights: dict, peak: str, bottom: str) -> dict:
    """
    Buy at the peak and hold (same method as the stress test). Find the first
    day after the bottom when the portfolio is back to its starting value.
    """
    p, b = _nearest(prices, peak), _nearest(prices, bottom)
    cols = [t for t, w in weights.items() if w > 0]
    held = prices.loc[p:, cols]
    value = sum(held[t] / held[t].iloc[0] * weights[t] for t in cols)

    after = value.loc[b:]
    back = after[after >= 1.0]
    if back.empty:
        return {"recovered": False, "recovery_date": None,
                "months_total": None, "months_from_bottom": None,
                "still_down": float(value.iloc[-1] - 1)}
    r = back.index[0]
    return {"recovered": True, "recovery_date": r,
            "months_total": _months(p, r), "months_from_bottom": _months(b, r),
            "still_down": 0.0}


def all_recoveries(prices, weights):
    return {name: recovery_time(prices, weights, s, e)
            for name, (s, e) in SCENARIOS.items()}


# ----------------------------------------------------------- 2. Panic-selling

def panic_sell_cost(prices: pd.DataFrame, weights: dict, amount: float,
                    peak: str, bottom: str, wait_months: int = 12) -> dict:
    """
    Two clients invest `amount` at the peak in the same portfolio and ride
    the crash to the bottom (same numbers as the stress test). From there:
    - one stays invested until today, rebalanced monthly;
    - the other sells everything at the bottom, holds T-bills (SGOV) for
      `wait_months`, then buys the same portfolio back.
    """
    b = _nearest(prices, bottom)
    back_in = _nearest(prices, b + pd.DateOffset(months=wait_months))

    at_bottom = amount * (1 + stress_test(prices, weights, 1.0, peak, bottom)["return"])
    index = portfolio_index(prices, weights, start=b)      # $1 at the bottom
    stayed = at_bottom * index.iloc[-1]
    cash_growth = prices["SGOV"].loc[back_in] / prices["SGOV"].loc[b]
    panicked = at_bottom * cash_growth * index.iloc[-1] / index.loc[back_in]
    return {"value_at_bottom": at_bottom, "stayed": stayed, "panicked": panicked,
            "cost": stayed - panicked, "sold_on": b, "bought_back_on": back_in,
            "as_of": index.index[-1]}


def all_panic_costs(prices, weights, amount, wait_months=12):
    return {name: panic_sell_cost(prices, weights, amount, s, e, wait_months)
            for name, (s, e) in SCENARIOS.items()}


# ---------------------------------------------- 3. Retirement timing (sequence)

def run_withdrawals(returns, amount: float, monthly_withdrawal: float) -> dict:
    """Grow the balance each month, then take the withdrawal."""
    balance = amount
    for month, r in enumerate(returns, start=1):
        balance = balance * (1 + r) - monthly_withdrawal
        if balance <= 0:
            return {"ending": 0.0, "ran_out_month": month}
    return {"ending": balance, "ran_out_month": None}


def sequence_risk(prices: pd.DataFrame, weights: dict, amount: float,
                  start: str = "2007-11-01", years: int = 10,
                  withdrawal_rate: float = 0.05) -> dict:
    """
    Retiree A retires right before the 2008 crash and withdraws a fixed
    amount every month for `years`. Retiree B gets the EXACT same monthly
    returns in reverse order, so the crash comes at the end. Same average
    return, same withdrawals - only the order differs.
    """
    index = portfolio_index(prices, weights)
    monthly = index.resample("ME").last().pct_change().dropna()
    returns = monthly.loc[start:].iloc[: years * 12]
    if len(returns) < years * 12:
        raise ValueError(f"Not enough history for {years} years from {start}")

    withdrawal = amount * withdrawal_rate / 12
    crash_first = run_withdrawals(returns.to_numpy(), amount, withdrawal)
    crash_last = run_withdrawals(returns.to_numpy()[::-1], amount, withdrawal)
    growth = float((1 + returns).prod())
    return {
        "period_start": returns.index[0], "period_end": returns.index[-1],
        "years": years, "yearly_withdrawal": withdrawal * 12,
        "avg_yearly_return": growth ** (1 / years) - 1,   # identical for both
        "crash_first": crash_first, "crash_last": crash_last,
        "difference": crash_last["ending"] - crash_first["ending"],
    }
