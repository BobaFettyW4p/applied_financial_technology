"""Build and cache the research dataset: S&P 1500 constituents' daily adjusted OHLCV from yfinance.

Universe note: current index members only, so results carry survivorship bias. Use this
as a screen; confirm anything promising on QuantConnect (point-in-time universe).
"""
import io
import sys
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

DATA = Path(__file__).parent / "data"
START = "2010-01-01"
PAGES = {
    "sp500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
    "sp400": "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
    "sp600": "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
}


def tickers() -> list[str]:
    out = set()
    for url in PAGES.values():
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
        for t in pd.read_html(io.StringIO(html)):
            col = next((c for c in t.columns if str(c) in ("Symbol", "Ticker symbol")), None)
            if col is not None:
                out |= set(t[col].astype(str).str.replace(".", "-", regex=False))
                break
    return sorted(out)


def download() -> None:
    DATA.mkdir(exist_ok=True)
    tk = tickers()
    print(len(tk), "tickers")
    px = yf.download(tk, start=START, auto_adjust=True, progress=False, threads=True)
    for f in ("Open", "High", "Low", "Close", "Volume"):
        px[f].dropna(how="all", axis=1).to_parquet(DATA / f"{f.lower()}.parquet")
    print("saved", px["Close"].shape)


def load() -> dict[str, pd.DataFrame]:
    return {f: pd.read_parquet(DATA / f"{f}.parquet") for f in ("open", "high", "low", "close", "volume")}


if __name__ == "__main__":
    download()
