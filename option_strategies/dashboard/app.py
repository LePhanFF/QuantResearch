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

import os
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "rockit")


# ── Auth ─────────────────────────────────────────────────────────

@app.post("/api/login")
async def api_login(request: Request):
    body = await request.json()
    if body.get("password") == DASHBOARD_PASSWORD:
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False, "error": "Wrong password"}, status_code=401)


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
async def api_basket(size: int = 50000, max_dd: int = 20):
    """Build an optimized portfolio basket for a given account size.

    Balances yield, growth, and risk.
    max_dd: maximum portfolio drawdown target (5-40%).
    """
    import math
    import numpy as np

    # Need scan data — auto-scan if none exists
    global _latest_scan
    scan = _latest_scan
    if not scan:
        scan = _load_latest_from_disk()
    if not scan or not scan.get("tickers"):
        # Auto-trigger a scan
        from datetime import datetime
        results = run_scan()
        _latest_scan = {"generated": datetime.now().isoformat(timespec="seconds"), "tickers": results}
        scan = _latest_scan

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
    # More aggressive risk = less cash buffer, more deployment
    max_dd_target = max(5, min(40, max_dd))
    cash_buffer = max(0.15, 0.30 - (max_dd_target - 10) * 0.005)
    deployable = size * (1 - cash_buffer)
    max_per_ticker = size * 0.20
    max_per_sector = size * 0.35

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

    # Estimate annual income
    annual_div_income = sum(a["div_yield"] / 100 * a["capital"] for a in allocated)
    annual_premium_income = sum(a["roc_pct"] / 100 * a["capital"] for a in allocated)
    total_annual_income = annual_div_income + annual_premium_income

    return JSONResponse({
        "account_size": size,
        "max_dd_target": max_dd_target,
        "cash_buffer_pct": round(cash_buffer * 100, 1),
        "deployed": round(total_deployed, 0),
        "deployed_pct": round(total_deployed / size * 100, 1),
        "cash_reserve": round(size - total_deployed, 0),
        "cash_reserve_pct": round((size - total_deployed) / size * 100, 1),
        "positions": len(allocated),
        "weighted_yield_pct": round(total_yield, 2),
        "weighted_roc_pct": round(total_roc, 1),
        "est_drawdown_pct": round(total_dd_weighted, 1),
        "income": {
            "annual_dividends": round(annual_div_income, 0),
            "annual_premiums": round(annual_premium_income, 0),
            "annual_total": round(total_annual_income, 0),
            "monthly_total": round(total_annual_income / 12, 0),
            "yield_on_account_pct": round(total_annual_income / size * 100, 1),
        },
        "allocations": allocated,
        "sectors": {k: round(v / size * 100, 1) for k, v in sector_used.items()},
    })


