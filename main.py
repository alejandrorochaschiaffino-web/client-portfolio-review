"""
Run the tool from the terminal.

    python main.py              -> reviews the three sample clients
    python main.py --interview  -> asks you the questionnaire live
    python main.py --offline    -> skip the live download, use saved prices
"""

import math
import sys
from portfolio_tool.profiles import QUESTIONS, assess
from portfolio_tool.allocation import allocate, stock_share
from portfolio_tool.duration import rate_shock
from portfolio_tool.portfolios import MODEL_PORTFOLIOS
from portfolio_tool.risk import portfolio_stats, run_stress_tests, SCENARIO_NOTES
from portfolio_tool.client_scenarios import all_recoveries, all_panic_costs, sequence_risk
from portfolio_tool.sample_clients import SAMPLE_CLIENTS
from portfolio_tool import data


def money(x):
    """Signed dollars for gains and losses, e.g. -$2,030 or +$450."""
    x = round(x)
    if x == 0:
        return "$0"
    return f"-${abs(x):,}" if x < 0 else f"+${x:,}"


def dollars(x):
    """Plain dollars for balances, e.g. $464,372 (or -$1,234 if negative)."""
    x = round(x)
    return f"-${abs(x):,}" if x < 0 else f"${x:,}"


def show_risk(alloc, prices):
    weights = MODEL_PORTFOLIOS[alloc.profile]

    if prices is not None:
        s = portfolio_stats(prices, weights)
        print(f"History {s['start']:%b %Y} to {s['end']:%b %Y} (rebalanced monthly):")
        print(f"  {'Annualized return (compound)':33}{s['annual_return']:>7.1%}")
        print(f"  {'Volatility (monthly, annualized)':33}{s['volatility']:>7.1%}")
        print(f"  {'Worst fall from a peak':33}{s['max_drawdown']:>7.1%}  "
              f"({money(s['max_drawdown'] * alloc.amount)} on today's amount)")
        print()
        print("Crisis stress tests (invested at the market peak, measured at the bottom):")
        recoveries = all_recoveries(prices, weights)
        for name, r in run_stress_tests(prices, weights, alloc.amount).items():
            print(f"  {name:24} {r['return']:>7.1%}  {money(r['dollar_change']):>12}")
            print(f"    {SCENARIO_NOTES[name]}")
            rec = recoveries[name]
            if rec["recovered"]:
                print(f"    Back to even: {rec['recovery_date']:%b %Y}, "
                      f"{rec['months_total']:.0f} months after the peak "
                      f"({rec['months_from_bottom']:.0f} after the bottom)")
            else:
                print(f"    Not back to even yet ({rec['still_down']:.1%} today)")
        print()

        print("Cost of panic-selling (sold at the bottom, bought back 1 year later):")
        for name, r in all_panic_costs(prices, weights, alloc.amount).items():
            verdict = (f"cost of panicking {dollars(r['cost'])}" if r["cost"] >= 0
                       else f"panicking came out ahead by {dollars(-r['cost'])}")
            print(f"  {name:24} stayed invested {dollars(r['stayed']):>10}   "
                  f"panic-sold {dollars(r['panicked']):>10}   {verdict}")
        print(f"  (values as of {r['as_of']:%b %d, %Y})")
        print()

        s = sequence_risk(prices, weights, alloc.amount)
        print(f"Retirement timing risk: withdrawing {dollars(s['yearly_withdrawal'])}/year "
              f"for {s['years']} years ({s['period_start']:%b %Y} to {s['period_end']:%b %Y}):")
        for label, key in (("Crash at the START (retired in late 2007)", "crash_first"),
                           ("Same returns, crash at the END", "crash_last")):
            out = s[key]
            ending = ("ran out of money in month " + str(out["ran_out_month"])
                      if out["ran_out_month"] else dollars(out["ending"]) + " left")
            print(f"  {label:42} {ending}")
        first, last = s["crash_first"], s["crash_last"]
        if first["ran_out_month"] and last["ran_out_month"]:
            print(f"  Both ran out of money; the crash-first retiree ran out "
                  f"{last['ran_out_month'] - first['ran_out_month']} months sooner.")
        else:
            print(f"  Same {s['annualized_return']:.1%} annualized return; "
                  f"timing alone made a {dollars(abs(s['difference']))} difference.")
        print()

    print("Interest-rate shock on bonds and cash (duration x rate change):")
    for change in (0.01, 0.02, -0.01):
        shock = rate_shock(alloc, change)
        print(f"  Rates {change:+.0%}:  {money(shock['total_dollar_change']):>10}  "
              f"({shock['pct_of_portfolio']:+.1%} of the portfolio)")
    print()


def show_review(name, situation, amount, answers, prices):
    result = assess(answers)
    alloc = allocate(result.profile, amount)

    print("=" * 66)
    print(f"Client:    {name}")
    print(f"Situation: {situation}")
    print(f"Investing: ${amount:,.0f}")
    print("-" * 66)
    print(f"Risk score: {result.score}/28  ->  Profile: {result.profile}")
    print(f"Why: {result.reason}")
    print(f"Portfolio: {alloc.description}")
    print(f"Stocks: {stock_share(alloc):.0%} of the portfolio")
    print()
    print(f"  {'Fund':6} {'Asset class':22} {'Weight':>7} {'Dollars':>12}")
    for h in alloc.holdings:
        print(f"  {h.ticker:6} {h.asset_class:22} {h.weight:>7.0%} {h.dollars:>12,.0f}")
    print()
    show_risk(alloc, prices)


def get_prices():
    try:
        prices, source = data.load_prices(live="--offline" not in sys.argv)
        print(f"Market data: {source}\n")
        return prices
    except Exception as e:      # missing or damaged data: still show what we can
        print(f"Market data unavailable ({e}). Showing rate shocks only.\n")
        return None


def interview(prices):
    print("Answer each question with 1, 2, 3 or 4.\n")
    answers = {}
    for q in QUESTIONS:
        print(q["text"])
        for i, a in enumerate(q["answers"], start=1):
            print(f"  {i}. {a}")
        while True:
            choice = input("> ").strip()
            if choice in ("1", "2", "3", "4"):
                answers[q["id"]] = int(choice)
                break
            print("Please type 1, 2, 3 or 4.")
        print()
    name = input("Client name: ").strip() or "New client"
    while True:
        raw = input("Amount to invest ($): ").replace(",", "").replace("$", "").strip()
        try:
            amount = float(raw)
            if math.isfinite(amount) and amount > 0:
                break
        except ValueError:
            pass
        print("Please enter a dollar amount greater than 0, like 50000.")
    show_review(name, "Live interview", amount, answers, prices)


if __name__ == "__main__":
    prices = get_prices()
    if "--interview" in sys.argv:
        interview(prices)
    else:
        for c in SAMPLE_CLIENTS:
            show_review(c["name"], c["situation"], c["amount"], c["answers"], prices)
