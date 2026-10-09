import numpy as np
import pandas as pd
import pytest

from portfolio_tool.allocation import allocate
from portfolio_tool.data import splice, SNAPSHOT, load_snapshot
from portfolio_tool.duration import (bond_price, macaulay_duration,
                                     modified_duration, rate_shock)
from portfolio_tool.portfolios import MODEL_PORTFOLIOS
from portfolio_tool.risk import max_drawdown, portfolio_stats, stress_test, run_stress_tests


# ---------- Duration: must match the class Excel sheet ----------

def test_class_example_price_and_duration():
    # Duration Example tab: FV 1000, 5% coupon, 9% YTM, quarterly, 16 periods (4 years)
    assert bond_price(1000, 0.05, 0.09, 4, freq=4) == pytest.approx(866.8737, abs=1e-3)
    assert macaulay_duration(1000, 0.05, 0.09, 4, freq=4) == pytest.approx(3.6174, abs=1e-4)


def test_zero_coupon_duration_equals_maturity():
    assert macaulay_duration(1000, 0.0, 0.05, 10, freq=2) == pytest.approx(10)


def test_modified_duration_predicts_price_change():
    p0 = bond_price(1000, 0.04, 0.05, 10)
    p1 = bond_price(1000, 0.04, 0.0501, 10)  # +1 basis point
    approx = -modified_duration(1000, 0.04, 0.05, 10) * 0.0001
    assert (p1 / p0 - 1) == pytest.approx(approx, rel=0.01)


def test_rate_shock_moderate_100k():
    shock = rate_shock(allocate("Moderate", 100_000), 0.01)
    # BND $35,000 x 5.8 x 1% = -$2,030 ; SGOV $5,000 x 0.1 x 1% = -$5
    assert shock["total_dollar_change"] == pytest.approx(-2035)


def test_rate_cut_helps_bonds():
    assert rate_shock(allocate("Conservative", 10_000), -0.01)["total_dollar_change"] > 0


# ---------- Risk math on made-up prices ----------

def fake_prices():
    days = pd.bdate_range("2007-01-01", "2023-12-29")
    rng = np.random.default_rng(0)
    data = {t: 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, len(days)))
            for t in ["VTI", "VXUS", "BND", "SGOV"]}
    return pd.DataFrame(data, index=days)


def test_max_drawdown():
    assert max_drawdown(pd.Series([100, 120, 60, 90, 130])) == pytest.approx(-0.5)
    assert max_drawdown(pd.Series([1, 2, 3])) == 0


def test_stress_test_buy_and_hold_math():
    days = pd.bdate_range("2020-01-01", periods=3)
    prices = pd.DataFrame({"VTI": [100, 50, 80], "BND": [100, 100, 110]}, index=days)
    r = stress_test(prices, {"VTI": 0.5, "BND": 0.5}, 10_000, "2020-01-01", "2020-01-03")
    assert r["return"] == pytest.approx(-0.05)        # 0.5*0.8 + 0.5*1.1 - 1
    assert r["dollar_change"] == pytest.approx(-500)
    assert r["worst_drop"] == pytest.approx(-0.25)    # day 2: 0.5*0.5 + 0.5*1.0


def test_stats_and_scenarios_run_on_every_portfolio():
    prices = fake_prices()
    for weights in MODEL_PORTFOLIOS.values():
        stats = portfolio_stats(prices, weights)
        assert stats["volatility"] > 0 and stats["max_drawdown"] <= 0
        assert len(run_stress_tests(prices, weights, 1000)) == 3


def test_splice_joins_proxy_history():
    idx = pd.bdate_range("2020-01-01", periods=4)
    proxy = pd.Series([10.0, 11.0, 12.0, 13.0], index=idx)
    fund = pd.Series([50.0, 52.0], index=idx[2:])
    out = splice(fund, proxy)
    assert list(out.index) == list(idx)
    assert out.iloc[2] == 50.0                       # real fund untouched
    assert out.iloc[1] / out.iloc[0] == pytest.approx(11 / 10)  # proxy returns kept


# ---------- Real data checks (run once data/prices.csv exists) ----------

needs_data = pytest.mark.skipif(not SNAPSHOT.exists(), reason="no price snapshot yet")


@needs_data
def test_snapshot_covers_all_crises():
    prices = load_snapshot()
    assert set(["VTI", "VXUS", "BND", "SGOV"]) <= set(prices.columns)
    assert prices.index[0] <= pd.Timestamp("2007-10-09")
    assert prices.index[-1] >= pd.Timestamp("2022-10-12")
    assert not prices.isna().any().any()


@needs_data
def test_growth_falls_more_than_conservative_in_2008():
    prices = load_snapshot()
    g = run_stress_tests(prices, MODEL_PORTFOLIOS["Growth"], 1)["2008 Financial Crisis"]
    c = run_stress_tests(prices, MODEL_PORTFOLIOS["Conservative"], 1)["2008 Financial Crisis"]
    assert g["return"] < c["return"] < 0.05
