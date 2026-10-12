import pytest

from portfolio_tool.sample_clients import SAMPLE_CLIENTS
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


def test_selling_everything_after_a_drop_caps_risk():
    from portfolio_tool.profiles import assess
    brave_but_sells = dict(horizon=4, goal=4, drop_reaction=1, experience=4, income=4,
                           emergency_fund=4, tradeoff=4)
    r = assess(brave_but_sells)
    assert r.score_profile == "Growth" and r.profile == "Moderately Conservative"
    assert r.capped and r.cap_reason == "losses"


def test_goal_years_cap_like_the_horizon_question():
    from portfolio_tool.profiles import assess, horizon_bucket
    assert [horizon_bucket(y) for y in (1, 2, 3, 5, 6, 10, 11, 30)] == [1, 1, 2, 2, 3, 3, 4, 4]
    growth = dict(horizon=4, goal=4, drop_reaction=4, experience=4, income=4, emergency_fund=4, tradeoff=4)
    assert assess(growth).profile == "Growth"
    assert assess(growth, goal_years=2).profile == "Conservative"
    assert assess(growth, goal_years=4).profile == "Moderately Conservative"
    assert assess(growth, goal_years=20).profile == "Growth"


def test_strictest_cap_wins_and_samples_are_unchanged():
    from portfolio_tool.profiles import assess
    both = dict(horizon=1, goal=4, drop_reaction=1, experience=4, income=4, emergency_fund=4, tradeoff=4)
    assert assess(both).profile == "Conservative"          # horizon cap is stricter than the loss cap
    expected = {"Jordan Lee": "Growth", "Carlos and Ana Rivera": "Moderate", "Maria Gonzalez": "Conservative"}
    for c in SAMPLE_CLIENTS:
        assert assess(c["answers"], goal_years=c["goal"]["years"]).profile == expected[c["name"]]
