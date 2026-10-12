"""
One function that runs every analysis for a client and returns the results
as plain data. The web app, the client letter and the PDF report all read
from this, so they can never disagree with each other.
"""

from __future__ import annotations

from .allocation import allocate, stock_share
from .client_scenarios import all_panic_costs, all_recoveries, sequence_risk
from .duration import rate_shock
from .portfolios import MODEL_PORTFOLIOS
from .profiles import assess
from .projection import monthly_returns, project
from .risk import portfolio_stats, run_stress_tests


def build_review(name: str, answers: dict, amount: float, prices=None, goal: dict | None = None) -> dict:
    """
    goal (optional): {"target": dollars, "years": n, "monthly": savings per month}
    for the goal projection. Needs price history, like the other analyses.
    """
    result = assess(answers, goal_years=goal["years"] if goal else None)
    alloc = allocate(result.profile, amount)
    weights = MODEL_PORTFOLIOS[result.profile]

    review = {
        "name": (name or "").strip(),       # blank -> each language's own word for "client"
        "amount": amount,
        "answers": dict(answers),
        "score": result.score,
        "score_profile": result.score_profile,
        "profile": result.profile,
        "capped": result.capped,
        "cap_reason": result.cap_reason,
        "goal_years": goal["years"] if goal else None,
        "stock_share": stock_share(alloc),
        "holdings": [{"ticker": h.ticker, "asset_class": h.asset_class,
                      "weight": h.weight, "dollars": h.dollars} for h in alloc.holdings],
        "rate_shocks": {change: rate_shock(alloc, change) for change in (0.01, 0.02, -0.01)},
        "has_history": prices is not None,
    }
    if prices is None:
        return review

    stats = portfolio_stats(prices, weights)
    stress = run_stress_tests(prices, weights, amount)
    recoveries = all_recoveries(prices, weights)
    panic = all_panic_costs(prices, weights, amount)
    review.update({
        "data_through": prices.index[-1],
        "stats": stats,
        "crises": [{
            "name": name_,
            "return": stress[name_]["return"],
            "dollar_change": stress[name_]["dollar_change"],
            "peak": stress[name_]["start"], "bottom": stress[name_]["end"],
            **recoveries[name_],
            "stayed": panic[name_]["stayed"],
            "panicked": panic[name_]["panicked"],
            "panic_cost": panic[name_]["cost"],
        } for name_ in stress],
        "sequence": sequence_risk(prices, weights, amount),
        "goal": (project(monthly_returns(prices, weights), amount, goal["monthly"],
                         goal["years"], goal["target"]) if goal else None),
    })
    return review
