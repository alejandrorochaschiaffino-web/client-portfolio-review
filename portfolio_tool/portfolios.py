"""
Model portfolios: one mix of low-cost index ETFs per risk profile.

The idea: riskier profiles hold more stocks (higher long-run growth,
bigger swings); safer profiles hold more bonds and cash (smaller swings,
lower growth). Weights in each portfolio add up to 100%.
"""

# The funds we use. All are broad, low-cost index ETFs.
FUNDS = {
    "VTI":  {"name": "Vanguard Total Stock Market ETF",
             "asset_class": "US Stocks"},
    "VXUS": {"name": "Vanguard Total International Stock ETF",
             "asset_class": "International Stocks"},
    "BND":  {"name": "Vanguard Total Bond Market ETF",
             "asset_class": "Bonds"},
    "SGOV": {"name": "iShares 0-3 Month Treasury Bond ETF",
             "asset_class": "Cash & T-Bills"},
}

# Average duration (years) of the bond and cash funds, used for rate shocks.
# BND: 5.8 years per Vanguard's fact sheet as of June 30, 2026.
# SGOV holds 0-3 month T-bills, so its duration is about 0.1 years.
# Stock funds have no bond duration; rate shocks here cover bonds and cash only.
FUND_DURATIONS = {"BND": 5.8, "SGOV": 0.1}

# Weight of each fund, by profile (fractions that sum to 1.0).
MODEL_PORTFOLIOS = {
    "Conservative": {
        "VTI": 0.15, "VXUS": 0.05, "BND": 0.55, "SGOV": 0.25},
    "Moderately Conservative": {
        "VTI": 0.30, "VXUS": 0.10, "BND": 0.45, "SGOV": 0.15},
    "Moderate": {
        "VTI": 0.45, "VXUS": 0.15, "BND": 0.35, "SGOV": 0.05},
    "Growth": {
        "VTI": 0.60, "VXUS": 0.25, "BND": 0.15, "SGOV": 0.00},
}

# One line an advisor could say to a client about each portfolio.
DESCRIPTIONS = {
    "Conservative": "Mostly bonds and cash. Built to protect your money, "
                    "with modest growth.",
    "Moderately Conservative": "More bonds than stocks. Some growth, "
                               "with smaller swings.",
    "Moderate": "A balance of stocks and bonds. Solid long-term growth "
                "with moderate ups and downs.",
    "Growth": "Mostly stocks. Highest long-term growth potential, "
              "but expect big swings along the way.",
}


def check_portfolios():
    """Sanity check: every portfolio's weights must add up to 100%."""
    for profile, weights in MODEL_PORTFOLIOS.items():
        total = sum(weights.values())
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"{profile} weights sum to {total}, not 1.0")
        for ticker in weights:
            if ticker not in FUNDS:
                raise ValueError(f"{profile} uses unknown fund {ticker}")


check_portfolios()
