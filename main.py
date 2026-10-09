"""
Run the tool from the terminal.

    python main.py              -> reviews the three sample clients
    python main.py --interview  -> asks you the questionnaire live
    python main.py --offline    -> skip the live download, use saved prices
"""

import sys
from portfolio_tool.profiles import QUESTIONS, assess
from portfolio_tool.allocation import allocate, stock_share
from portfolio_tool.duration import rate_shock
from portfolio_tool.portfolios import MODEL_PORTFOLIOS
from portfolio_tool.risk import portfolio_stats, run_stress_tests, SCENARIO_NOTES
from portfolio_tool.sample_clients import SAMPLE_CLIENTS
from portfolio_tool import data


def money(x):
    return f"-${abs(x):,.0f}" if x < 0 else f"+${x:,.0f}"


def show_risk(alloc, prices):
    weights = MODEL_PORTFOLIOS[alloc.profile]

    if prices is not None:
        s = portfolio_stats(prices, weights)
        print(f"History {s['start']:%Y}-{s['end']:%Y} (rebalanced monthly):")
        print(f"  Average yearly return  {s['annual_return']:>7.1%}")
        print(f"  Volatility             {s['volatility']:>7.1%}")
        print(f"  Worst fall from a peak {s['max_drawdown']:>7.1%}  "
              f"({money(s['max_drawdown'] * alloc.amount)} on today's amount)")
        print()
        print("Crisis stress tests (bought at the peak, held to the bottom):")
        for name, r in run_stress_tests(prices, weights, alloc.amount).items():
            print(f"  {name:24} {r['return']:>7.1%}  {money(r['dollar_change']):>12}")
            print(f"    {SCENARIO_NOTES[name]}")
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
    except FileNotFoundError as e:
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
    amount = float(input("Amount to invest ($): ").replace(",", "").replace("$", ""))
    show_review(name, "Live interview", amount, answers, prices)


if __name__ == "__main__":
    prices = get_prices()
    if "--interview" in sys.argv:
        interview(prices)
    else:
        for c in SAMPLE_CLIENTS:
            show_review(c["name"], c["situation"], c["amount"], c["answers"], prices)
