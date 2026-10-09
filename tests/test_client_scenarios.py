import numpy as np
import pandas as pd
import pytest

from portfolio_tool.client_scenarios import (panic_sell_cost, recovery_time,
                                              run_withdrawals, sequence_risk,
                                              all_recoveries, all_panic_costs)
from portfolio_tool.data import SNAPSHOT, load_snapshot
from portfolio_tool.portfolios import MODEL_PORTFOLIOS
from portfolio_tool.risk import portfolio_index, portfolio_stats


def frame(**cols):
    idx = pd.bdate_range("2020-01-01", periods=len(next(iter(cols.values()))))
    return pd.DataFrame(cols, index=idx, dtype=float)


# ---------- Rebalanced portfolio index ----------

def test_index_single_fund_is_just_its_price():
    p = frame(VTI=[100, 110, 99, 120])
    assert list(portfolio_index(p, {"VTI": 1.0})) == pytest.approx([1, 1.1, 0.99, 1.2])


def test_index_rebalances_at_new_month():
    # A doubles during January, B flat. On Feb 1 the mix is reset to 50/50.
    idx = pd.to_datetime(["2020-01-02", "2020-01-31", "2020-02-03", "2020-02-04"])
    p = pd.DataFrame({"A": [100, 200, 200, 100], "B": [100, 100, 100, 100]}, index=idx, dtype=float)
    v = portfolio_index(p, {"A": 0.5, "B": 0.5})
    assert v.iloc[1] == pytest.approx(1.5)          # 0.5*2 + 0.5*1
    assert v.iloc[2] == pytest.approx(1.5)          # rebalanced, value unchanged
    assert v.iloc[3] == pytest.approx(1.125)        # 0.75 in A halves -> 0.375 + 0.75
    # Without rebalancing it would have been 0.5*1 + 0.5*1 = 1.0


def test_zero_weight_funds_are_ignored():
    p = frame(VTI=[100, 120], SGOV=[100, 100])
    assert portfolio_index(p, {"VTI": 1.0, "SGOV": 0.0}).iloc[-1] == pytest.approx(1.2)


# ---------- 1. Recovery time ----------

def test_recovery_found_after_bottom():
    p = frame(VTI=[100, 70, 50, 80, 100, 120])
    r = recovery_time(p, {"VTI": 1.0}, "2020-01-01", "2020-01-03")
    assert r["recovered"] and r["recovery_date"] == p.index[4]


def test_no_recovery_reports_still_down():
    p = frame(VTI=[100, 60, 50, 70, 90])
    r = recovery_time(p, {"VTI": 1.0}, "2020-01-01", "2020-01-03")
    assert not r["recovered"] and r["months_total"] is None
    assert r["still_down"] == pytest.approx(-0.10)


def test_portfolio_that_never_lost_recovers_immediately():
    p = frame(BND=[100, 101, 102])
    r = recovery_time(p, {"BND": 1.0}, "2020-01-01", "2020-01-02")
    assert r["recovered"] and r["months_from_bottom"] == 0


# ---------- 2. Panic-selling ----------

def test_panic_sell_math():
    days = pd.bdate_range("2020-01-01", "2021-06-30")
    vti = np.full(len(days), 100.0)
    bottom = days.get_loc(pd.Timestamp("2020-03-02"))
    vti[bottom:] = 50.0                         # crash
    back = days.searchsorted(pd.Timestamp("2021-03-02"))
    vti[back:] = 90.0                           # partial recovery by the time they buy back
    vti[-1] = 120.0                             # then a new high
    p = pd.DataFrame({"VTI": vti, "SGOV": 100.0}, index=days)
    r = panic_sell_cost(p, {"VTI": 1.0}, 10_000, "2020-01-01", "2020-03-02", wait_months=12)
    assert r["value_at_bottom"] == pytest.approx(5_000)
    assert r["stayed"] == pytest.approx(12_000)
    assert r["panicked"] == pytest.approx(5_000 * 120 / 90)   # bought back at 90
    assert r["cost"] == pytest.approx(12_000 - 5_000 * 120 / 90)


def test_panic_sell_earns_cash_interest_while_waiting():
    days = pd.bdate_range("2020-01-01", "2021-06-30")
    p = pd.DataFrame({"VTI": 100.0, "SGOV": np.linspace(100, 110, len(days))}, index=days)
    r = panic_sell_cost(p, {"VTI": 1.0}, 1000, "2020-01-01", "2020-03-02")
    assert r["panicked"] > r["stayed"]          # flat stocks: cash wins slightly


# ---------- 3. Retirement timing (sequence of returns) ----------

def test_withdrawals_simple():
    out = run_withdrawals([0.10, 0.10], 1000, 100)
    assert out["ending"] == pytest.approx((1000 * 1.1 - 100) * 1.1 - 100)


