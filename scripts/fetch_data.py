"""
Download fresh ETF prices and save them to data/prices.csv.

Run it yourself (`python scripts/fetch_data.py`) or let the GitHub Action
"Update market data" run it on GitHub's servers.

The file is only rewritten when there is a new trading day or prices
really changed, so tiny rounding noise from Yahoo doesn't create commits.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from portfolio_tool.data import fetch_prices, load_snapshot, SNAPSHOT  # noqa: E402

prices = fetch_prices().round(4)

if SNAPSHOT.exists():
    old = load_snapshot()
    same_days = old.index.equals(prices.index)
    if same_days and ((prices - old[prices.columns]).abs() / old[prices.columns]).max().max() < 1e-4:
        print(f"No new data (still through {prices.index[-1]:%Y-%m-%d}); snapshot unchanged.")
        sys.exit(0)

SNAPSHOT.parent.mkdir(exist_ok=True)
prices.to_csv(SNAPSHOT)
print(f"Saved {len(prices):,} days of prices "
      f"({prices.index[0]:%Y-%m-%d} to {prices.index[-1]:%Y-%m-%d}) to {SNAPSHOT}")
