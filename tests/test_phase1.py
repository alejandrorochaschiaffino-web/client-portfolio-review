import pytest
from portfolio_tool.profiles import assess, profile_for_score, score_answers
from portfolio_tool.allocation import allocate, stock_share
from portfolio_tool.portfolios import MODEL_PORTFOLIOS


def answers(points, **overrides):
    base = {q: points for q in ["horizon", "goal", "drop_reaction",
                                "experience", "income", "emergency_fund",
                                "tradeoff"]}
    base.update(overrides)
    return base


def test_score_range():
    assert score_answers(answers(1)) == 7
    assert score_answers(answers(4)) == 28


@pytest.mark.parametrize("score,profile", [
    (7, "Conservative"), (12, "Conservative"),
    (13, "Moderately Conservative"), (17, "Moderately Conservative"),
    (18, "Moderate"), (22, "Moderate"),
    (23, "Growth"), (28, "Growth"),
])
def test_score_bands(score, profile):
    assert profile_for_score(score) == profile


def test_bad_answer_rejected():
    with pytest.raises(ValueError):
        score_answers(answers(5))


def test_short_horizon_caps_profile():
    # Brave answers, but needs the money in < 3 years -> Conservative
    r = assess(answers(4, horizon=1))
    assert r.score_profile == "Growth"
    assert r.profile == "Conservative"
    assert r.capped


def test_medium_horizon_caps_profile():
    r = assess(answers(4, horizon=2))
    assert r.profile == "Moderately Conservative"
    assert r.capped


def test_cap_never_raises_risk():
    # A cautious client with a short horizon stays Conservative, not capped
    r = assess(answers(1))
    assert r.profile == "Conservative"
    assert not r.capped


def test_allocation_dollars_add_up():
    for profile in MODEL_PORTFOLIOS:
        a = allocate(profile, 100_000)
        assert sum(h.dollars for h in a.holdings) == pytest.approx(100_000)


def test_riskier_profiles_hold_more_stock():
    shares = [stock_share(allocate(p, 1000)) for p in
              ["Conservative", "Moderately Conservative", "Moderate", "Growth"]]
    assert shares == sorted(shares)
