"""
Wheel Strategy Dashboard — FastAPI Backend
============================================

API:
    GET  /              Dashboard UI
    GET  /api/scan      Run a fresh live scan, return JSON
    GET  /api/latest    Return cached last scan
    GET  /api/history   List past scan files
    GET  /api/playbook  Decision rules as JSON

Run:
    uvicorn dashboard.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.daily_scanner import run_scan, save_report

app = FastAPI(title="Wheel Strategy Dashboard", version="1.0.0")

BASE_DIR = Path(__file__).resolve().parent
SCAN_DIR = Path(__file__).resolve().parent.parent / "results" / "daily_scans"

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_latest_scan: dict | None = None


# ── API ──────────────────────────────────────────────────────────

@app.get("/api/scan")
async def api_scan():
    """Run a fresh live scan and return results."""
    global _latest_scan
    results = run_scan()
    path = save_report(results, str(SCAN_DIR))
    _latest_scan = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "tickers": results,
    }
    return JSONResponse(_latest_scan)


@app.get("/api/latest")
async def api_latest():
    """Return the most recent cached scan."""
    global _latest_scan
    if _latest_scan:
        return JSONResponse(_latest_scan)
    latest = _load_latest_from_disk()
    if latest:
        _latest_scan = latest
        return JSONResponse(latest)
    return JSONResponse({"error": "No scans yet. Hit /api/scan first."}, status_code=404)


@app.get("/api/history")
async def api_history():
    """List past scan files."""
    SCAN_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(SCAN_DIR.glob("scan_*.json"), reverse=True)
    return JSONResponse([
        {"file": f.name, "timestamp": f.stem.replace("scan_", "")}
        for f in files[:50]
    ])


@app.get("/api/playbook")
async def api_playbook():
    """Return the full decision playbook as structured JSON."""
    return JSONResponse({
        "entry": {
            "SELL_PUT": "IVR >= 30, above 200 SMA, no earnings. IVR 30-50 = 0.25 delta, IVR 50+ = 0.20 delta.",
            "BUY_STOCK": "IVR < 20 (premium too thin), or strong breakout, or ex-div capture.",
            "STAND_ASIDE": "Earnings in DTE, or >10% below 200 SMA, or below 200 SMA + IVR > 80.",
        },
        "put_management": {
            "50% profit": "Close, re-sell 30-45 DTE.",
            "OTM > 21 DTE": "Hold.",
            "OTM <= 21 DTE": "Close if >30% profit, else roll same strike +30d.",
            "ITM < 3%": "Roll same strike +30d for credit.",
            "ITM 3-8%": "Roll down 1-2 strikes +45d. Must be for credit.",
            "ITM > 8%": "Accept assignment, sell covered calls.",
            "golden_rule": "NEVER roll for a debit.",
        },
        "covered_call": {
            "> 5% above basis": "Sell 0.30-0.40 delta CC — get called away.",
            "Near basis (+/- 2%)": "Sell 0.25 delta CC — standard income.",
            "2-10% below basis": "Sell 0.15-0.20 delta CC — patient recovery.",
            "> 10% below basis": "Sell 0.10-0.15 delta CC — wait for recovery.",
            "rule": "Never sell a call below adjusted cost basis.",
        },
        "call_management": {
            "50% profit": "Close, re-sell.",
            "ITM <= 7 DTE, above basis": "Let it get called away. Cycle complete.",
            "ITM <= 7 DTE, below basis": "Roll up and out.",
            "Stock fell > 8%": "Roll call down closer to money. Never below cost basis.",
        },
        "concentration": {
            "max_per_ticker": "20%", "max_per_sector": "35%", "cash_buffer": "25%",
        },
    })


@app.get("/api/options/{ticker}")
async def api_options(ticker: str, expiry: str | None = None):
    """Return option chain (puts + calls) for a ticker.

    If expiry is omitted, returns available expirations.
    If expiry is given (YYYY-MM-DD), returns the chain for that date.
    """
    import pandas as pd
    import yfinance as yf
    import math

    t = yf.Ticker(ticker)
    expirations = list(t.options) if t.options else []

    if not expiry:
        return JSONResponse({"ticker": ticker, "expirations": expirations})

    if expiry not in expirations:
        return JSONResponse({"error": f"Invalid expiry {expiry}"}, status_code=400)

    chain = t.option_chain(expiry)
    spot = None
    try:
        info = t.info
        spot = info.get("currentPrice") or info.get("regularMarketPrice")
    except Exception:
        pass

    def safe_float(v, default=0.0):
        try:
            f = float(v)
            return f if f == f else default  # NaN check
        except (TypeError, ValueError):
            return default

    def safe_int(v, default=0):
        try:
            f = float(v)
            return int(f) if f == f else default
        except (TypeError, ValueError):
            return default

    # Compute days to expiry for delta calc
    from datetime import datetime as _dt
    try:
        exp_date = _dt.strptime(expiry, "%Y-%m-%d")
        dte = max((exp_date - _dt.now()).days, 1)
    except Exception:
        dte = 30

    from option_pricing import black_scholes_put as _bs_put, black_scholes_call as _bs_call

    def _calc_delta(strike, iv_pct, side):
        """Estimate delta using Black-Scholes."""
        if not spot or spot <= 0 or iv_pct <= 0:
            return None
        T = dte / 365
        sigma = iv_pct / 100
        try:
            if side == "CALL":
                q = _bs_call(spot, strike, T, 0.045, sigma)
                return round(q.delta, 3)
            else:
                q = _bs_put(spot, strike, T, 0.045, sigma)
                return round(q.delta, 3)
        except Exception:
            return None

    def clean(df, side):
        rows = []
        for _, r in df.iterrows():
            bid = safe_float(r.get("bid"))
            ask = safe_float(r.get("ask"))
            iv_raw = safe_float(r.get("impliedVolatility"))
            iv_pct = round(iv_raw * 100, 1)
            strike = float(r["strike"])
            delta = _calc_delta(strike, iv_pct if iv_pct > 0 else 30, side)
            rows.append({
                "strike": strike,
                "last": safe_float(r.get("lastPrice")),
                "bid": bid,
                "ask": ask,
                "mid": round((bid + ask) / 2, 2),
                "volume": safe_int(r.get("volume")),
                "oi": safe_int(r.get("openInterest")),
                "iv": iv_pct,
                "delta": delta,
                "itm": bool(r.get("inTheMoney", False)),
                "side": side,
            })
        return rows

    puts = clean(chain.puts, "PUT")
    calls = clean(chain.calls, "CALL")

    return JSONResponse({
        "ticker": ticker,
        "expiry": expiry,
        "spot": spot,
        "puts": puts,
        "calls": calls,
        "expirations": expirations,
    })


# ── Dashboard ────────────────────────────────────────────────────

@app.get("/api/chart/{ticker}")
async def api_chart(ticker: str, months: int = 6):
    """Return OHLCV + indicators for interactive charting."""
    import math
    from datetime import datetime, timedelta
    import numpy as np
    import pandas as pd
    import yfinance as yf

    end = datetime.now()
    start = end - timedelta(days=months * 31)
    df = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                     end=end.strftime("%Y-%m-%d"), progress=False,
                     auto_adjust=False)
    if df.empty:
        return JSONResponse({"error": f"No data for {ticker}"}, status_code=404)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # OHLCV candles
    candles = []
    for dt, row in df.iterrows():
        candles.append({
            "time": dt.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row.get("Volume", 0)),
        })

    close = df["Close"]

    # EMAs
    ema20 = close.ewm(span=20).mean()
    ema50 = close.ewm(span=50).mean()
    sma200 = close.rolling(200).mean()

    def series_to_list(s):
        return [{"time": dt.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
                for dt, v in s.dropna().items()]

    # RSI-14
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # Volume
    vol = df.get("Volume", pd.Series(dtype=float))
    vol_data = [{"time": dt.strftime("%Y-%m-%d"), "value": int(v),
                 "color": "#26a69a80" if float(df.loc[dt, "Close"]) >= float(df.loc[dt, "Open"]) else "#ef535080"}
                for dt, v in vol.items() if not pd.isna(v)]

    return JSONResponse({
        "ticker": ticker,
        "candles": candles,
        "ema20": series_to_list(ema20),
        "ema50": series_to_list(ema50),
        "sma200": series_to_list(sma200),
        "rsi": series_to_list(rsi),
        "volume": vol_data,
    })


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "index.html")


def _load_latest_from_disk() -> dict | None:
    SCAN_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(SCAN_DIR.glob("scan_*.json"), reverse=True)
    if not files:
        return None
    with open(files[0]) as f:
        return json.load(f)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard.app:app", host="0.0.0.0", port=8080, reload=True)
