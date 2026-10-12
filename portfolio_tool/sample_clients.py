"""
Three made-up clients for demos and tests. Answers are points (1-4)
for each question in profiles.QUESTIONS. Each has a savings goal for the
goal projection: reach `target` dollars in `years`, adding `monthly`.
"""

SAMPLE_CLIENTS = [
    {
        "name": "Jordan Lee",
        "age": 28,
        "situation": "Software engineer saving for retirement",
        "amount": 50_000,
        "answers": {"horizon": 4, "goal": 4, "drop_reaction": 4,
                    "experience": 3, "income": 4, "emergency_fund": 3,
                    "tradeoff": 4},
        "goal": {"target": 1_000_000, "years": 30, "monthly": 500},
    },
    {
        "name": "Carlos and Ana Rivera",
        "age": 45,
        "situation": "Saving for their kids' college in about 8 years",
        "amount": 120_000,
        "answers": {"horizon": 3, "goal": 3, "drop_reaction": 3,
                    "experience": 3, "income": 3, "emergency_fund": 3,
                    "tradeoff": 2},
        "goal": {"target": 200_000, "years": 8, "monthly": 400},
    },
    {
        "name": "Maria Gonzalez",
        "age": 61,
        "situation": "Retiring in 2 years; confident investor",
        "amount": 400_000,
        "answers": {"horizon": 1, "goal": 3, "drop_reaction": 4,
                    "experience": 4, "income": 3, "emergency_fund": 4,
                    "tradeoff": 3},
        "goal": {"target": 400_000, "years": 2, "monthly": 0},   # keep what she has
    },
]
