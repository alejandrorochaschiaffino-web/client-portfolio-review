# Client Portfolio Review Tool

A bilingual (English/Spanish) tool that profiles an investor, builds and
stress-tests a portfolio, and writes the client review an advisor would send.

> Educational project. Not investment advice.

## Status

- [x] **Phase 1 — Foundation:** risk questionnaire, suitability caps, model portfolios, allocation engine
- [ ] Phase 2 — Risk engine: real ETF data, crisis stress tests, duration rate shock
- [ ] Phase 3 — MVP: bilingual AI client report, web app, public link
- [ ] Phase 4 — Monte Carlo goal projection, PDF export
- [ ] Phase 5 — Demo video and polish

## How it works (Phase 1)

1. **Questionnaire.** 7 questions (time horizon, goal, reaction to a 20% drop,
   experience, income stability, emergency fund, preferred range of results).
   Each answer is worth 1–4 points, so scores run from 7 to 28.
2. **Profile.** The score picks a profile:

   | Score | Profile |
   |---|---|
   | 7–12 | Conservative |
   | 13–17 | Moderately Conservative |
   | 18–22 | Moderate |
   | 23–28 | Growth |

3. **Suitability cap.** A client who needs the money within 3 years is capped at
   Conservative; within 3–5 years, at Moderately Conservative. Their *willingness*
   to take risk can't override their *ability* to take it.
4. **Allocation.** Each profile maps to a model portfolio of four index ETFs
   (VTI, VXUS, BND, SGOV), split into dollars for the client's amount.

| Profile | US stocks | Intl stocks | Bonds | Cash |
|---|---|---|---|---|
| Conservative | 15% | 5% | 55% | 25% |
| Moderately Conservative | 30% | 10% | 45% | 15% |
| Moderate | 45% | 15% | 35% | 5% |
| Growth | 60% | 25% | 15% | 0% |

## Run it

```bash
python3 main.py               # review the three sample clients
python3 main.py --interview   # take the questionnaire yourself
python3 -m pip install pytest && python3 -m pytest   # run the tests
```

## Project layout

```
portfolio_tool/
  profiles.py        questionnaire, scoring, suitability caps
  portfolios.py      the four model portfolios
  allocation.py      profile + amount -> dollars per fund
  sample_clients.py  three made-up clients for demos
main.py              terminal demo
tests/               automated checks
```
