"""
Risk analytics on real price history.

- Long-run stats: yearly return, volatility (how much returns swing),
  and maximum drawdown (worst peak-to-bottom fall), using monthly
  rebalancing back to the target weights.
- Stress tests: what the portfolio would have done in three real crises,
  buying at the peak and holding to the bottom.
"""

import math
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


def portfolio_stats(prices: pd.DataFrame, weights: dict) -> dict:
    """Annual return, volatility and max drawdown with monthly rebalancing."""
    monthly = prices[list(weights)].resample("ME").last().pct_change().dropna()
    port = sum(monthly[t] * w for t, w in weights.items())
    growth = (1 + port).cumprod()
    years = len(port) / 12
    return {
        "annual_return": float(growth.iloc[-1] ** (1 / years) - 1),
        "volatility": float(port.std() * math.sqrt(12)),
        "max_drawdown": max_drawdown(pd.concat([pd.Series([1.0]), growth])),
        "start": port.index[0], "end": port.index[-1], "years": years,
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
