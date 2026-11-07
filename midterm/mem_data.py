"""Memory-theme dataset: DRAM ETF's underlying stocks (Roundhill holdings as of 2026-11-02) + proxies."""
from pathlib import Path

import pandas as pd
import yfinance as yf

DATA = Path(__file__).parent / "data"
HOLD = {  # name: yahoo ticker
    "MU": "MU", "STX": "STX", "WDC": "WDC", "SNDK": "SNDK", "SKHY_ADR": "SKHY",
    "Samsung": "005930.KS", "SKhynix": "000660.KS", "Kioxia": "285A.T",
    "Nanya": "2408.TW", "Winbond": "2344.TW", "GigaDevice": "603986.SS",
}
PROXY = {"SPY": "SPY", "SMH": "SMH", "QQQ": "QQQ", "EWY": "EWY", "EWT": "EWT", "NVDA": "NVDA", "DRAM": "DRAM",
         "KRW": "KRW=X", "TWD": "TWD=X", "JPY": "JPY=X"}

def pull():
    allt = {**HOLD, **PROXY}
    raw = yf.download(list(allt.values()), start="2010-01-01", auto_adjust=True, progress=False, threads=False)
    inv = {v: k for k, v in allt.items()}
    out = {}
    for f in ("Open", "High", "Low", "Close", "Volume"):
        d = raw[f].rename(columns=inv)
        d.to_parquet(DATA / f"mem_{f.lower()}.parquet"); out[f] = d
    return out

if __name__ == "__main__":
    o = pull()
    c = o["Close"]
    print(pd.DataFrame({"first": c.apply(lambda s: s.first_valid_index()), "last": c.apply(lambda s: s.last_valid_index()),
                        "n": c.count()}).to_string())
