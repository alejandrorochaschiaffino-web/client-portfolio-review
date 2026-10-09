"""
Market data: daily prices for the four ETFs.

How it works:
1. Try to download fresh prices from Yahoo Finance (needs internet).
2. If that fails, fall back to the saved snapshot in data/prices.csv,
   so the tool still works offline or if Yahoo is down.

Filling in history before a fund existed:
- VXUS launched in 2011 and SGOV in 2020, but our stress tests go back to
  2008. Before each fund's launch we use a "proxy" that tracks the same
  thing: VGTSX (Vanguard's international index mutual fund) for VXUS, and
  BIL (a 1-3 month T-bill ETF) for SGOV. We chain the proxy's daily
  returns onto the real fund's history.
"""

from pathlib import Path
import pandas as pd

TICKERS = ["VTI", "VXUS", "BND", "SGOV"]
PROXIES = {"VXUS": "VGTSX", "SGOV": "BIL"}   # fund -> stand-in before launch
START = "2007-06-01"
SNAPSHOT = Path(__file__).resolve().parent.parent / "data" / "prices.csv"


# The data must reach back before the first stress test (Oct 9, 2007).
MUST_START_BY = pd.Timestamp("2007-10-09")


def _end_date() -> str:
    """
    yfinance's `end` is exclusive. Include today only once the US market has
    closed (New York time), so an unfinished trading day is never saved as
    if it were a closing price.
    """
    from zoneinfo import ZoneInfo
    now = pd.Timestamp.now(tz=ZoneInfo("America/New_York"))
    closed = now.hour > 16 or (now.hour == 16 and now.minute >= 30)
    end = now.normalize() + pd.Timedelta(days=1 if closed else 0)
    return end.strftime("%Y-%m-%d")


def _download(symbols, start):
    import logging, contextlib, io
    import yfinance as yf   # imported here so the rest works without it
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    end = _end_date()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        raw = yf.download(symbols, start=start, end=end, auto_adjust=True,
                          progress=False, threads=False)
    if raw is None or raw.empty:
        raise RuntimeError("Download returned nothing")
    closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
    closes = closes.dropna(how="all")
    missing = [s for s in symbols if s not in closes.columns or closes[s].dropna().empty]
    if missing:
        raise RuntimeError(f"Download is missing {missing}")
    return closes


def splice(fund: pd.Series, proxy: pd.Series) -> pd.Series:
    """Extend `fund` back in time using the proxy's daily returns."""
    fund, proxy = fund.dropna(), proxy.dropna()
    if fund.empty or proxy.empty:
        raise RuntimeError("Cannot splice an empty price series")
    first = fund.index[0]
    earlier = proxy[proxy.index <= first]
    if len(earlier) < 2:
        return fund
    # Scale the proxy so it meets the real fund's price on the fund's first day
    scaled = earlier * (fund.iloc[0] / earlier.iloc[-1])
    if scaled.index[-1] == first:          # same day in both: keep the real fund's price
        scaled = scaled.iloc[:-1]
    return pd.concat([scaled, fund]).sort_index()


def fetch_prices(start: str = START) -> pd.DataFrame:
    """Download live adjusted prices and fill pre-launch history with proxies."""
    closes = _download(TICKERS + list(PROXIES.values()), start)
    out = {}
    for t in TICKERS:
        series = closes[t]
        if t in PROXIES:
            series = splice(series, closes[PROXIES[t]])
        out[t] = series
    prices = pd.DataFrame(out).dropna()
    check_prices(prices)
    return prices


def check_prices(prices: pd.DataFrame, must_be_recent: bool = True) -> None:
    """Refuse incomplete or broken data, e.g. if one stand-in fund failed to download."""
    if prices.empty:
        raise RuntimeError("No usable prices")
    missing = [t for t in TICKERS if t not in prices.columns]
    if missing:
        raise RuntimeError(f"Missing funds: {missing}")
    if prices[TICKERS].isna().any().any() or (prices[TICKERS] <= 0).any().any():
        raise RuntimeError("Prices contain gaps or non-positive values")
    if not prices.index.is_monotonic_increasing or not prices.index.is_unique:
        raise RuntimeError("Dates are out of order or repeated")
    if prices.index[0] > MUST_START_BY:
        raise RuntimeError(f"History starts {prices.index[0]:%Y-%m-%d}, too late for the 2008 test")
    if must_be_recent and (pd.Timestamp.today() - prices.index[-1]).days > 10:
        raise RuntimeError(f"Latest price is {prices.index[-1]:%Y-%m-%d}, more than 10 days old")


def load_snapshot(path: Path = SNAPSHOT) -> pd.DataFrame:
    prices = pd.read_csv(path, index_col=0, parse_dates=True)
    check_prices(prices, must_be_recent=False)     # a snapshot may be a little old
    return prices


def load_prices(live: bool = True) -> tuple[pd.DataFrame, str]:
    """Return (prices, source). Tries live data first, then the snapshot."""
    if live:
        try:
            return fetch_prices(), "live (Yahoo Finance)"
        except Exception:
            pass
    if SNAPSHOT.exists():
        prices = load_snapshot()
        return prices, f"saved snapshot through {prices.index[-1]:%b %d, %Y}"
    raise FileNotFoundError(
        "No internet and no saved data. Run: python scripts/fetch_data.py")
