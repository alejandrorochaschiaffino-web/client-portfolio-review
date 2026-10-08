"""
Client intake: a short risk questionnaire that turns a client's answers
into a risk profile (Conservative -> Growth).

How it works, in plain English:
1. Each question has 4 answers worth 1 to 4 points.
2. Add up the points (7 questions, so the total runs from 7 to 28).
3. The total picks a profile.
4. Suitability check: if the client needs the money soon, we cap how
   risky the profile can be, no matter how brave their answers were.
   (This mirrors the FINRA suitability idea: risk must fit the client's
   situation, not just their attitude.)
"""

from dataclasses import dataclass

# Profiles, from least to most risky. Order matters: we compare positions.
PROFILES = ["Conservative", "Moderately Conservative", "Moderate", "Growth"]

# Each question: an id, the question text, and 4 answers worth 1-4 points.
QUESTIONS = [
    {
        "id": "horizon",
        "text": "When will you need to start using most of this money?",
        "answers": ["In less than 3 years", "In 3 to 5 years",
                    "In 6 to 10 years", "More than 10 years from now"],
    },
    {
        "id": "goal",
        "text": "What is your main goal for this money?",
        "answers": ["Protect what I have", "Earn steady income",
                    "Balance growth and safety", "Grow it as much as possible"],
    },
    {
        "id": "drop_reaction",
        "text": "Your portfolio falls 20% in one year. What do you do?",
        "answers": ["Sell everything", "Sell some", "Hold and wait",
                    "Buy more while prices are low"],
    },
    {
        "id": "experience",
        "text": "How much investing experience do you have?",
        "answers": ["None", "Savings accounts and CDs only",
                    "Some stocks or funds", "I invest regularly"],
    },
    {
        "id": "income",
        "text": "How stable is your income?",
        "answers": ["Unstable", "Somewhat stable", "Stable", "Very stable"],
    },
    {
        "id": "emergency_fund",
        "text": "How many months of expenses do you have saved for emergencies?",
        "answers": ["None", "Less than 3 months", "3 to 6 months",
                    "More than 6 months"],
    },
    {
        "id": "tradeoff",
        "text": "Which one-year range of results would you choose?",
        "answers": ["+2% to +4%", "-5% to +10%", "-15% to +20%",
                    "-25% to +35%"],
    },
]

# Score bands: (lowest total, highest total, profile)
SCORE_BANDS = [
    (7, 12, "Conservative"),
    (13, 17, "Moderately Conservative"),
    (18, 22, "Moderate"),
    (23, 28, "Growth"),
]

# Suitability caps by time horizon answer (1-4 points).
# Money needed in < 3 years -> at most Conservative.
# Money needed in 3-5 years -> at most Moderately Conservative.
HORIZON_CAPS = {1: "Conservative", 2: "Moderately Conservative"}


@dataclass
class RiskResult:
    score: int                 # total points, 7-28
    score_profile: str         # profile the score alone points to
    profile: str               # final profile after suitability caps
    capped: bool               # True if a cap lowered the profile
    reason: str                # plain-English explanation


def score_answers(answers: dict) -> int:
    """Add up the points. `answers` maps question id -> points (1-4)."""
    total = 0
    for q in QUESTIONS:
        points = answers[q["id"]]
        if points not in (1, 2, 3, 4):
            raise ValueError(f"{q['id']}: answer must be 1-4, got {points}")
        total += points
    return total


def profile_for_score(score: int) -> str:
    """Look up which score band the total falls in."""
    for low, high, profile in SCORE_BANDS:
        if low <= score <= high:
            return profile
    raise ValueError(f"Score {score} is outside 7-28")


def assess(answers: dict) -> RiskResult:
    """Full assessment: score, profile, then the suitability cap."""
    score = score_answers(answers)
    score_profile = profile_for_score(score)

    profile = score_profile
    capped = False
    reason = f"Score of {score} out of 28 points to {score_profile}."

    cap = HORIZON_CAPS.get(answers["horizon"])
    if cap and PROFILES.index(score_profile) > PROFILES.index(cap):
        profile = cap
        capped = True
        reason += (f" Capped at {cap} because the client needs the money "
                   f"soon, so there is little time to recover from a loss.")

    return RiskResult(score, score_profile, profile, capped, reason)
