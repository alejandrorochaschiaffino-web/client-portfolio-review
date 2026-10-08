"""
Run the tool from the terminal.

    python main.py            -> shows the three sample clients
    python main.py --interview -> asks you the questionnaire live
"""

import sys
from portfolio_tool.profiles import QUESTIONS, assess
from portfolio_tool.allocation import allocate, stock_share
from portfolio_tool.sample_clients import SAMPLE_CLIENTS


def show_review(name, situation, amount, answers):
    result = assess(answers)
    alloc = allocate(result.profile, amount)

    print("=" * 64)
    print(f"Client:   {name}")
    print(f"Situation: {situation}")
    print(f"Investing: ${amount:,.0f}")
    print("-" * 64)
    print(f"Risk score: {result.score}/28  ->  Profile: {result.profile}")
    print(f"Why: {result.reason}")
    print(f"Portfolio: {alloc.description}")
    print(f"Stocks: {stock_share(alloc):.0%} of the portfolio")
    print()
    print(f"  {'Fund':6} {'Asset class':22} {'Weight':>7} {'Dollars':>12}")
    for h in alloc.holdings:
        print(f"  {h.ticker:6} {h.asset_class:22} {h.weight:>7.0%} {h.dollars:>12,.0f}")
    print()


def interview():
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
    show_review(name, "Live interview", amount, answers)


if __name__ == "__main__":
    if "--interview" in sys.argv:
        interview()
    else:
        for c in SAMPLE_CLIENTS:
            show_review(c["name"], c["situation"], c["amount"], c["answers"])
