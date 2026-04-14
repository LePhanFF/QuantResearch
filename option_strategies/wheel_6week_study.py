"""
6-Week Backstudy of the Top-10 Wheel Tickers
=============================================

For each of the top 10 wheel candidates defined in ``wheel_criteria`` this
script produces a short-horizon report covering the last 6 weeks:

  - Realized price behavior (return, vol, max drawdown, trend vs 200 SMA)
  - A simulated cash-secured put (CSP) sold ~6 weeks ago, 30 DTE, 5% OTM,
    held to expiry (pricing done with Black-Scholes + 30d HV)
  - Today's trade signal from ``wheel_criteria.evaluate()``

Futures tickers /MES and /MNQ are mapped to the Yahoo symbols ES=F and
NQ=F (same underlying index; the micros are 1/10th the multiplier of the
minis). We annotate notional in terms of the micro contract.

Outputs go into ``results/6week_study/``:

  - ``top10_6week_report.csv``  — all metrics per ticker
  - ``top10_6week_report.txt``  — human-readable report
  - ``top10_6week_summary.png`` — 6-week return + CSP outcome chart

Run:
    python wheel_6week_study.py
"""

from __future__ import annotations

import io
import math
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance is required. Install with: pip install yfinance")
    sys.exit(1)

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from option_pricing import black_scholes_put, historical_volatility
from wheel_criteria import TOP_10_WHEEL_TICKERS, WheelTicker, evaluate


# =============================================================================
# Config
# =============================================================================

# Map our canonical tickers to yfinance symbols. Futures use the full-sized
# mini since the micros share the same underlying index level.
YF_SYMBOL = {
    "/MES": "ES=F",
    "/MNQ": "NQ=F",
}

LOOKBACK_WEEKS = 6
CSP_DTE_DAYS = 30            # calendar DTE for the simulated CSP
CSP_OTM_PCT = 0.05           # 5% OTM put
RISK_FREE = 0.045
VOL_LOOKBACK_DAYS = 30
DATA_MONTHS = 10             # download enough history for 200-SMA context
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "results",
    "6week_study",
)


# =============================================================================
# Data loading
# =============================================================================


def download_history(symbol: str, months: int = DATA_MONTHS) -> pd.Series:
    """Download daily closes from yfinance."""
    end = datetime.now()
    start = end - timedelta(days=months * 31)
    data = yf.download(
        symbol,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=False,
    )
    if data.empty:
        raise ValueError(f"No data for {symbol}")

    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
    else:
        close = data["Close"]

    close = close.dropna()
    close.name = symbol
    return close


# =============================================================================
# Analytics
# =============================================================================


@dataclass
class TickerReport:
    ticker: str
    yf_symbol: str
    sector: str
    start_date: str
    end_date: str
    start_price: float
    end_price: float
    period_return_pct: float
    realized_vol_6w_pct: float   # annualized, window only
    realized_vol_30d_pct: float  # annualized, 30d
    max_drawdown_pct: float
    above_200_sma: bool
    dist_from_200_sma_pct: float
    iv_rank_proxy: float

    # CSP simulation
    csp_entry_date: str
    csp_strike: float
    csp_premium: float
    csp_spot_at_entry: float
    csp_expiry_date: str
    csp_spot_at_expiry: float
    csp_outcome: str
    csp_pnl_per_contract: float
    csp_return_on_cash_pct: float
    csp_annualized_return_pct: float

    # Today's action
    today_action: str
    today_reason: str


def _max_drawdown(prices: np.ndarray) -> float:
    """Max drawdown (negative %) over the window."""
    if len(prices) == 0:
        return 0.0
    peak = np.maximum.accumulate(prices)
    dd = (prices - peak) / peak
    return float(dd.min() * 100)


def _iv_rank_proxy(prices: pd.Series, window: int = 180) -> float:
    """
    Approximate IV rank using realized vol rank over the lookback.

    We compute rolling 30-day realized vol across `window` days and rank
    today's 30-day vol within its own range. Not a true IV rank, but a
    reasonable stand-in when we don't have option-chain data.
    """
    returns = np.log(prices / prices.shift(1)).dropna()
    if len(returns) < 40:
        return 50.0
    rv = returns.rolling(30).std() * math.sqrt(252) * 100
    rv = rv.dropna().tail(window)
    if len(rv) < 5:
        return 50.0
    current = rv.iloc[-1]
    lo, hi = rv.min(), rv.max()
    if hi - lo < 1e-9:
        return 50.0
    return float((current - lo) / (hi - lo) * 100)


