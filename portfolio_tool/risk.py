"""
Risk analytics on real price history.

Everything here is measured on ONE daily portfolio value series: $1
invested, rebalanced back to the target weights on the first trading day of
every month. Using a single series keeps all the numbers consistent with
each other (the worst fall, each crisis loss, recovery times, etc.).

- Long-run stats: annualized (compound) return, volatility of monthly
  returns, and maximum drawdown (worst peak-to-bottom fall, daily).
- Stress tests: what the portfolio did in three real crises, from the
  market peak to the market bottom.
"""

import math
import numpy as np
import pandas as pd

# Market peak -> bottom for each crisis (S&P 500 dates).
SCENARIOS = {
    "2008 Financial Crisis": ("2007-10-09", "2009-03-09"),
    "2020 COVID Crash": ("2020-02-19", "2020-03-23"),
    "2022 Rate Shock": ("2022-01-03", "2022-10-12"),
}

SCENARIO_NOTES = {
    "2008 Financial Crisis": "Banks failed and stocks fell by about half; high-quality bonds held up.",
    "2020 COVID Crash": "The fastest crash on record, over about a month, followed by a quick recovery.",
    "2022 Rate Shock": "Rates rose fast to fight inflation, so stocks AND bonds fell together.",
}


def max_drawdown(values: pd.Series) -> float:
    """Worst fall from a previous high, as a negative fraction (e.g. -0.35)."""
    running_peak = values.cummax()
    return float((values / running_peak - 1).min())


def portfolio_index(prices: pd.DataFrame, weights: dict,
                    start=None, end=None) -> pd.Series:
    """
    Daily value of $1 invested at `start`, rebalanced back to the target
    weights on the first trading day of every month (at that day's close).
    """
    cols = [t for t, w in weights.items() if w > 0]
    target = np.array([weights[t] for t in cols])
    px = prices.loc[start:end, cols]
    arr = px.to_numpy()
    months = px.index.to_period("M")
    values = np.empty(len(px))
    value, shares = 1.0, None
    for i in range(len(px)):
        if shares is None or months[i] != months[i - 1]:
            if shares is not None:
                value = float(shares @ arr[i])      # value before rebalancing
            shares = target * value / arr[i]        # rebalance to target
        values[i] = float(shares @ arr[i])
    return pd.Series(values, index=px.index)


def month_end_values(index: pd.Series) -> pd.Series:
    """
    Month-end values, starting with the very first value so the first
    month counts, and dropping a final month that isn't finished yet.
    """
    monthly = index.resample("ME").last()
    last = index.index[-1]
    if last < last + pd.offsets.BMonthEnd(0):           # month still in progress
        monthly = monthly.iloc[:-1]
    first_month = index.index.to_period("M") == index.index[0].to_period("M")
    if first_month.sum() > 1:                           # start isn't already a month-end
        start = pd.Series([index.iloc[0]], index=[index.index[0]])
        monthly = pd.concat([start, monthly])
    return monthly


def portfolio_stats(prices: pd.DataFrame, weights: dict) -> dict:
    """Annualized return, volatility of monthly returns, and max drawdown."""
    index = portfolio_index(prices, weights)
    start, end = index.index[0], index.index[-1]
    years = (end - start).days / 365.25
    monthly = month_end_values(index).pct_change().dropna()
    return {
        "annual_return": float(index.iloc[-1] ** (1 / years) - 1),   # compound (CAGR)
        "volatility": float(monthly.std() * math.sqrt(12)),
        "max_drawdown": max_drawdown(index),        # daily, catches the true bottom
        "start": start, "end": end, "years": years,
    }


def _nearest(prices, date) -> pd.Timestamp:
    """First trading day on or after `date`. Refuses dates outside the data."""
    ts = pd.Timestamp(date)
    if ts < prices.index[0] or ts > prices.index[-1]:
        raise ValueError(f"{date} is outside the price history "
                         f"({prices.index[0]:%Y-%m-%d} to {prices.index[-1]:%Y-%m-%d})")
    return prices.index[prices.index.searchsorted(ts)]


def stress_test(prices: pd.DataFrame, weights: dict, amount: float,
                start: str, end: str, index: pd.Series = None) -> dict:
    """Invested at `start` (the peak), measured at `end` (the bottom)."""
    if index is None:
        index = portfolio_index(prices, weights)
    s, e = _nearest(index, start), _nearest(index, end)
    path = index.loc[s:e] / index.loc[s]
    ret = float(path.iloc[-1] - 1)
    return {"start": s, "end": e, "return": ret,
            "dollar_change": round(amount * ret, 2),
            "worst_drop": max_drawdown(path)}


def run_stress_tests(prices: pd.DataFrame, weights: dict, amount: float) -> dict:
    index = portfolio_index(prices, weights)
    return {name: stress_test(prices, weights, amount, s, e, index)
            for name, (s, e) in SCENARIOS.items()}
