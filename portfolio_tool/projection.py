"""
Goal projection: how likely is the client to reach a dollar goal?

Method (a "block bootstrap" Monte Carlo):
1. Take the portfolio's real monthly returns since 2007 (the same
   monthly-rebalanced series every other number in the tool uses).
2. Build thousands of possible futures by stitching together random
   12-month stretches of that history. Keeping whole years together keeps
   real behavior intact: crashes cluster, recoveries follow them.
3. Grow the starting amount through each future, adding the monthly
   savings at the end of every month, and count how often the goal is met.

Because savings enter every future linearly, each simulated future can be
summarized by two numbers:
    ending balance = amount x G  +  monthly savings x A
G is the growth of $1 invested at the start, and A is what $1 saved every
month grows to. That makes "what if they saved $X more?" exact and instant,
with no need to re-run the simulation.

Figures are in future (nominal) dollars, before fees, taxes and inflation.
"""

from __future__ import annotations

import numpy as np

from .risk import month_end_values, portfolio_index

PERCENTILES = (10, 25, 50, 75, 90)
TARGET_ODDS = 0.80          # the "comfortable" probability used for advice


def monthly_returns(prices, weights: dict) -> np.ndarray:
    """Real monthly returns of the monthly-rebalanced portfolio (complete months)."""
    return month_end_values(portfolio_index(prices, weights)).pct_change().dropna().to_numpy()


def bootstrap_returns(history: np.ndarray, months: int, n_paths: int,
                      block: int = 12, seed: int = 7) -> np.ndarray:
    """
    (n_paths x months) matrix of simulated monthly returns, made of random
    `block`-month stretches of `history`. Stretches wrap around the end of the
    history (a "circular" block bootstrap) so every month is equally likely.
    """
    history = np.asarray(history, dtype=float)
    if history.ndim != 1 or len(history) < block:
        raise ValueError("need at least one full block of monthly history")
    if months < 1 or n_paths < 1:
        raise ValueError("months and n_paths must be positive")
    rng = np.random.default_rng(seed)
    n_blocks = -(-months // block)                          # ceiling division
    starts = rng.integers(0, len(history), size=(n_paths, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)) % len(history)
    return history[idx.reshape(n_paths, n_blocks * block)[:, :months]]


def growth_factors(returns: np.ndarray) -> tuple:
    """
    Per simulated future: G = growth of $1 invested at the start, and
    A = value at the end of $1 saved at the end of every month.
    """
    growth = 1 + returns
    G = growth.prod(axis=1)
    # $1 saved at the end of month m grows through months m+1..end.
    later = np.cumprod(growth[:, ::-1], axis=1)[:, ::-1]    # growth from month m to the end
    A = later[:, 1:].sum(axis=1) + 1.0                      # last deposit doesn't grow
    return G, A


def project(history: np.ndarray, amount: float, monthly: float, years: int,
            goal: float, n_paths: int = 10_000, seed: int = 7) -> dict:
    """Odds of reaching `goal` in `years`, plus the fan of outcomes for a chart."""
    if not (amount > 0 and np.isfinite(amount)):
        raise ValueError("amount must be a positive number")
    if monthly < 0 or not np.isfinite(monthly):
        raise ValueError("monthly savings can't be negative")
    if goal <= 0 or not np.isfinite(goal):
        raise ValueError("goal must be a positive number")
    if not 1 <= years <= 50:
        raise ValueError("years must be between 1 and 50")
    months = int(round(years * 12))
    returns = bootstrap_returns(history, months, n_paths, seed=seed)

    # Month-by-month balances, kept only as percentiles (the fan chart).
    balance = np.full(n_paths, float(amount))
    bands = {p: [float(amount)] for p in PERCENTILES}
    for m in range(months):
        balance = balance * (1 + returns[:, m]) + monthly
        for p, v in zip(PERCENTILES, np.percentile(balance, PERCENTILES)):
            bands[p].append(float(v))

    G, A = growth_factors(returns)
    ending = amount * G + monthly * A                       # equals `balance` (tested)
    needed = np.maximum(0.0, (goal - amount * G) / A)       # savings each future needs
    required = float(np.quantile(needed, TARGET_ODDS))      # met in 80% of futures

    longer = bootstrap_returns(history, months + 24, n_paths, seed=seed)
    G2, A2 = growth_factors(longer)

    def odds(extra=0.0):
        return float(np.mean(ending + extra * A >= goal))

    return {
        "amount": float(amount), "monthly": float(monthly), "years": years,
        "goal": float(goal), "n_paths": n_paths, "months": months,
        "probability": odds(),
        "contributed": float(amount + monthly * months),
        "ending": {p: float(v) for p, v in zip(PERCENTILES, np.percentile(ending, PERCENTILES))},
        "bands": bands,
        "required_monthly": required,           # total monthly savings for 80% odds
        "levers": {
            "plus_100": odds(100), "plus_250": odds(250), "plus_500": odds(500),
            "plus_2_years": float(np.mean(amount * G2 + monthly * A2 >= goal)),
        },
    }


def chart_floor(result: dict) -> float:
    """
    Bottom of the y-axis for the fan chart: $0 for long goals, but close to
    the data for short ones, where starting at $0 would flatten everything.
    """
    low = min(min(result["bands"][10]), result["goal"])
    top = max(max(result["bands"][90]), result["goal"])
    floor = low * 0.9
    return 0.0 if floor < 0.35 * top else floor
