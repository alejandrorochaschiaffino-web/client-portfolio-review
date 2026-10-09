"""
Risk analytics on real price history.

- Long-run stats: yearly return, volatility (how much returns swing),
  and maximum drawdown (worst peak-to-bottom fall), using monthly
  rebalancing back to the target weights.
- Stress tests: what the portfolio would have done in three real crises,
  buying at the peak and holding to the bottom.
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
    weights on the first trading day of every month.
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


def portfolio_stats(prices: pd.DataFrame, weights: dict) -> dict:
    """
    Annual return, volatility and max drawdown, all from the same daily
    portfolio value (rebalanced monthly), so the numbers agree with each other.
    """
    index = portfolio_index(prices, weights)
    start, end = index.index[0], index.index[-1]
    years = (end - start).days / 365.25
    month_ends = pd.concat([pd.Series([1.0], index=[start]),
                            index.resample("ME").last()])
    monthly = month_ends.pct_change().dropna()
    return {
        "annual_return": float(index.iloc[-1] ** (1 / years) - 1),
        "volatility": float(monthly.std() * math.sqrt(12)),
        "max_drawdown": max_drawdown(index),        # daily, catches the true bottom
        "start": start, "end": end, "years": years,
    }


def _nearest(prices: pd.DataFrame, date: str) -> pd.Timestamp:
    """First trading day on or after `date`. Refuses dates outside the data."""
    ts = pd.Timestamp(date)
    if ts < prices.index[0] or ts > prices.index[-1]:
        raise ValueError(f"{date} is outside the price history "
                         f"({prices.index[0]:%Y-%m-%d} to {prices.index[-1]:%Y-%m-%d})")
    return prices.index[prices.index.searchsorted(ts)]


def stress_test(prices: pd.DataFrame, weights: dict, amount: float,
                start: str, end: str) -> dict:
    """Buy at `start`, hold to `end`. Returns % and dollar results."""
    s, e = _nearest(prices, start), _nearest(prices, end)
    window = prices.loc[s:e, list(weights)]
    value = sum(window[t] / window[t].iloc[0] * w for t, w in weights.items())
    ret = float(value.iloc[-1] - 1)
    return {"start": s, "end": e, "return": ret,
            "dollar_change": round(amount * ret, 2),
            "worst_drop": max_drawdown(value)}


def run_stress_tests(prices: pd.DataFrame, weights: dict, amount: float) -> dict:
    return {name: stress_test(prices, weights, amount, s, e)
            for name, (s, e) in SCENARIOS.items()}
