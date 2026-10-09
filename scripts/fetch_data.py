"""
Download fresh ETF prices and save them to data/prices.csv.

Run it yourself (`python scripts/fetch_data.py`) or let the GitHub Action
"Update market data" run it on GitHub's servers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from portfolio_tool.data import fetch_prices, SNAPSHOT  # noqa: E402

prices = fetch_prices()
SNAPSHOT.parent.mkdir(exist_ok=True)
prices.round(4).to_csv(SNAPSHOT)
print(f"Saved {len(prices):,} days of prices "
      f"({prices.index[0]:%Y-%m-%d} to {prices.index[-1]:%Y-%m-%d}) to {SNAPSHOT}")
