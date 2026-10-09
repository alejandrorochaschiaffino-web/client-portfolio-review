"""
One function that runs every analysis for a client and returns the results
as plain data. The terminal demo, the web app and the client report all
read from this, so they can never disagree with each other.
"""

from .allocation import allocate, stock_share
from .client_scenarios import all_panic_costs, all_recoveries, sequence_risk
from .duration import rate_shock
from .portfolios import MODEL_PORTFOLIOS
from .profiles import assess
from .risk import portfolio_stats, run_stress_tests


def build_review(name: str, answers: dict, amount: float, prices=None) -> dict:
    result = assess(answers)
    alloc = allocate(result.profile, amount)
    weights = MODEL_PORTFOLIOS[result.profile]

    review = {
        "name": name or "Client",
        "amount": amount,
        "answers": dict(answers),
        "score": result.score,
        "score_profile": result.score_profile,
        "profile": result.profile,
        "capped": result.capped,
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
    })
    return review