def _find_index_nearest(index: pd.DatetimeIndex, target: datetime) -> int:
    """Return position of trading day closest to target date."""
    target_ts = pd.Timestamp(target)
    diffs = np.abs(index - target_ts)
    return int(np.argmin(diffs))


def analyze_ticker(t: WheelTicker) -> Optional[TickerReport]:
    symbol = YF_SYMBOL.get(t.ticker, t.ticker)
    print(f"  {t.ticker:<6} -> {symbol}: downloading...", end=" ", flush=True)
    try:
        prices = download_history(symbol)
    except Exception as e:
        print(f"FAILED ({e})")
        return None

    if len(prices) < 50:
        print(f"insufficient data ({len(prices)} days)")
        return None

    # Identify 6-week window
    end_idx = len(prices) - 1
    end_date = prices.index[end_idx]
    start_target = end_date - pd.Timedelta(weeks=LOOKBACK_WEEKS)
    start_idx = _find_index_nearest(prices.index, start_target.to_pydatetime())

    window = prices.iloc[start_idx : end_idx + 1]
    start_price = float(window.iloc[0])
    end_price = float(window.iloc[-1])
    period_return = (end_price / start_price - 1) * 100

    # Realized vol
    win_returns = np.log(window / window.shift(1)).dropna().values
    rv_6w = float(np.std(win_returns, ddof=1) * math.sqrt(252) * 100) if len(win_returns) > 1 else 0.0
    rv_30d = historical_volatility(prices.values[-VOL_LOOKBACK_DAYS:], VOL_LOOKBACK_DAYS) * 100

    max_dd = _max_drawdown(window.values)

    # 200-day SMA status
    sma_200 = prices.rolling(200).mean().iloc[-1]
    if pd.isna(sma_200):
        sma_200 = prices.mean()
    above_200 = bool(end_price > sma_200)
    dist_200 = (end_price / float(sma_200) - 1) * 100

    # IV rank proxy
    ivr_proxy = _iv_rank_proxy(prices)

    # --- Simulate a CSP sold 6 weeks ago ---
    entry_idx = start_idx
    entry_price = start_price

    # HV at entry: use 30-day lookback BEFORE entry
    hv_window_start = max(0, entry_idx - VOL_LOOKBACK_DAYS)
    hv_at_entry = historical_volatility(
        prices.values[hv_window_start : entry_idx + 1], VOL_LOOKBACK_DAYS
    )
    if hv_at_entry <= 0:
        hv_at_entry = 0.20  # fallback

    strike = round(entry_price * (1 - CSP_OTM_PCT), 2)
    T = CSP_DTE_DAYS / 365
    quote = black_scholes_put(entry_price, strike, T, RISK_FREE, hv_at_entry * 1.2)
    premium = max(quote.price, 0.01)

    # Find expiry index (30 calendar days after entry)
    expiry_target = prices.index[entry_idx] + pd.Timedelta(days=CSP_DTE_DAYS)
    if expiry_target > prices.index[-1]:
        # Still open — mark-to-market at current price
        expiry_idx = end_idx
        outcome = "open"
    else:
        expiry_idx = _find_index_nearest(prices.index, expiry_target.to_pydatetime())
        outcome = "assigned" if prices.iloc[expiry_idx] <= strike else "expired_otm"

    spot_at_expiry = float(prices.iloc[expiry_idx])

    # Per-contract multiplier: 100 for stocks/ETFs, 5 for /MES, 2 for /MNQ
    mult = t.multiplier

    # PnL per contract (in dollars)
    if outcome == "expired_otm":
        pnl_per_contract = premium * mult
    elif outcome == "assigned":
        # Unrealized loss = (spot - strike) per point + keep premium
        pnl_per_contract = (spot_at_expiry - strike + premium) * mult
    else:  # open — mark-to-market
        days_elapsed = max(1, (prices.index[-1] - prices.index[entry_idx]).days)
        remaining_days = CSP_DTE_DAYS - days_elapsed
        if remaining_days > 0:
            T_now = remaining_days / 365
            current_put = black_scholes_put(
                spot_at_expiry, strike, T_now, RISK_FREE, hv_at_entry * 1.2
            ).price
        else:
            current_put = max(strike - spot_at_expiry, 0)
        pnl_per_contract = (premium - current_put) * mult

    # Cash at risk: full notional for equities, SPAN margin for futures
    if t.instrument == "future_option":
        cash_secured = t.margin_per_contract or (strike * mult)
    else:
        cash_secured = strike * mult
    roc = pnl_per_contract / cash_secured * 100 if cash_secured > 0 else 0
    days_held = max(1, (prices.index[expiry_idx] - prices.index[entry_idx]).days)
    ann_roc = roc * (365 / days_held)

    # --- Today's trade signal ---
    sig = evaluate(
        t,
        current_iv_rank=ivr_proxy,
        above_200_sma=above_200,
        earnings_within_dte=False,  # we don't have an earnings calendar
        in_strong_uptrend=(period_return > 8 and above_200),
    )

    print(f"ok ({outcome}, {period_return:+.1f}%)")

    return TickerReport(
        ticker=t.ticker,
        yf_symbol=symbol,
        sector=t.sector,
        start_date=str(prices.index[entry_idx].date()),
        end_date=str(prices.index[end_idx].date()),
        start_price=round(start_price, 2),
        end_price=round(end_price, 2),
        period_return_pct=round(period_return, 2),
        realized_vol_6w_pct=round(rv_6w, 2),
        realized_vol_30d_pct=round(rv_30d, 2),
        max_drawdown_pct=round(max_dd, 2),
        above_200_sma=above_200,
        dist_from_200_sma_pct=round(dist_200, 2),
        iv_rank_proxy=round(ivr_proxy, 1),
        csp_entry_date=str(prices.index[entry_idx].date()),
        csp_strike=strike,
        csp_premium=round(premium, 2),
        csp_spot_at_entry=round(entry_price, 2),
        csp_expiry_date=str(prices.index[expiry_idx].date()),
        csp_spot_at_expiry=round(spot_at_expiry, 2),
        csp_outcome=outcome,
        csp_pnl_per_contract=round(pnl_per_contract, 2),
        csp_return_on_cash_pct=round(roc, 2),
        csp_annualized_return_pct=round(ann_roc, 2),
        today_action=sig.action,
        today_reason=sig.reason,
    )


