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
   (max drawdown), measured on daily values with the portfolio rebalanced to its target weights
   every month.
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

## Results (real data, Jun 2007 – Oct 2026)

| Profile | Avg yearly return | Volatility | Worst fall | 2008 crisis | 2020 COVID | 2022 rate shock |
|---|---|---|---|---|---|---|
| Conservative | 4.0% | 4.6% | −14.4% | −6.5% | −7.6% | −13.0% |
| Moderately Conservative | 5.6% | 7.3% | −24.8% | −18.9% | −14.4% | −16.8% |
| Moderate | 7.0% | 10.2% | −36.9% | −31.2% | −21.2% | −20.6% |
| Growth | 8.2% | 13.8% | −50.2% | −47.2% | −29.6% | −24.3% |

**Key finding:** the Conservative portfolio lost *more* in 2022 than in 2008. In 2008 bonds
rose while stocks crashed; in 2022 rising rates pushed bonds down with stocks, exactly what
duration predicts. Bonds protect against most crashes, but not against a rate shock.

### What clients actually ask after a crash

| Question | How the tool answers it |
|---|---|
| "How long until I'm back to even?" | **Recovery time:** months from the peak (and from the bottom) until the portfolio regained its starting value |
| "Should I sell and wait it out?" | **Cost of panic-selling:** a client who sold at the bottom, sat in T-bills for a year and bought back, vs. one who stayed invested |
| "Does it matter when a crash hits if I'm retired?" | **Retirement timing risk:** 10 years of fixed withdrawals with the 2008 crash at the start vs. the exact same returns in reverse order |

On $100,000 in the Growth portfolio (values as of Oct 9, 2026):

| Crisis | Back to even after | Stayed invested | Panic-sold | Cost of panicking |
|---|---|---|---|---|
| 2008 Financial Crisis | 53 months (Mar 2012) | $469,563 | $281,140 | $188,423 |
| 2020 COVID Crash | 6 months (Aug 2020) | $204,743 | $122,098 | $82,646 |
| 2022 Rate Shock | 25 months (Feb 2024) | $152,248 | $134,724 | $17,524 |

**Retirement timing:** a $500,000 Growth portfolio withdrawing $25,000 a year from Nov 2007 to
Oct 2017 ends with **$451,949** when the crash comes first, but **$597,361** with the same
returns in reverse order. Same 5.8% average return; the order alone cost **$145,412**.

Past results don't predict future returns. Crisis figures assume buying at the peak and
holding to the bottom, before fees and taxes.

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
  client_scenarios.py  recovery time, panic-selling cost, retirement timing risk
scripts/fetch_data.py  downloads fresh prices
data/prices.csv      saved price snapshot
main.py              terminal demo
tests/               automated checks
```