def test_running_out_of_money_is_flagged():
    out = run_withdrawals([-0.5, 0.0, 0.0], 1000, 300)
    assert out["ending"] == 0 and out["ran_out_month"] == 2


def test_order_does_not_matter_without_withdrawals():
    rets = [-0.3, 0.1, 0.2, -0.05, 0.15]
    a = run_withdrawals(rets, 1000, 0)["ending"]
    b = run_withdrawals(rets[::-1], 1000, 0)["ending"]
    assert a == pytest.approx(b)


def test_crash_first_hurts_more_with_withdrawals():
    rets = [-0.3, -0.2] + [0.02] * 30
    first = run_withdrawals(rets, 1000, 10)["ending"]
    last = run_withdrawals(rets[::-1], 1000, 10)["ending"]
    assert first < last


# ---------- Real data sanity checks ----------

needs_data = pytest.mark.skipif(not SNAPSHOT.exists(), reason="no price snapshot yet")


@needs_data
def test_index_matches_an_independent_calculation():
    # Rebuild the monthly-rebalanced portfolio a different way: chain the
    # growth from each month's first trading day to the next one.
    prices = load_snapshot()
    for w in MODEL_PORTFOLIOS.values():
        idx = portfolio_index(prices, w)
        firsts = prices.groupby(prices.index.to_period("M")).head(1)
        value, expected = 1.0, [1.0]
        for a, b in zip(firsts.index[:-1], firsts.index[1:]):
            value *= sum(wt * prices.at[b, t] / prices.at[a, t] for t, wt in w.items() if wt > 0)
            expected.append(value)
        assert idx.loc[firsts.index].to_numpy() == pytest.approx(expected, rel=1e-9)


@needs_data
def test_all_crisis_numbers_describe_the_same_portfolio():
    from portfolio_tool.risk import run_stress_tests
    prices = load_snapshot()
    for w in MODEL_PORTFOLIOS.values():
        idx = portfolio_index(prices, w)
        stress = run_stress_tests(prices, w, 100_000)
        rec = all_recoveries(prices, w)
        panic = all_panic_costs(prices, w, 100_000)
        for name in stress:
            peak = stress[name]["start"]
            # bottom value, "stayed invested" value and recovery all follow idx
            assert panic[name]["value_at_bottom"] == pytest.approx(100_000 + stress[name]["dollar_change"], abs=0.01)
            assert panic[name]["stayed"] == pytest.approx(100_000 * idx.iloc[-1] / idx.loc[peak])
            if rec[name]["recovered"]:
                r = rec[name]["recovery_date"]
                assert idx.loc[r] >= idx.loc[peak]
                between = idx.loc[stress[name]["end"]:r].iloc[:-1]
                assert (between < idx.loc[peak]).all()      # first day back, not later


@needs_data
def test_worst_fall_is_at_least_as_bad_as_every_crisis():
    from portfolio_tool.risk import run_stress_tests
    prices = load_snapshot()
    for w in MODEL_PORTFOLIOS.values():
        worst = portfolio_stats(prices, w)["max_drawdown"]
        for r in run_stress_tests(prices, w, 1).values():
            assert worst <= r["return"] + 1e-9


@needs_data
def test_riskier_profiles_rank_correctly():
    prices = load_snapshot()
    order = ["Conservative", "Moderately Conservative", "Moderate", "Growth"]
    stats = [portfolio_stats(prices, MODEL_PORTFOLIOS[p]) for p in order]
    vols = [s["volatility"] for s in stats]
    worst = [s["max_drawdown"] for s in stats]
    assert vols == sorted(vols)
    assert worst == sorted(worst, reverse=True)


def test_broken_snapshot_is_rejected(tmp_path):
    from portfolio_tool.data import load_snapshot as load
    bad = tmp_path / "prices.csv"
    bad.write_text("Date,VTI,VXUS,BND\n2007-06-01,1,2,3\n")      # SGOV missing
    with pytest.raises(RuntimeError):
        load(bad)


