"""
Daily Wheel Strategy Scanner
=============================

Fetches live market data for all wheel tickers and produces a structured
JSON report with actionable signals for every phase of the wheel.
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from option_pricing import black_scholes_put, black_scholes_call, historical_volatility
from wheel_criteria import WHEEL_TICKERS, WheelTicker
from wheel_decision_engine import (
    evaluate_entry,
    manage_put,
    manage_shares,
    PutPosition,
    SharePosition,
)


RISK_FREE = 0.045
DATA_MONTHS = 10


def _download(symbol: str) -> pd.DataFrame:
    end = datetime.now()
    start = end - timedelta(days=DATA_MONTHS * 31)
    df = yf.download(symbol, start=start.strftime("%Y-%m-%d"),
                     end=end.strftime("%Y-%m-%d"), progress=False,
                     auto_adjust=False)
    if df.empty:
        raise ValueError(f"No data for {symbol}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _iv_rank_proxy(close: pd.Series, window: int = 180) -> float:
    rets = np.log(close / close.shift(1)).dropna()
    if len(rets) < 40:
        return 50.0
    rv = rets.rolling(30).std() * math.sqrt(252) * 100
    rv = rv.dropna().tail(window)
    if len(rv) < 5:
        return 50.0
    cur = rv.iloc[-1]
    lo, hi = rv.min(), rv.max()
    if hi - lo < 1e-9:
        return 50.0
    return float((cur - lo) / (hi - lo) * 100)


def _trend(close: pd.Series) -> str:
    sma20 = close.rolling(20).mean().iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]
    price = close.iloc[-1]
    if pd.isna(sma200):
        sma200 = close.mean()
    if price > sma20 > sma50 > sma200:
        return "STRONG_UP"
    if price > sma200:
        return "UP"
    if price < sma20 < sma50 < sma200:
        return "STRONG_DOWN"
    return "DOWN"


def scan_ticker(t: WheelTicker) -> dict:
    df = _download(t.ticker)
    close = df["Close"].dropna()

    price = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) > 1 else price
    day_chg = (price / prev - 1) * 100

    sma200_raw = close.rolling(200).mean().iloc[-1]
    sma200 = float(sma200_raw) if not pd.isna(sma200_raw) else float(close.mean())
    above_200 = price >= sma200
    pct_from_200 = (price / sma200 - 1) * 100
    ivr = _iv_rank_proxy(close)
    trend_label = _trend(close)
    hv30 = historical_volatility(close.values[-31:], 30)
    iv_est = hv30 * 1.2

    # 6-week metrics
    idx_6w = max(0, len(close) - 31)
    ret_6w = (price / float(close.iloc[idx_6w]) - 1) * 100
    win = close.iloc[idx_6w:]
    max_dd = float(((win - win.cummax()) / win.cummax()).min() * 100)

    # Entry signal
    entry = evaluate_entry(
        quality_score=t.quality_score,
        iv_rank=ivr,
        above_200_sma=above_200,
        pct_from_200_sma=pct_from_200,
        earnings_within_dte=False,
        in_strong_uptrend=(trend_label == "STRONG_UP"),
    )

    # CSP setup (5% OTM, ~35 DTE)
    csp_strike = round(price * 0.95, 2)
    T = 35 / 365
    csp_q = black_scholes_put(price, csp_strike, T, RISK_FREE, iv_est)
    csp_prem = max(csp_q.price, 0.01)
    csp_delta = abs(csp_q.delta)
    csp_ann_roc = (csp_prem / csp_strike) * (365 / 35) * 100

    # CC setup (if assigned at csp_strike)
    cost_basis = csp_strike - csp_prem
    cc_strike = round(price * 1.03, 2)
    cc_q = black_scholes_call(price, cc_strike, T, RISK_FREE, iv_est)
    cc_prem = max(cc_q.price, 0.01)

    # Put management
    put_dec = manage_put(PutPosition(
        ticker=t.ticker, strike=csp_strike,
        premium_collected=csp_prem, current_underlying=price,
        days_remaining=35, iv_rank=ivr,
        put_mark=csp_prem * 0.6,
        above_200_sma=above_200, earnings_before_expiry=False,
    ))

    # Share management
    share_dec = manage_shares(SharePosition(
        ticker=t.ticker, shares=100,
        cost_basis=cost_basis, current_price=price,
        iv_rank=ivr, above_200_sma=above_200,
        earnings_before_next_expiry=False,
        dividend_ex_date_before_expiry=False,
    ))

    return {
        "ticker": t.ticker, "name": t.name, "sector": t.sector,
        "instrument": t.instrument,
        "price": round(price, 2),
        "day_change_pct": round(day_chg, 2),
        "return_6w_pct": round(ret_6w, 2),
        "max_dd_6w_pct": round(max_dd, 2),
        "sma_200": round(sma200, 2),
        "above_200_sma": above_200,
        "pct_from_200_sma": round(pct_from_200, 2),
        "iv_rank": round(ivr, 1),
        "hv_30d": round(hv30 * 100, 1),
        "trend": trend_label,
        "entry_action": entry.action.value,
        "entry_reason": entry.reason,
        "entry_delta": entry.target_delta,
        "entry_dte": entry.target_dte,
        "csp_strike": csp_strike,
        "csp_premium": round(csp_prem, 2),
        "csp_delta": round(csp_delta, 3),
        "csp_ann_roc_pct": round(csp_ann_roc, 1),
        "csp_capital_required": round(csp_strike * 100, 0),
        "cc_strike": cc_strike,
        "cc_premium": round(cc_prem, 2),
        "cost_basis_if_assigned": round(cost_basis, 2),
        "put_mgmt_action": put_dec.action.value,
        "put_mgmt_reason": put_dec.reason,
        "share_mgmt_action": share_dec.action.value,
        "share_mgmt_reason": share_dec.reason,
        "share_mgmt_delta": share_dec.target_delta,
        "scan_time": datetime.now().isoformat(timespec="seconds"),
    }


def run_scan(tickers: list[WheelTicker] | None = None) -> list[dict]:
    tickers = tickers or WHEEL_TICKERS
    results = []
    for t in tickers:
        try:
            results.append(scan_ticker(t))
        except Exception as e:
            results.append({
                "ticker": t.ticker, "name": t.name,
                "error": str(e),
                "scan_time": datetime.now().isoformat(timespec="seconds"),
            })
    return results


def save_report(results: list[dict], output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"scan_{ts}.json")
    with open(path, "w") as f:
        json.dump({"generated": ts, "tickers": results}, f, indent=2)
    return path


if __name__ == "__main__":
    import io
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("Running daily wheel scan...")
    results = run_scan()
    for r in results:
        if "error" in r:
            print(f"  {r['ticker']:>5}: ERROR - {r['error']}")
        else:
            print(f"  {r['ticker']:>5} ${r['price']:>8.2f}  IVR:{r['iv_rank']:>5.1f}  "
                  f"{r['trend']:<12} -> {r['entry_action']}")
