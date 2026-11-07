"""Retry tickers that yfinance rate-limited in data.py, in small batches, and merge into the cache."""
import time

import pandas as pd
import yfinance as yf

from data import DATA, START, tickers

have = set(pd.read_parquet(DATA / "close.parquet").columns)
missing = [t for t in tickers() if t not in have]
print(len(missing), "missing")
parts = []
for i in range(0, len(missing), 20):
    parts.append(yf.download(missing[i:i + 20], start=START, auto_adjust=True, progress=False, threads=False))
    time.sleep(3)
for f in ("Open", "High", "Low", "Close", "Volume"):
    new = pd.concat([p[f] for p in parts], axis=1).dropna(how="all", axis=1)
    old = pd.read_parquet(DATA / f"{f.lower()}.parquet")
    pd.concat([old, new.reindex(old.index)], axis=1).to_parquet(DATA / f"{f.lower()}.parquet")
    print(f, new.shape[1], "added")