def test_interview_handles_bad_amounts():
    import subprocess, sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    answers = "4\n" * 7 + "Test\nfifty\n0\n-5\n$25,000\n"
    out = subprocess.run([sys.executable, "main.py", "--interview", "--offline"],
                         input=answers, capture_output=True, text=True, cwd=root, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.count("Please enter a dollar amount") == 3
    assert "25,000" in out.stdout


@needs_data
def test_2008_recovery_is_slower_for_riskier_portfolios():
    prices = load_snapshot()
    g = all_recoveries(prices, MODEL_PORTFOLIOS["Growth"])["2008 Financial Crisis"]
    c = all_recoveries(prices, MODEL_PORTFOLIOS["Conservative"])["2008 Financial Crisis"]
    assert g["recovered"] and c["recovered"]
    assert 24 < g["months_total"] < 84            # US stocks took about 4-5 years
    assert c["months_total"] < g["months_total"]


@needs_data
def test_panic_sell_bottom_matches_stress_test():
    from portfolio_tool.risk import run_stress_tests
    prices = load_snapshot()
    for w in MODEL_PORTFOLIOS.values():
        stress = run_stress_tests(prices, w, 100_000)
        panic = all_panic_costs(prices, w, 100_000)
        for name in stress:
            assert panic[name]["value_at_bottom"] == pytest.approx(100_000 + stress[name]["dollar_change"], abs=0.01)


@needs_data
def test_panic_selling_2008_cost_money():
    prices = load_snapshot()
    for w in MODEL_PORTFOLIOS.values():
        r = all_panic_costs(prices, w, 100_000)["2008 Financial Crisis"]
        assert r["cost"] > 0 and r["stayed"] > r["panicked"]


@needs_data
def test_sequence_risk_real_history():
    prices = load_snapshot()
    for w in MODEL_PORTFOLIOS.values():
        s = sequence_risk(prices, w, 500_000)
        assert s["crash_first"]["ending"] < s["crash_last"]["ending"]
        no_withdrawals = sequence_risk(prices, w, 500_000, withdrawal_rate=0)
        assert no_withdrawals["difference"] == pytest.approx(0, abs=1e-6)


# ---------- Review follow-ups ----------

def test_month_end_values_include_start_and_drop_unfinished_month():
    from portfolio_tool.risk import month_end_values
    days = pd.bdate_range("2020-01-15", "2020-03-10")       # March unfinished
    m = month_end_values(pd.Series(range(1, len(days) + 1), index=days, dtype=float))
    assert m.index[0] == pd.Timestamp("2020-01-15")          # starting value kept
    assert m.index[-1] == pd.Timestamp("2020-02-29")          # March dropped
    assert len(m) == 3


@needs_data
def test_sequence_risk_refuses_unfinished_months():
    prices = load_snapshot()
    with pytest.raises(ValueError):
        sequence_risk(prices, MODEL_PORTFOLIOS["Growth"], 1000, start="2016-11-01", years=10)


def test_amount_must_be_a_real_number():
    from portfolio_tool.allocation import allocate
    for bad in (float("inf"), float("nan"), 0, -1):
        with pytest.raises(ValueError):
            allocate("Moderate", bad)


def test_interview_rejects_infinity():
    import subprocess, sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    out = subprocess.run([sys.executable, "main.py", "--interview", "--offline"],
                         input="4\n" * 7 + "T\ninf\nnan\n1e400\n5000\n",
                         capture_output=True, text=True, cwd=root, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.count("Please enter a dollar amount") == 3
    for bad in ("$nan", "$inf", "$-nan", "$-inf"):
        assert bad not in out.stdout.lower()
    assert "Investing: $5,000" in out.stdout


def test_money_formatting():
    import main
    assert main.money(-0.3) == "$0"
    assert main.money(-1234.4) == "-$1,234"
    assert main.money(450) == "+$450"
    assert main.dollars(-1234) == "-$1,234"
    assert main.dollars(464372.2) == "$464,372"


def test_duplicate_dates_rejected():
    from portfolio_tool.data import check_prices
    p = frame(VTI=[1, 2], VXUS=[1, 2], BND=[1, 2], SGOV=[1, 2])
    p.index = pd.DatetimeIndex(["2007-01-02", "2007-01-02"])
    with pytest.raises(RuntimeError):
        check_prices(p, must_be_recent=False)


def test_splice_when_proxy_lacks_the_launch_day():
    from portfolio_tool.data import splice
    proxy = pd.Series([10.0, 11.0, 12.0], index=pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"]))
    fund = pd.Series([50.0, 55.0], index=pd.to_datetime(["2020-01-06", "2020-01-07"]))
    out = splice(fund, proxy)
    assert list(out.index) == list(proxy.index) + list(fund.index)   # no day lost
    assert out.loc["2020-01-06"] == 50.0                              # real fund kept
    assert out.iloc[1] / out.iloc[0] == pytest.approx(1.1)            # proxy returns kept


def test_splice_rejects_empty_download():
    from portfolio_tool.data import splice
    with pytest.raises(RuntimeError):
        splice(pd.Series(dtype=float), pd.Series([1.0, 2.0]))


@needs_data
def test_readme_results_table_matches_the_code():
    from pathlib import Path
    from portfolio_tool.risk import run_stress_tests
    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text()
    prices = load_snapshot()
    fmt = lambda x: f"{x:.1%}".replace("-", "−")
    for name, w in MODEL_PORTFOLIOS.items():
        s = portfolio_stats(prices, w)
        crises = [r["return"] for r in run_stress_tests(prices, w, 1).values()]
        row = f"| {name} | " + " | ".join(fmt(x) for x in
              [s["annual_return"], s["volatility"], s["max_drawdown"], *crises]) + " |"
        assert row in readme, f"README row out of date: {row}"
