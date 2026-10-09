# Client Portfolio Review Tool

A bilingual (English/Spanish) tool that profiles an investor, builds and
stress-tests a portfolio, and writes the client review an advisor would send.

> Educational project. Not investment advice.

## Status

- [x] **Phase 1 — Foundation:** risk questionnaire, suitability caps, model portfolios, allocation engine
- [x] **Phase 2 — Risk engine:** real ETF data, crisis stress tests, duration rate shock
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

## How it works (Phase 2)

1. **Real data.** Daily prices for VTI, VXUS, BND and SGOV from Yahoo Finance, back to 2007.
   VXUS (launched 2011) and SGOV (2020) are extended back with stand-ins that track the
   same thing: VGTSX for international stocks and BIL for T-bills. If the live download
   fails, the tool uses the saved snapshot in `data/prices.csv`, which a GitHub Action
   refreshes every Monday.
2. **Long-run risk.** Average yearly return, volatility, and the worst fall from a peak
   (max drawdown), rebalancing to target weights monthly.
3. **Crisis stress tests.** Buy at the market peak, hold to the bottom:

   | Crisis | Peak | Bottom |
   |---|---|---|
   | 2008 Financial Crisis | Oct 9, 2007 | Mar 9, 2009 |
   | 2020 COVID Crash | Feb 19, 2020 | Mar 23, 2020 |
   | 2022 Rate Shock | Jan 3, 2022 | Oct 12, 2022 |

4. **Rate shock with duration.** Bond price change ≈ −duration × change in rates. BND's
   average duration is 5.8 years ([Vanguard fact sheet](https://workplace.vanguard.com/iippdf/pdfs/FS928R.pdf),
   June 30, 2026); SGOV's is about 0.1 years. The duration math is tested against a class
   example: a 4-year, 5% quarterly bond at a 9% yield prices at $866.87 with a duration of
   3.6174 years.

## Run it

```bash
python3 main.py               # review the three sample clients
python3 main.py --interview   # take the questionnaire yourself
python3 main.py --offline     # use saved prices, no download
python3 scripts/fetch_data.py # refresh the price snapshot
python3 -m pip install -r requirements.txt && python3 -m pytest   # run the tests
```

## Project layout

```
portfolio_tool/
  profiles.py        questionnaire, scoring, suitability caps
  portfolios.py      the four model portfolios
  allocation.py      profile + amount -> dollars per fund
  sample_clients.py  three made-up clients for demos
  data.py            live prices with saved-snapshot fallback
  risk.py            return, volatility, drawdown, crisis stress tests
  duration.py        bond duration and the rate-shock test
scripts/fetch_data.py  downloads fresh prices
data/prices.csv      saved price snapshot
main.py              terminal demo
tests/               automated checks
```