# =============================================================================
# Reporting
# =============================================================================


def write_csv(reports: list[TickerReport], path: str) -> None:
    df = pd.DataFrame([asdict(r) for r in reports])
    df.to_csv(path, index=False)


def write_text_report(reports: list[TickerReport], path: str) -> str:
    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d")
    lines.append("=" * 100)
    lines.append(f"  TOP 10 WHEEL TICKERS — 6-WEEK BACKSTUDY  ({now})")
    lines.append("=" * 100)
    lines.append("")

    # Market action table
    lines.append("  MARKET ACTION (last 6 weeks)")
    lines.append("  " + "-" * 96)
    lines.append(
        f"  {'Ticker':<7} {'Sector':<16} {'Start':>10} {'End':>10} "
        f"{'Return%':>9} {'Vol6w%':>8} {'MaxDD%':>8} {'vs200SMA':>10}"
    )
    lines.append("  " + "-" * 96)
    for r in reports:
        lines.append(
            f"  {r.ticker:<7} {r.sector:<16} "
            f"{r.start_price:>10.2f} {r.end_price:>10.2f} "
            f"{r.period_return_pct:>+8.2f}% {r.realized_vol_6w_pct:>7.1f}% "
            f"{r.max_drawdown_pct:>7.2f}% {r.dist_from_200_sma_pct:>+9.1f}%"
        )

    # CSP simulation
    lines.append("")
    lines.append("  SIMULATED CSP (sold 6 weeks ago, 5% OTM, 30 DTE, held to expiry)")
    lines.append("  " + "-" * 96)
    lines.append(
        f"  {'Ticker':<7} {'Strike':>9} {'Prem':>7} {'Spot@Exp':>10} "
        f"{'Outcome':<13} {'PnL/ctrct':>11} {'ROC%':>8} {'Ann%':>8}"
    )
    lines.append("  " + "-" * 96)
    for r in reports:
        lines.append(
            f"  {r.ticker:<7} {r.csp_strike:>9.2f} {r.csp_premium:>7.2f} "
            f"{r.csp_spot_at_expiry:>10.2f} {r.csp_outcome:<13} "
            f"${r.csp_pnl_per_contract:>10,.0f} "
            f"{r.csp_return_on_cash_pct:>+7.2f}% {r.csp_annualized_return_pct:>+7.1f}%"
        )

    # Totals
    total_pnl = sum(r.csp_pnl_per_contract for r in reports)
    winners = sum(1 for r in reports if r.csp_pnl_per_contract > 0)
    lines.append("  " + "-" * 96)
    lines.append(
        f"  Aggregate (1 ctrct each): PnL ${total_pnl:,.0f}  |  "
        f"Winners {winners}/{len(reports)}"
    )

    # Today's signals
    lines.append("")
    lines.append("  TODAY'S SIGNAL")
    lines.append("  " + "-" * 96)
    lines.append(f"  {'Ticker':<7} {'IVr(proxy)':>11} {'Action':<13} Reason")
    lines.append("  " + "-" * 96)
    for r in reports:
        lines.append(
            f"  {r.ticker:<7} {r.iv_rank_proxy:>10.0f}  "
            f"{r.today_action:<13} {r.today_reason}"
        )

    # Caveats
    lines.append("")
    lines.append("  NOTES")
    lines.append("  " + "-" * 96)
    lines.append("  * Premiums estimated via Black-Scholes using 30d historical vol * 1.2 IV")
    lines.append("    premium. Real-market premiums will differ, especially across earnings.")
    lines.append("  * IV rank is a realized-vol rank proxy across ~180 trading days.")
    lines.append("  * /MES and /MNQ use ES=F and NQ=F index levels. PnL shown is per MICRO")
    lines.append("    contract by scaling by the multiplier (5 and 2 respectively).")
    lines.append("  * No earnings calendar is used; confirm before acting on signals.")
    lines.append("=" * 100)

    text = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def write_chart(reports: list[TickerReport], path: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    tickers = [r.ticker for r in reports]
    returns = [r.period_return_pct for r in reports]
    csp_pnl = [r.csp_pnl_per_contract for r in reports]

    colors_r = ["#2ca02c" if x >= 0 else "#d62728" for x in returns]
    colors_p = ["#2ca02c" if x >= 0 else "#d62728" for x in csp_pnl]

    axes[0].barh(tickers, returns, color=colors_r)
    axes[0].set_title("6-Week Price Return (%)")
    axes[0].axvline(0, color="black", linewidth=0.8)
    axes[0].grid(True, alpha=0.3, axis="x")
    axes[0].invert_yaxis()

    axes[1].barh(tickers, csp_pnl, color=colors_p)
    axes[1].set_title("Simulated CSP PnL per Contract ($)")
    axes[1].axvline(0, color="black", linewidth=0.8)
    axes[1].grid(True, alpha=0.3, axis="x")
    axes[1].invert_yaxis()

    fig.suptitle(
        f"Top-10 Wheel Tickers: 6-Week Backstudy  ({datetime.now().strftime('%Y-%m-%d')})",
        fontsize=13,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"6-Week Wheel Backstudy — output: {OUTPUT_DIR}")
    print(f"Lookback: {LOOKBACK_WEEKS} weeks   CSP: {CSP_DTE_DAYS}DTE {CSP_OTM_PCT:.0%} OTM")
    print()

    reports: list[TickerReport] = []
    for t in TOP_10_WHEEL_TICKERS:
        try:
            r = analyze_ticker(t)
            if r is not None:
                reports.append(r)
        except Exception as e:
            print(f"  {t.ticker}: error — {e}")

    if not reports:
        print("No reports generated.")
        return

    csv_path = os.path.join(OUTPUT_DIR, "top10_6week_report.csv")
    txt_path = os.path.join(OUTPUT_DIR, "top10_6week_report.txt")
    png_path = os.path.join(OUTPUT_DIR, "top10_6week_summary.png")

    write_csv(reports, csv_path)
    text = write_text_report(reports, txt_path)
    write_chart(reports, png_path)

    print()
    print(text)
    print()
    print(f"CSV:    {csv_path}")
    print(f"Report: {txt_path}")
    print(f"Chart:  {png_path}")


if __name__ == "__main__":
    main()