@app.get("/api/basket/backtest")
async def api_basket_backtest(size: int = 50000, max_dd: int = 20):
    """Backtest the basket allocation over the last 5 years.

    Uses the same allocation logic as /api/basket, then downloads
    5Y daily data for each ticker, computes weighted portfolio
    equity curve, drawdown, and annual returns.
    """
    import numpy as np
    import pandas as pd
    import yfinance as yf

    # Get the basket allocation by calling our own endpoint
    basket_resp = await api_basket(size=size, max_dd=max_dd)
    basket = __import__("json").loads(basket_resp.body.decode())

    if "error" in basket or not basket.get("allocations"):
        return JSONResponse({"error": "No basket data. Run /api/scan first."}, status_code=400)

    allocations = basket["allocations"]
    tickers = [a["ticker"] for a in allocations]
    weights = {a["ticker"]: a["capital"] / basket["deployed"] for a in allocations}

    # Download 5Y daily data for all tickers at once
    if not tickers:
        return JSONResponse({"error": "Empty basket"}, status_code=400)

    data = yf.download(tickers, period="5y", interval="1d", progress=False)
    if data.empty:
        return JSONResponse({"error": "No historical data"}, status_code=400)

    # Extract close prices
    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"]
    else:
        close = data[["Close"]]
        close.columns = [tickers[0]]

    close = close.dropna(how="all").ffill()

    # Compute daily returns for each ticker
    returns = close.pct_change().fillna(0)

    # Weighted portfolio daily returns
    port_returns = pd.Series(0.0, index=returns.index)
    for t in tickers:
        if t in returns.columns:
            port_returns += returns[t] * weights.get(t, 0)

    # Add estimated daily premium income (spread evenly)
    daily_premium = basket["income"]["annual_premiums"] / 252 / basket["deployed"]
    port_returns += daily_premium

    # Equity curve
    equity = (1 + port_returns).cumprod() * size
    equity_list = [{"time": dt.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
                   for dt, v in equity.items()]

    # Buy & hold SPY benchmark
    spy_col = "SPY" if "SPY" in close.columns else None
    bench_list = []
    if spy_col:
        spy_ret = returns[spy_col]
        spy_eq = (1 + spy_ret).cumprod() * size
        bench_list = [{"time": dt.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
                      for dt, v in spy_eq.items()]

    # Drawdown series
    peak = equity.cummax()
    dd = (equity - peak) / peak * 100
    dd_list = [{"time": dt.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
               for dt, v in dd.items()]

    # Stats
    total_days = len(equity)
    years = total_days / 252
    total_return = (equity.iloc[-1] / equity.iloc[0] - 1) * 100
    ann_return = ((equity.iloc[-1] / equity.iloc[0]) ** (1 / max(years, 0.1)) - 1) * 100
    max_drawdown = float(dd.min())
    sharpe = float(port_returns.mean() / port_returns.std() * np.sqrt(252)) if port_returns.std() > 0 else 0

    # Annual breakdown
    annual = []
    for year in sorted(equity.index.year.unique()):
        yr_eq = equity[equity.index.year == year]
        if len(yr_eq) < 2:
            continue
        yr_ret = (yr_eq.iloc[-1] / yr_eq.iloc[0] - 1) * 100
        yr_dd_series = dd[dd.index.year == year]
        yr_dd = float(yr_dd_series.min()) if len(yr_dd_series) > 0 else 0
        annual.append({
            "year": int(year),
            "return_pct": round(yr_ret, 1),
            "max_dd_pct": round(yr_dd, 1),
            "end_value": round(float(yr_eq.iloc[-1]), 0),
        })

    return JSONResponse({
        "account_size": size,
        "max_dd_target": max_dd,
        "positions": len(tickers),
        "tickers": tickers,
        "years": round(years, 1),
        "stats": {
            "total_return_pct": round(total_return, 1),
            "ann_return_pct": round(ann_return, 1),
            "max_drawdown_pct": round(max_drawdown, 1),
            "sharpe": round(sharpe, 2),
            "final_value": round(float(equity.iloc[-1]), 0),
        },
        "annual": annual,
        "equity": equity_list,
        "benchmark": bench_list,
        "drawdown": dd_list,
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
        from datetime import datetime as _dt
        import pandas as pd
        today = _dt.now()

        # Get next earnings date
        next_earnings = None
        days_to_earnings = None
        try:
            ed = t.earnings_dates
            if ed is not None and len(ed) > 0:
                for dt_idx in ed.index:
                    try:
                        edt = pd.Timestamp(dt_idx).tz_localize(None)
                    except Exception:
                        edt = pd.Timestamp(dt_idx)
                    dte_earn = (edt - pd.Timestamp(today)).days
                    if dte_earn >= 0:
                        if next_earnings is None or dte_earn < days_to_earnings:
                            next_earnings = edt.strftime("%Y-%m-%d")
                            days_to_earnings = dte_earn
        except Exception:
            pass

        # Find best expiry (30-45 DTE sweet spot)
        best_expiry = None
        best_dte = None
        exp_details = []
        for exp in expirations:
            try:
                exp_date = _dt.strptime(exp, "%Y-%m-%d")
                dte = (exp_date - today).days
                has_earnings = False
                if next_earnings:
                    earn_date = _dt.strptime(next_earnings, "%Y-%m-%d")
                    has_earnings = earn_date <= exp_date
                exp_details.append({
                    "expiry": exp,
                    "dte": dte,
                    "has_earnings": has_earnings,
                })
                if 28 <= dte <= 50:
                    if best_dte is None or abs(dte - 35) < abs(best_dte - 35):
                        best_expiry = exp
                        best_dte = dte
            except Exception:
                exp_details.append({"expiry": exp, "dte": None, "has_earnings": False})
        # Fallback
        if not best_expiry and expirations:
            for ed in exp_details:
                dte = ed.get("dte")
                if dte and dte > 7 and (best_dte is None or abs(dte - 35) < abs(best_dte - 35)):
                    best_expiry = ed["expiry"]
                    best_dte = dte

        return JSONResponse({
            "ticker": ticker,
            "expirations": [e["expiry"] for e in exp_details],
            "expiry_details": exp_details,
            "recommended_expiry": best_expiry,
            "recommended_dte": best_dte,
            "next_earnings": next_earnings,
            "days_to_earnings": days_to_earnings,
        })

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

    # Mark each option with a zone for highlighting
    for p in puts:
        d = p.get("delta")
        if d is not None:
            ad = abs(d)
            if 0.20 <= ad <= 0.30:
                p["zone"] = "optimal"    # best theta/IV sweet spot
            elif 0.15 <= ad < 0.20 or 0.30 < ad <= 0.35:
                p["zone"] = "good"       # acceptable range
            elif 0.10 <= ad < 0.15 or 0.35 < ad <= 0.50:
                p["zone"] = "wide"       # visible but not ideal
            else:
                p["zone"] = None
        else:
            p["zone"] = None

    for c in calls:
        d = c.get("delta")
        if d is not None:
            if 0.20 <= d <= 0.30:
                c["zone"] = "optimal"
            elif 0.15 <= d < 0.20 or 0.30 < d <= 0.35:
                c["zone"] = "good"
            elif 0.10 <= d < 0.15 or 0.35 < d <= 0.50:
                c["zone"] = "wide"
            else:
                c["zone"] = None
        else:
            c["zone"] = None

    # Find recommended strikes
    rec_put_strike = None
    rec_put = None
    for p in puts:
        d = p.get("delta")
        if d is not None and -0.35 <= d <= -0.18:
            if rec_put is None or abs(d - (-0.25)) < abs(rec_put["delta"] - (-0.25)):
                rec_put = p
                rec_put_strike = p["strike"]

    rec_call_strike = None
    rec_call = None
    for c in calls:
        d = c.get("delta")
        if d is not None and 0.18 <= d <= 0.35:
            if rec_call is None or abs(d - 0.25) < abs(rec_call["delta"] - 0.25):
                rec_call = c
                rec_call_strike = c["strike"]

    # Annual ROC for recommended put
    rec_put_roc = None
    if rec_put and rec_put_strike and rec_put_strike > 0:
        prem = rec_put["mid"] if rec_put["mid"] > 0 else rec_put["last"]
        if prem > 0 and dte > 0:
            rec_put_roc = round(prem / rec_put_strike * (365 / dte) * 100, 1)

    return JSONResponse({
        "ticker": ticker,
        "expiry": expiry,
        "dte": dte,
        "spot": spot,
        "puts": puts,
        "calls": calls,
        "expirations": expirations,
        "recommended": {
            "put_strike": rec_put_strike,
            "put_delta": rec_put["delta"] if rec_put else None,
            "put_premium": rec_put["mid"] if rec_put and rec_put["mid"] > 0 else (rec_put["last"] if rec_put else None),
            "put_ann_roc": rec_put_roc,
            "call_strike": rec_call_strike,
            "call_delta": rec_call["delta"] if rec_call else None,
            "call_premium": rec_call["mid"] if rec_call and rec_call["mid"] > 0 else (rec_call["last"] if rec_call else None),
        },
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

    # ── Trade signals (overlay markers on chart) ──
    signals = []
    if not intraday and len(close) > 50:
        sma200_s = close.rolling(200).mean()
        # IV rank proxy (rolling 30d vol rank over 180d)
        log_ret = np.log(close / close.shift(1))
        rv30 = log_ret.rolling(30).std() * np.sqrt(252)
        rv_rank = rv30.rolling(180).apply(
            lambda x: (x.iloc[-1] - x.min()) / (x.max() - x.min()) * 100
            if x.max() != x.min() else 50, raw=False)

        for i in range(1, len(close)):
            dt = close.index[i]
            p = float(close.iloc[i])
            r = float(rsi.iloc[i]) if i < len(rsi) else 50
            r_prev = float(rsi.iloc[i-1]) if i-1 < len(rsi) else 50
            sma = float(sma200_s.iloc[i]) if not pd.isna(sma200_s.iloc[i]) else p
            ivr = float(rv_rank.iloc[i]) if i < len(rv_rank) and not pd.isna(rv_rank.iloc[i]) else 50

            # SELL PUT signal: RSI crosses below 30 + above 200 SMA + IVR > 30
            if r < 30 and r_prev >= 30 and p > sma and ivr > 30:
                signals.append({
                    "time": fmt_time(dt), "position": "belowBar",
                    "color": "#22c55e", "shape": "arrowUp",
                    "text": f"SELL PUT (RSI {r:.0f}, IVR {ivr:.0f})",
                })
            # BUY STOCK signal: RSI crosses below 25 + above 200 SMA + IVR < 25
            elif r < 25 and r_prev >= 25 and p > sma:
                signals.append({
                    "time": fmt_time(dt), "position": "belowBar",
                    "color": "#3b82f6", "shape": "arrowUp",
                    "text": f"BUY (RSI {r:.0f}, oversold)",
                })
            # ACCUMULATE: price touches 200 SMA from above (within 1%)
            elif abs(p - sma) / sma < 0.01 and p > sma * 0.99:
                prev_dist = abs(float(close.iloc[i-1]) - sma) / sma
                if prev_dist > 0.02:
                    signals.append({
                        "time": fmt_time(dt), "position": "belowBar",
                        "color": "#a855f7", "shape": "circle",
                        "text": "200 SMA support",
                    })
            # STAND ASIDE: RSI crosses above 70 (overbought)
            elif r > 70 and r_prev <= 70:
                signals.append({
                    "time": fmt_time(dt), "position": "aboveBar",
                    "color": "#eab308", "shape": "arrowDown",
                    "text": f"OVERBOUGHT (RSI {r:.0f})",
                })
            # SELL CALL: RSI crosses above 75 (very overbought, sell CC aggressively)
            elif r > 75 and r_prev <= 75:
                signals.append({
                    "time": fmt_time(dt), "position": "aboveBar",
                    "color": "#ef4444", "shape": "arrowDown",
                    "text": f"SELL CALL (RSI {r:.0f})",
                })

    # ── Earnings dates ──
    earnings = []
    if not intraday:
        try:
            tk = yf.Ticker(ticker)
            ed = tk.earnings_dates
            if ed is not None and len(ed) > 0:
                for dt_idx, row in ed.iterrows():
                    try:
                        edate = pd.Timestamp(dt_idx).tz_localize(None).strftime("%Y-%m-%d")
                    except Exception:
                        edate = str(dt_idx)[:10]
                    eps_est = row.get("EPS Estimate")
                    eps_act = row.get("Reported EPS")
                    surprise = row.get("Surprise(%)")
                    def safe_num(v):
                        try:
                            f = float(v)
                            return round(f, 2) if f == f else None
                        except Exception:
                            return None
                    is_upcoming = safe_num(eps_act) is None
                    earnings.append({
                        "time": edate,
                        "eps_estimate": safe_num(eps_est),
                        "eps_actual": safe_num(eps_act),
                        "surprise_pct": safe_num(surprise),
                        "upcoming": is_upcoming,
                    })
        except Exception:
            pass

    # ── Volume profile (price bins with volume) ──
    vol_profile = []
    if not intraday and len(close) > 20:
        prices = close.values
        volumes = df["Volume"].values if "Volume" in df.columns else np.zeros(len(close))
        price_min, price_max = float(np.nanmin(prices)), float(np.nanmax(prices))
        if price_max > price_min:
            n_bins = 30
            bin_size = (price_max - price_min) / n_bins
            for i in range(n_bins):
                lo = price_min + i * bin_size
                hi = lo + bin_size
                mask = (prices >= lo) & (prices < hi)
                total_vol = float(np.nansum(volumes[mask]))
                vol_profile.append({
                    "price": round((lo + hi) / 2, 2),
                    "volume": int(total_vol),
                    "lo": round(lo, 2),
                    "hi": round(hi, 2),
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
        "signals": signals,
        "earnings": earnings,
        "volume_profile": vol_profile,
    })


@app.get("/api/heatmap")
async def api_heatmap():
    """Return sector-level heatmap data from latest scan."""
    global _latest_scan
    scan = _latest_scan
    if not scan:
        scan = _load_latest_from_disk()
    if not scan or not scan.get("tickers"):
        return JSONResponse({"error": "Run a scan first"}, status_code=400)

    tickers = [t for t in scan["tickers"] if "error" not in t]

    # Group by sector
    sectors = {}
    for t in tickers:
        sec = t.get("sector", "Other")
        if sec not in sectors:
            sectors[sec] = {"tickers": [], "total_ivr": 0, "total_rsi": 0,
                            "total_chg": 0, "count": 0, "sell_put": 0,
                            "buy_stock": 0, "stand_aside": 0}
        s = sectors[sec]
        s["tickers"].append({
            "ticker": t["ticker"],
            "price": t.get("price", 0),
            "day_change_pct": t.get("day_change_pct", 0),
            "iv_rank": t.get("iv_rank", 0),
            "rsi_14": t.get("rsi_14", 50),
            "entry_action": t.get("entry_action", ""),
            "csp_ann_roc_pct": t.get("csp_ann_roc_pct", 0),
        })
        s["total_ivr"] += t.get("iv_rank", 0)
        s["total_rsi"] += t.get("rsi_14", 50)
        s["total_chg"] += t.get("day_change_pct", 0)
        s["count"] += 1
        action = t.get("entry_action", "")
        if action == "SELL_PUT": s["sell_put"] += 1
        elif action == "BUY_STOCK": s["buy_stock"] += 1
        else: s["stand_aside"] += 1

    result = []
    for sec, s in sectors.items():
        n = s["count"]
        avg_ivr = s["total_ivr"] / n if n else 0
        avg_rsi = s["total_rsi"] / n if n else 50
        avg_chg = s["total_chg"] / n if n else 0
        # Sector health: oversold/neutral/overbought
        if avg_rsi < 35:
            health = "OVERSOLD"
        elif avg_rsi > 65:
            health = "OVERBOUGHT"
        else:
            health = "NEUTRAL"

        result.append({
            "sector": sec,
            "count": n,
            "avg_ivr": round(avg_ivr, 1),
            "avg_rsi": round(avg_rsi, 1),
            "avg_change_pct": round(avg_chg, 2),
            "health": health,
            "sell_put": s["sell_put"],
            "buy_stock": s["buy_stock"],
            "stand_aside": s["stand_aside"],
            "tickers": sorted(s["tickers"], key=lambda x: x["iv_rank"], reverse=True),
        })

    result.sort(key=lambda x: x["avg_ivr"], reverse=True)
    return JSONResponse({"sectors": result})


@app.post("/api/chat")
async def api_chat(request: Request):
    """Chat with Gemini about a ticker using live scan data as context."""
    if not GEMINI_API_KEY:
        return JSONResponse({"error": "GEMINI_API_KEY not set"}, status_code=500)

    body = await request.json()
    message = body.get("message", "")
    ticker = body.get("ticker")
    history = body.get("history", [])

    # Build context from scan data — check memory, disk, or inline from browser
    context_parts = []
    scan = _latest_scan or _load_latest_from_disk()
    # Also accept ticker data passed from the browser
    ticker_data = body.get("ticker_data")
    if ticker_data:
        context_parts.append(f"Current scan data for {ticker}:\n{__import__('json').dumps(ticker_data, indent=2)}")
    elif ticker and scan:
        t = next((x for x in scan.get("tickers", []) if x.get("ticker") == ticker), None)
        if t:
            context_parts.append(f"Current scan data for {ticker}:\n{__import__('json').dumps(t, indent=2)}")

    from dashboard.gemini_prompt import SYSTEM_PROMPT
    system_prompt = SYSTEM_PROMPT

    # Build Gemini messages
    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)

    contents = []
    for h in history[-10:]:  # last 10 messages for context window
        contents.append(genai.types.Content(
            role=h["role"],
            parts=[genai.types.Part(text=h["text"])],
        ))

    # Add current message with context
    user_text = message
    if context_parts:
        user_text = "\n\n".join(context_parts) + "\n\nUser question: " + message

    contents.append(genai.types.Content(
        role="user",
        parts=[genai.types.Part(text=user_text)],
    ))

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3,
                max_output_tokens=1024,
            ),
        )
        reply = response.text
    except Exception as e:
        reply = f"Gemini error: {str(e)}"

    return JSONResponse({"reply": reply})


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
