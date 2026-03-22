"""
Wheel Strategy Study — Real Market Data (Yahoo Finance)
========================================================

Downloads 5+ years of real price data via yfinance and runs the full
wheel strategy parameter study, producing CSV results, equity curves,
and a comprehensive summary report.

Tickers selected to cover different wheel profiles:
  - AAPL  : Blue-chip tech (growth)
  - AMD   : High-IV semiconductor (volatile growth)
  - JPM   : Financials, solid dividend
  - KO    : Dividend aristocrat (stable)
  - T     : Low-priced, high yield, range-bound
  - IWM   : Small-cap ETF
  - QQQM  : Nasdaq-100 mini ETF
  - SCHD  : Dividend-focused ETF

Usage:
    python wheel_study_real.py                    # Run all tickers
    python wheel_study_real.py --tickers AAPL AMD # Run specific tickers
    python wheel_study_real.py --years 3          # Use 3 years of data
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import io

try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance is required. Install with: pip install yfinance")
    sys.exit(1)

# Fix Windows console encoding for Unicode characters
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from wheel_backtest import (
    BacktestConfig,
    BacktestResult,
    WheelBacktester,
)
from wheel_study import (
    STRIKE_CONFIGS,
    DTE_OPTIONS,
    ROLL_CONFIGS,
    PERIOD_MAP,
    print_summary_tables,
    generate_charts,
)


# =============================================================================
# Default tickers — representative wheel candidates
# =============================================================================

DEFAULT_TICKERS = [
    "AAPL",   # Blue-chip tech
    "AMD",    # High-IV semiconductor
    "JPM",    # Financials + dividend
    "KO",     # Dividend aristocrat (stable)
    "T",      # Low-priced, high yield
    "IWM",    # Small-cap ETF
    "QQQM",   # Nasdaq-100 mini ETF
    "SCHD",   # Dividend ETF
]


# =============================================================================
# Data download
# =============================================================================

def download_prices(ticker: str, years: int = 6) -> pd.Series:
    """Download daily closing prices from Yahoo Finance.

    Downloads extra data (6 years) to ensure full 5-year coverage
    after the vol lookback window.
    """
    end = datetime.now()
    start = end - timedelta(days=years * 365 + 30)

    print(f"  Downloading {ticker} from {start.date()} to {end.date()}...")
    data = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                       end=end.strftime("%Y-%m-%d"), progress=False)

    if data.empty:
        raise ValueError(f"No data returned for {ticker}")

    # Handle multi-level columns from yfinance
    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
    else:
        close = data["Close"]

    close = close.dropna()
    close.name = "Close"
    print(f"  Got {len(close)} trading days ({close.index[0].date()} to {close.index[-1].date()})")
    return close


# =============================================================================
# Study runner (real data version)
# =============================================================================

def run_real_study(
    prices: pd.Series,
    ticker: str,
    output_dir: str = "results_real",
) -> pd.DataFrame:
    """Run the full parameter study on real price data."""
    os.makedirs(output_dir, exist_ok=True)
    records = []
    total_days = len(prices)

    for period_name, period_days in PERIOD_MAP.items():
        min_needed = period_days + 60
        if total_days < min_needed:
            print(f"  Skipping {period_name}: need {min_needed} days, have {total_days}")
            continue

        period_prices = prices.iloc[-period_days:]

        for strike_name, strike_params in STRIKE_CONFIGS.items():
            for dte in DTE_OPTIONS:
                for roll_name, roll_params in ROLL_CONFIGS.items():
                    config_kwargs = {
                        **strike_params,
                        **roll_params,
                        "dte": dte,
                        "cc_otm_pct": strike_params.get("otm_pct", 0.0),
                    }

                    config = BacktestConfig(**config_kwargs)
                    try:
                        bt = WheelBacktester(period_prices.copy(), config, ticker)
                        result = bt.run()

                        records.append({
                            "ticker": ticker,
                            "period": period_name,
                            "period_start": result.start_date,
                            "period_end": result.end_date,
                            "strike": strike_name,
                            "dte": dte,
                            "roll": roll_name,
                            "total_return_pct": round(result.total_return_pct, 2),
                            "annual_return_pct": round(result.annualized_return_pct, 2),
                            "max_drawdown_pct": round(result.max_drawdown_pct, 2),
                            "total_trades": result.total_trades,
                            "csp_trades": result.csp_trades,
                            "cc_trades": result.cc_trades,
                            "win_rate": round(result.win_rate, 1),
                            "premium_collected": round(result.total_premium_collected, 2),
                            "completed_cycles": result.completed_cycles,
                            "avg_cycle_days": round(result.avg_cycle_days, 0),
                            "initial_capital": round(result.initial_capital, 2),
                            "final_capital": round(result.final_capital, 2),
                        })
                    except Exception as e:
                        print(f"    ERROR: {period_name}/{strike_name}/{dte}DTE/{roll_name}: {e}")

    df = pd.DataFrame(records)
    if not df.empty:
        csv_path = os.path.join(output_dir, f"{ticker}_study_results.csv")
        df.to_csv(csv_path, index=False)
        print(f"  Results saved: {csv_path}")

    return df


# =============================================================================
# Equity curve comparison (real data)
# =============================================================================

def run_equity_comparison_real(
    prices: pd.Series,
    ticker: str,
    output_dir: str = "results_real",
):
    """Run key configs and plot equity curves vs buy & hold."""
    os.makedirs(output_dir, exist_ok=True)

    key_configs = [
        ("ATM 30DTE Hold", BacktestConfig(
            strike_method="atm", dte=30,
            roll_method="hold_to_expiry")),
        ("3%OTM 45DTE Roll@7d", BacktestConfig(
            strike_method="otm_pct", otm_pct=0.03, dte=45,
            roll_method="roll_before_expiry", roll_days_before=7,
            cc_otm_pct=0.03)),
        ("5%OTM 45DTE Roll@50%", BacktestConfig(
            strike_method="otm_pct", otm_pct=0.05, dte=45,
            roll_method="roll_at_profit", roll_profit_pct=0.50,
            cc_otm_pct=0.05)),
        ("ATM 60DTE Roll@7d", BacktestConfig(
            strike_method="atm", dte=60,
            roll_method="roll_before_expiry", roll_days_before=7)),
        ("10%OTM 30DTE Hold", BacktestConfig(
            strike_method="otm_pct", otm_pct=0.10, dte=30,
            roll_method="hold_to_expiry", cc_otm_pct=0.10)),
    ]

    fig, ax = plt.subplots(figsize=(14, 8))
    vol_lookback = 30

    # Buy & Hold benchmark
    bh_prices = prices.iloc[vol_lookback:]
    bh_normalized = bh_prices / bh_prices.iloc[0] * 100
    ax.plot(bh_normalized.index, bh_normalized.values,
            label="Buy & Hold", linestyle="--", linewidth=2, color="black")

    for name, config in key_configs:
        try:
            bt = WheelBacktester(prices.copy(), config, ticker)
            result = bt.run()
            eq = result.equity_curve / result.equity_curve.iloc[0] * 100
            ax.plot(eq.index, eq.values,
                    label=f"{name} ({result.annualized_return_pct:.1f}% ann.)")
        except Exception as e:
            print(f"  Skipping {name}: {e}")

    ax.set_title(f"{ticker}: Wheel Strategy vs Buy & Hold (Real Data)", fontsize=14)
    ax.set_xlabel("Date")
    ax.set_ylabel("Normalized Equity (base=100)")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)

    chart_path = os.path.join(output_dir, f"{ticker}_equity_comparison.png")
    plt.tight_layout()
    plt.savefig(chart_path, dpi=150)
    plt.close(fig)
    print(f"  Equity chart saved: {chart_path}")


# =============================================================================
# Report generation
# =============================================================================

def generate_report(all_dfs: list[pd.DataFrame], output_dir: str = "results_real"):
    """Generate a combined cross-ticker summary report."""
    if not all_dfs:
        return

    combined = pd.concat(all_dfs, ignore_index=True)
    combined_path = os.path.join(output_dir, "all_tickers_real_study.csv")
    combined.to_csv(combined_path, index=False)

    print(f"\n{'=' * 80}")
    print(f"  REAL DATA — CROSS-TICKER COMPARISON")
    print(f"{'=' * 80}")

    # Best config per ticker per period
    for period in sorted(combined["period"].unique(), key=lambda x: PERIOD_MAP.get(x, 0)):
        print(f"\n  {period} — Best Configuration per Ticker:")
        print(f"  {'Ticker':<8} {'Strike':<10} {'DTE':>4} {'Roll':<20} "
              f"{'Ann.Ret%':>9} {'MaxDD%':>8} {'WinRate':>8} {'Cycles':>7}")
        print(f"  {'-' * 78}")

        period_df = combined[combined["period"] == period]
        if period_df.empty:
            print(f"  (no data for this period)")
            continue

        best_per_ticker = period_df.loc[
            period_df.groupby("ticker")["annual_return_pct"].idxmax()
        ].sort_values("annual_return_pct", ascending=False)

        for _, r in best_per_ticker.iterrows():
            print(f"  {r['ticker']:<8} {r['strike']:<10} {r['dte']:>4} "
                  f"{r['roll']:<20} {r['annual_return_pct']:>8.1f}% "
                  f"{r['max_drawdown_pct']:>7.1f}% {r['win_rate']:>7.1f}% "
                  f"{r['completed_cycles']:>7}")

    # Overall aggregate by strike
    print(f"\n{'─' * 80}")
    print(f"  AGGREGATE: Average by Strike (all tickers, all periods)")
    print(f"{'─' * 80}")
    strike_agg = combined.groupby("strike").agg({
        "annual_return_pct": "mean",
        "max_drawdown_pct": "mean",
        "win_rate": "mean",
        "completed_cycles": "mean",
    }).round(2)
    print(strike_agg.to_string())

    # Overall aggregate by roll method
    print(f"\n{'─' * 80}")
    print(f"  AGGREGATE: Average by Roll Method (all tickers, all periods)")
    print(f"{'─' * 80}")
    roll_agg = combined.groupby("roll").agg({
        "annual_return_pct": "mean",
        "max_drawdown_pct": "mean",
        "win_rate": "mean",
        "premium_collected": "mean",
    }).round(2)
    print(roll_agg.to_string())

    # Overall aggregate by DTE
    print(f"\n{'─' * 80}")
    print(f"  AGGREGATE: Average by DTE (all tickers, all periods)")
    print(f"{'─' * 80}")
    dte_agg = combined.groupby("dte").agg({
        "annual_return_pct": "mean",
        "max_drawdown_pct": "mean",
        "win_rate": "mean",
        "total_trades": "mean",
    }).round(2)
    print(dte_agg.to_string())

    # Wheel vs Buy & Hold comparison
    print(f"\n{'─' * 80}")
    print(f"  WHEEL vs BUY & HOLD COMPARISON (5Y period)")
    print(f"{'─' * 80}")
    fiveY = combined[combined["period"] == "5Y"]
    if not fiveY.empty:
        print(f"  {'Ticker':<8} {'Best Wheel Ann%':>16} {'Worst Wheel Ann%':>17} "
              f"{'Avg Wheel Ann%':>15} {'Median Ann%':>12}")
        print(f"  {'-' * 70}")
        for ticker in sorted(fiveY["ticker"].unique()):
            tdf = fiveY[fiveY["ticker"] == ticker]
            print(f"  {ticker:<8} {tdf['annual_return_pct'].max():>15.1f}% "
                  f"{tdf['annual_return_pct'].min():>16.1f}% "
                  f"{tdf['annual_return_pct'].mean():>14.1f}% "
                  f"{tdf['annual_return_pct'].median():>11.1f}%")

    print(f"\n  Combined results saved to: {combined_path}")
    return combined


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Wheel Strategy Study with Real Yahoo Finance Data")
    parser.add_argument("--tickers", nargs="+", default=None,
                        help="Tickers to study (default: curated list)")
    parser.add_argument("--years", type=int, default=6,
                        help="Years of data to download (default: 6 for 5Y coverage)")
    parser.add_argument("--output", type=str, default="results_real",
                        help="Output directory")
    args = parser.parse_args()

    tickers = args.tickers or DEFAULT_TICKERS
    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), args.output
    )
    os.makedirs(output_dir, exist_ok=True)

    print(f"Wheel Strategy Study — Real Market Data")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Data window: ~{args.years} years")
    print(f"Output: {output_dir}\n")

    all_dfs = []
    failed_tickers = []

    for ticker in tickers:
        print(f"\n{'=' * 70}")
        print(f"  {ticker}")
        print(f"{'=' * 70}")

        try:
            prices = download_prices(ticker, years=args.years)

            # Run parameter study
            df = run_real_study(prices, ticker, output_dir)
            if not df.empty:
                all_dfs.append(df)

                # Per-ticker summary
                print_summary_tables(df)

                # Generate charts
                generate_charts(df, output_dir)

                # Equity curve comparison
                run_equity_comparison_real(prices, ticker, output_dir)

        except Exception as e:
            print(f"  FAILED: {e}")
            failed_tickers.append((ticker, str(e)))

    # Cross-ticker report
    if all_dfs:
        generate_report(all_dfs, output_dir)

    if failed_tickers:
        print(f"\n  FAILED TICKERS:")
        for t, err in failed_tickers:
            print(f"    {t}: {err}")

    print(f"\nDone. Results in: {output_dir}/")


if __name__ == "__main__":
    main()
