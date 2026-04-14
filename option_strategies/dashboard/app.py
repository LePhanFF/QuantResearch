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


@app.get("/api/fundamentals/{ticker}")
async def api_fundamentals(ticker: str):
    """Return company profile, financials, and news."""
    import yfinance as yf

    t = yf.Ticker(ticker)
    info = t.info or {}

    def sf(k, fmt=None):
        v = info.get(k)
        if v is None:
            return None
        if fmt == "pct":
            return round(float(v) * 100, 1)
        if fmt == "B":
            return round(float(v) / 1e9, 2)
        if fmt == "M":
            return round(float(v) / 1e6, 1)
        try:
            f = float(v)
            return round(f, 2) if f == f else None
        except (TypeError, ValueError):
            return v

    # News
    news_items = []
    try:
        raw = t.news or []
        for n in raw[:8]:
            content = n.get("content", n)
            news_items.append({
                "title": content.get("title", ""),
                "publisher": content.get("provider", {}).get("displayName", "") if isinstance(content.get("provider"), dict) else content.get("publisher", ""),
                "date": content.get("pubDate", ""),
                "link": content.get("canonicalUrl", {}).get("url", "") if isinstance(content.get("canonicalUrl"), dict) else "",
            })
    except Exception:
        pass

    return JSONResponse({
        "ticker": ticker,
        "profile": {
            "name": info.get("longName") or info.get("shortName", ticker),
            "summary": info.get("longBusinessSummary", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "employees": sf("fullTimeEmployees"),
            "website": info.get("website", ""),
        },
        "valuation": {
            "market_cap_b": sf("marketCap", "B"),
            "trailing_pe": sf("trailingPE"),
            "forward_pe": sf("forwardPE"),
            "peg_ratio": sf("pegRatio"),
            "price_to_book": sf("priceToBook"),
            "ev_to_ebitda": sf("enterpriseToEbitda"),
        },
        "profitability": {
            "gross_margin_pct": sf("grossMargins", "pct"),
            "operating_margin_pct": sf("operatingMargins", "pct"),
            "profit_margin_pct": sf("profitMargins", "pct"),
            "roe_pct": sf("returnOnEquity", "pct"),
            "roa_pct": sf("returnOnAssets", "pct"),
        },
        "growth": {
            "revenue_growth_pct": sf("revenueGrowth", "pct"),
            "earnings_growth_pct": sf("earningsGrowth", "pct"),
        },
        "balance_sheet": {
            "total_cash_b": sf("totalCash", "B"),
            "total_debt_b": sf("totalDebt", "B"),
            "debt_to_equity": sf("debtToEquity"),
            "current_ratio": sf("currentRatio"),
            "free_cash_flow_b": sf("freeCashflow", "B"),
            "operating_cash_flow_b": sf("operatingCashflow", "B"),
        },
        "dividends": {
            "dividend_yield_pct": sf("dividendYield"),
            "payout_ratio_pct": sf("payoutRatio", "pct"),
            "annual_dividend": sf("trailingAnnualDividendRate"),
        },
        "news": news_items,
    })


@app.get("/api/basket")
async def api_basket(size: int = 50000):
    """Build an optimized portfolio basket for a given account size.

    Balances yield, growth, and risk — constrains max drawdown to ~20%.
    Returns allocations for selling puts, buying stock, and covered calls.
    """
    import math
    import numpy as np

    # Need scan data
    global _latest_scan
    scan = _latest_scan
    if not scan:
        scan = _load_latest_from_disk()
    if not scan or not scan.get("tickers"):
        return JSONResponse({"error": "Run a scan first (/api/scan)"}, status_code=400)

    tickers = [t for t in scan["tickers"] if "error" not in t]

    # Score each ticker for basket inclusion
    scored = []
    for t in tickers:
        # Skip tickers that cost more than 20% of portfolio
        capital = t.get("csp_capital_required", 0) or 0
        if capital > size * 0.20 or capital <= 0:
            continue

        # Composite score: yield + growth potential + premium income - risk
        ivr = t.get("iv_rank", 0) or 0
        rsi = t.get("rsi_14", 50) or 50
        roc = t.get("csp_ann_roc_pct", 0) or 0
        dd = abs(t.get("max_dd_6w_pct", 0) or 0)
        pe = t.get("trailing_pe", 25) or 25
        off_high = abs(t.get("pct_off_52w_high", 0) or 0)
        div_yield = 0
        # Estimate div yield from sector
        for wt in __import__("wheel_criteria", fromlist=["WHEEL_TICKERS"]).WHEEL_TICKERS:
            if wt.ticker == t["ticker"]:
                div_yield = wt.dividend_yield
                break

        # Yield score (0-25): dividend + option premium
        yield_score = min(div_yield * 3, 15) + min(roc * 0.5, 10)

        # Value score (0-25): lower P/E better, pullback = opportunity
        value_score = max(0, 25 - pe * 0.4) + min(off_high * 0.5, 10)

        # Momentum score (0-25): RSI sweet spot 30-60
        if rsi < 30:
            mom_score = 20  # oversold = great entry
        elif rsi < 50:
            mom_score = 15
        elif rsi < 70:
            mom_score = 8
        else:
            mom_score = 0  # overbought = avoid

        # Risk penalty (0-25): lower drawdown = better
        risk_score = max(0, 25 - dd * 1.5)

        total = yield_score + value_score + mom_score + risk_score
        action = t.get("entry_action", "STAND_ASIDE")

        scored.append({
            "ticker": t["ticker"],
            "name": t.get("name", ""),
            "sector": t.get("sector", ""),
            "price": t.get("price", 0),
            "capital": capital,
            "action": action,
            "score": round(total, 1),
            "yield_score": round(yield_score, 1),
            "value_score": round(value_score, 1),
            "momentum_score": round(mom_score, 1),
            "risk_score": round(risk_score, 1),
            "iv_rank": ivr,
            "rsi": rsi,
            "roc_pct": roc,
            "dd_6w_pct": -dd,
            "div_yield": div_yield,
            "csp_strike": t.get("csp_strike"),
            "csp_premium": t.get("csp_premium"),
            "trailing_pe": t.get("trailing_pe"),
        })

    # Sort by composite score
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Greedy allocation with concentration limits
    cash_buffer = 0.25
    deployable = size * (1 - cash_buffer)
    max_per_ticker = size * 0.20
    max_per_sector = size * 0.35
    max_dd_target = 20.0  # max portfolio drawdown %

    allocated = []
    sector_used = {}
    total_deployed = 0.0
    total_yield = 0.0
    total_roc = 0.0
    total_dd_weighted = 0.0

    for s in scored:
        if total_deployed >= deployable:
            break
        cost = s["capital"]
        if cost > max_per_ticker:
            continue
        if total_deployed + cost > deployable:
            continue
        sec = s["sector"]
        if sector_used.get(sec, 0) + cost > max_per_sector:
            continue

        # Check portfolio drawdown constraint
        weight = cost / size
        projected_dd = abs(s["dd_6w_pct"]) * weight
        if total_dd_weighted + projected_dd > max_dd_target * 0.8:
            continue

        allocated.append({
            **s,
            "weight_pct": round(cost / size * 100, 1),
            "strategy": "SELL_PUT" if s["action"] == "SELL_PUT" else "BUY_STOCK",
        })
        sector_used[sec] = sector_used.get(sec, 0) + cost
        total_deployed += cost
        total_yield += s["div_yield"] * (cost / size)
        total_roc += s["roc_pct"] * (cost / size)
        total_dd_weighted += projected_dd

    return JSONResponse({
        "account_size": size,
        "deployed": round(total_deployed, 0),
        "deployed_pct": round(total_deployed / size * 100, 1),
        "cash_reserve": round(size - total_deployed, 0),
        "cash_reserve_pct": round((size - total_deployed) / size * 100, 1),
        "positions": len(allocated),
        "weighted_yield_pct": round(total_yield, 2),
        "weighted_roc_pct": round(total_roc, 1),
        "est_drawdown_pct": round(total_dd_weighted, 1),
        "allocations": allocated,
        "sectors": {k: round(v / size * 100, 1) for k, v in sector_used.items()},
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
async def api_chart(ticker: str, tf: str = "1Y"):
    """Return OHLCV + indicators for interactive charting.

    Timeframe options:
      1D  = today intraday (15m bars)
      5D  = 5 days intraday (15m bars)
      1M  = 1 month (1h bars)
      3M  = 3 months (1h bars)
      6M  = 6 months (daily bars)
      1Y  = 1 year (daily bars)
      2Y  = 2 years (daily bars)
      5Y  = 5 years (daily bars)
    """
    import math
    import numpy as np
    import pandas as pd
    import yfinance as yf

    # Map timeframe to yfinance period + interval
    TF_MAP = {
        "1D":  ("1d",  "15m"),
        "5D":  ("5d",  "15m"),
        "1M":  ("1mo", "1h"),
        "3M":  ("3mo", "1h"),
        "6M":  ("6mo", "1d"),
        "1Y":  ("1y",  "1d"),
        "2Y":  ("2y",  "1d"),
        "5Y":  ("5y",  "1d"),
    }
    period, interval = TF_MAP.get(tf.upper(), ("1y", "1d"))
    intraday = interval in ("15m", "1h")

    df = yf.download(ticker, period=period, interval=interval,
                     progress=False, auto_adjust=False)
    if df.empty:
        return JSONResponse({"error": f"No data for {ticker}"}, status_code=404)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Time formatting: intraday uses unix timestamp, daily uses date string
    def fmt_time(dt):
        if intraday:
            return int(dt.timestamp())
        return dt.strftime("%Y-%m-%d")

    # OHLCV candles
    candles = []
    for dt, row in df.iterrows():
        candles.append({
            "time": fmt_time(dt),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
        })

    close = df["Close"]

    # EMAs (adjust periods for intraday)
    if intraday and interval == "15m":
        ema_short, ema_mid = 26, 78  # ~1 day, ~3 days in 15m bars
        sma_long_period = 200        # won't have enough data, that's fine
    elif intraday and interval == "1h":
        ema_short, ema_mid = 20, 50
        sma_long_period = 200
    else:
        ema_short, ema_mid = 20, 50
        sma_long_period = 200

    ema20 = close.ewm(span=ema_short).mean()
    ema50 = close.ewm(span=ema_mid).mean()
    sma200 = close.rolling(sma_long_period).mean()

    def series_to_list(s):
        return [{"time": fmt_time(dt), "value": round(float(v), 2)}
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
    vol_data = []
    for dt, v in vol.items():
        if pd.isna(v):
            continue
        c = float(df.loc[dt, "Close"])
        o = float(df.loc[dt, "Open"])
        vol_data.append({
            "time": fmt_time(dt),
            "value": int(v),
            "color": "#26a69a80" if c >= o else "#ef535080",
        })

    return JSONResponse({
        "ticker": ticker,
        "timeframe": tf.upper(),
        "interval": interval,
        "bars": len(candles),
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
