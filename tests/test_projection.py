"""Checks the goal projection math against formulas that can be worked out by hand."""

import numpy as np
import pytest

from portfolio_tool.data import SNAPSHOT, load_snapshot
from portfolio_tool.portfolios import MODEL_PORTFOLIOS
from portfolio_tool.projection import (TARGET_ODDS, bootstrap_returns, growth_factors,
                                       monthly_returns, project)

needs_data = pytest.mark.skipif(not SNAPSHOT.exists(), reason="no price snapshot yet")
RNG = np.random.default_rng(0)
HISTORY = RNG.normal(0.006, 0.04, 228)                 # 19 years of made-up monthly returns


def test_constant_returns_match_compound_interest_formulas():
    r, n = 0.005, 120
    returns = np.full((3, n), r)
    G, A = growth_factors(returns)
    assert np.allclose(G, (1 + r) ** n)
    assert np.allclose(A, ((1 + r) ** n - 1) / r)      # future value of an annuity


def test_no_volatility_means_a_certain_outcome():
    flat = np.full(60, 0.005)
    hit = project(flat, 100_000, 500, 10, goal=100_000 * 1.005 ** 120 + 500 * (1.005 ** 120 - 1) / 0.005 - 1)
    miss = project(flat, 100_000, 500, 10, goal=100_000 * 1.005 ** 120 + 500 * (1.005 ** 120 - 1) / 0.005 + 1)
    assert hit["probability"] == 1.0 and miss["probability"] == 0.0


def test_month_by_month_simulation_agrees_with_the_shortcut_formula():
    res = project(HISTORY, 50_000, 300, 15, goal=150_000, n_paths=2_000)
    for p in (10, 50, 90):                              # same futures, two computations
        assert res["bands"][p][-1] == pytest.approx(res["ending"][p], rel=1e-9)
    assert len(res["bands"][50]) == 15 * 12 + 1


def test_bootstrap_keeps_whole_years_of_history_together():
    history = np.arange(100) / 1000                      # each month's "return" is its position
    sims = bootstrap_returns(history, months=36, n_paths=50, block=12)
    for row in sims:
        for start in range(0, 36, 12):
            block = np.round(row[start:start + 12] * 1000).astype(int)
            assert all((b - a) % 100 == 1 for a, b in zip(block, block[1:]))


def test_bootstrap_draws_from_the_whole_history_evenly():
    sims = bootstrap_returns(HISTORY, months=240, n_paths=4_000)
    assert sims.mean() == pytest.approx(HISTORY.mean(), abs=0.0005)
    assert sims.std() == pytest.approx(HISTORY.std(), rel=0.02)


def test_same_seed_same_answer():
    a = project(HISTORY, 80_000, 200, 12, goal=200_000, n_paths=3_000)
    b = project(HISTORY, 80_000, 200, 12, goal=200_000, n_paths=3_000)
    assert a["probability"] == b["probability"] and a["ending"] == b["ending"]


def test_more_savings_or_more_time_never_lowers_the_odds():
    res = project(HISTORY, 80_000, 200, 12, goal=250_000, n_paths=3_000)
    lev = res["levers"]
    assert res["probability"] <= lev["plus_100"] <= lev["plus_250"] <= lev["plus_500"]
    assert lev["plus_2_years"] >= res["probability"]
    assert 0 < res["probability"] < 1


def test_required_savings_really_gives_80_percent_odds():
    res = project(HISTORY, 80_000, 200, 12, goal=250_000, n_paths=5_000)
    need = res["required_monthly"]
    assert need > 200                                    # current savings fall short
    again = project(HISTORY, 80_000, need + 0.01, 12, goal=250_000, n_paths=5_000)
    assert again["probability"] >= TARGET_ODDS
    short = project(HISTORY, 80_000, need * 0.9, 12, goal=250_000, n_paths=5_000)
    assert short["probability"] < TARGET_ODDS


def test_easy_goal_needs_no_savings():
    res = project(HISTORY, 100_000, 0, 20, goal=50_000, n_paths=2_000)
    assert res["required_monthly"] == 0 and res["probability"] > 0.95


def test_percentiles_are_in_order():
    res = project(HISTORY, 60_000, 250, 25, goal=400_000, n_paths=3_000)
    e = res["ending"]
    assert e[10] <= e[25] <= e[50] <= e[75] <= e[90]
    for m in range(0, res["months"] + 1, 30):
        assert res["bands"][10][m] <= res["bands"][50][m] <= res["bands"][90][m]


@pytest.mark.parametrize("kwargs", [
    dict(amount=0), dict(amount=float("inf")), dict(monthly=-1), dict(goal=0),
    dict(years=0), dict(years=51), dict(monthly=float("nan")),
])
def test_bad_inputs_are_rejected(kwargs):
    args = dict(history=HISTORY, amount=10_000, monthly=100, years=10, goal=50_000)
    args.update(kwargs)
    with pytest.raises(ValueError):
        project(**args)


@needs_data
def test_real_portfolios_rank_sensibly_on_a_long_goal():
    prices = load_snapshot()
    odds = {}
    for name in ("Conservative", "Growth"):
        hist = monthly_returns(prices, MODEL_PORTFOLIOS[name])
        assert len(hist) > 200                           # 2007 to today
        odds[name] = project(hist, 50_000, 500, 30, goal=800_000, n_paths=4_000)["probability"]
    assert odds["Growth"] > odds["Conservative"]         # more stock wins over 30 years
