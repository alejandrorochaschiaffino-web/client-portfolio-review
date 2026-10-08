"""
Allocation engine: turn a profile + an investment amount into
dollars per fund and a stocks/bonds/cash summary.
"""

from dataclasses import dataclass
from .portfolios import FUNDS, MODEL_PORTFOLIOS, DESCRIPTIONS


@dataclass
class Holding:
    ticker: str
    name: str
    asset_class: str
    weight: float      # fraction of the portfolio, e.g. 0.45
    dollars: float     # weight x amount invested


@dataclass
class Allocation:
    profile: str
    amount: float
    description: str
    holdings: list           # list of Holding
    by_asset_class: dict     # asset class -> fraction


def allocate(profile: str, amount: float) -> Allocation:
    if profile not in MODEL_PORTFOLIOS:
        raise ValueError(f"Unknown profile: {profile}")
    if amount <= 0:
        raise ValueError("Amount must be positive")

    holdings = []
    by_class = {}
    for ticker, weight in MODEL_PORTFOLIOS[profile].items():
        if weight == 0:
            continue
        fund = FUNDS[ticker]
        holdings.append(Holding(ticker, fund["name"], fund["asset_class"],
                                weight, round(weight * amount, 2)))
        by_class[fund["asset_class"]] = by_class.get(fund["asset_class"], 0) + weight

    return Allocation(profile, amount, DESCRIPTIONS[profile], holdings, by_class)


def stock_share(alloc: Allocation) -> float:
    """Fraction of the portfolio in stocks (US + international)."""
    return sum(w for cls, w in alloc.by_asset_class.items() if "Stocks" in cls)
