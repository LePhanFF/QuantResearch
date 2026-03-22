"""
Wheel Strategy Parameter Study
===============================

Runs the wheel backtest across multiple configurations and time periods,
then compares results in a summary table and charts.

Studies:
  1. Strike selection: ATM vs 3% OTM vs 5% OTM vs 10% OTM
  2. DTE: 30 vs 45 vs 60 days
  3. Rolling: Hold-to-expiry vs Roll@50% profit vs Roll@7d before expiry
  4. Time periods: 1Y, 3Y, 5Y
  5. Per-ticker comparison across wheel candidates

Usage:
    python wheel_study.py                      # Run with synthetic data
    python wheel_study.py --data prices/       # Run with CSV files in folder
    python wheel_study.py --ticker AAPL.csv    # Run single ticker
"""

import argparse
import os
import sys
from itertools import product

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from wheel_backtest import (
    BacktestConfig,
    BacktestResult,
    WheelBacktester,
    generate_synthetic_prices,
    load_prices_csv,
)


# =============================================================================
# Study Configurations
# =============================================================================

STRIKE_CONFIGS = {
    "ATM": {"strike_method": "atm"},
    "3% OTM": {"strike_method": "otm_pct", "otm_pct": 0.03},
    "5% OTM": {"strike_method": "otm_pct", "otm_pct": 0.05},
    "10% OTM": {"strike_method": "otm_pct", "otm_pct": 0.10},
}

DTE_OPTIONS = [30, 45, 60]

ROLL_CONFIGS = {
    "Hold to Expiry": {"roll_method": "hold_to_expiry"},
    "Roll @50% Profit": {"roll_method": "roll_at_profit", "roll_profit_pct": 0.50},
    "Roll @75% Profit": {"roll_method": "roll_at_profit", "roll_profit_pct": 0.75},
    "Roll @7d Before": {"roll_method": "roll_before_expiry", "roll_days_before": 7},
}

PERIOD_MAP = {
    "1Y": 252,
    "3Y": 756,
    "5Y": 1260,
}


# =============================================================================
# Study Runner
# =============================================================================

def run_parameter_study(
    prices: pd.Series,
    ticker: str = "SYN",
    output_dir: str = "results",
) -> pd.DataFrame:
    """Run the full parameter study across strikes, DTEs, rolling, and periods.

    Returns a DataFrame with one row per (period, strike, dte, roll) combination.
    """
    os.makedirs(output_dir, exist_ok=True)
    records = []

    total_days = len(prices)

    for period_name, period_days in PERIOD_MAP.items():
        if total_days < period_days + 60:
            print(f"  Skipping {period_name}: not enough data "
                  f"({total_days} days < {period_days + 60} needed)")
            continue

        # Use the most recent N days
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
                        print(f"  ERROR: {period_name}/{strike_name}/{dte}DTE/{roll_name}: {e}")

    df = pd.DataFrame(records)
    if not df.empty:
        csv_path = os.path.join(output_dir, f"{ticker}_study_results.csv")
        df.to_csv(csv_path, index=False)
        print(f"\nResults saved to {csv_path}")

    return df


# =============================================================================
# Analysis & Reporting
# =============================================================================

def print_summary_tables(df: pd.DataFrame):
    """Print formatted summary tables from study results."""
    if df.empty:
        print("No results to display.")
        return

    ticker = df["ticker"].iloc[0]

    # --- By Period ---
    print(f"\n{'=' * 80}")
    print(f"  WHEEL STRATEGY STUDY: {ticker}")
    print(f"{'=' * 80}")

    for period in df["period"].unique():
        pdf = df[df["period"] == period]
        print(f"\n{'─' * 80}")
        print(f"  Period: {period}")
        print(f"{'─' * 80}")

        # Best by annualized return
        best = pdf.sort_values("annual_return_pct", ascending=False).head(5)
        print(f"\n  TOP 5 by Annualized Return:")
        print(f"  {'Strike':<10} {'DTE':>4} {'Roll':<20} {'Ann.Ret%':>9} "
              f"{'MaxDD%':>8} {'WinRate':>8} {'Trades':>7} {'Cycles':>7}")
        print(f"  {'-' * 75}")
        for _, r in best.iterrows():
            print(f"  {r['strike']:<10} {r['dte']:>4} {r['roll']:<20} "
                  f"{r['annual_return_pct']:>8.1f}% {r['max_drawdown_pct']:>7.1f}% "
                  f"{r['win_rate']:>7.1f}% {r['total_trades']:>7} {r['completed_cycles']:>7}")

        # Best risk-adjusted (return / |drawdown|)
        pdf_ra = pdf.copy()
        pdf_ra["risk_adj"] = pdf_ra["annual_return_pct"] / pdf_ra["max_drawdown_pct"].abs().clip(lower=0.1)
        best_ra = pdf_ra.sort_values("risk_adj", ascending=False).head(3)
        print(f"\n  TOP 3 Risk-Adjusted (Return/Drawdown):")
        print(f"  {'Strike':<10} {'DTE':>4} {'Roll':<20} {'Ann.Ret%':>9} "
              f"{'MaxDD%':>8} {'Ratio':>7}")
        print(f"  {'-' * 60}")
        for _, r in best_ra.iterrows():
            print(f"  {r['strike']:<10} {r['dte']:>4} {r['roll']:<20} "
                  f"{r['annual_return_pct']:>8.1f}% {r['max_drawdown_pct']:>7.1f}% "
                  f"{r['risk_adj']:>7.2f}")

    # --- Aggregate: Strike comparison ---
    print(f"\n{'─' * 80}")
    print(f"  AGGREGATE: Average by Strike Selection")
    print(f"{'─' * 80}")
    strike_agg = df.groupby("strike").agg({
        "annual_return_pct": "mean",
        "max_drawdown_pct": "mean",
        "win_rate": "mean",
        "completed_cycles": "mean",
    }).round(2)
    print(strike_agg.to_string())

    # --- Aggregate: DTE comparison ---
    print(f"\n{'─' * 80}")
    print(f"  AGGREGATE: Average by DTE")
    print(f"{'─' * 80}")
    dte_agg = df.groupby("dte").agg({
        "annual_return_pct": "mean",
        "max_drawdown_pct": "mean",
        "win_rate": "mean",
        "total_trades": "mean",
    }).round(2)
    print(dte_agg.to_string())

    # --- Aggregate: Roll method comparison ---
    print(f"\n{'─' * 80}")
    print(f"  AGGREGATE: Average by Roll Method")
    print(f"{'─' * 80}")
    roll_agg = df.groupby("roll").agg({
        "annual_return_pct": "mean",
        "max_drawdown_pct": "mean",
        "win_rate": "mean",
        "premium_collected": "mean",
    }).round(2)
    print(roll_agg.to_string())


def generate_charts(df: pd.DataFrame, output_dir: str = "results"):
    """Generate comparison charts from study results."""
    if df.empty:
        print("No data for charts.")
        return

    os.makedirs(output_dir, exist_ok=True)
    ticker = df["ticker"].iloc[0]
    pdf_path = os.path.join(output_dir, f"{ticker}_study_charts.pdf")

    with PdfPages(pdf_path) as pdf:
        # --- Chart 1: Annualized Return by Strike & Period ---
        fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True)
        fig.suptitle(f"{ticker} Wheel Strategy: Annualized Return by Strike", fontsize=14)

        for i, period in enumerate(["1Y", "3Y", "5Y"]):
            ax = axes[i]
            pdf_period = df[df["period"] == period]
            if pdf_period.empty:
                ax.set_title(f"{period} (no data)")
                continue

            pivot = pdf_period.groupby(["strike", "dte"])["annual_return_pct"].mean().unstack()
            if not pivot.empty:
                pivot.plot(kind="bar", ax=ax, rot=0)
                ax.set_title(f"{period}")
                ax.set_xlabel("Strike")
                ax.set_ylabel("Annualized Return (%)")
                ax.legend(title="DTE")
                ax.axhline(y=0, color="black", linewidth=0.5)

        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # --- Chart 2: Return vs Drawdown scatter ---
        fig, ax = plt.subplots(figsize=(10, 8))
        for period in df["period"].unique():
            pdf_period = df[df["period"] == period]
            ax.scatter(
                pdf_period["max_drawdown_pct"].abs(),
                pdf_period["annual_return_pct"],
                label=period,
                alpha=0.7,
                s=60,
            )

        ax.set_xlabel("Max Drawdown (%)", fontsize=12)
        ax.set_ylabel("Annualized Return (%)", fontsize=12)
        ax.set_title(f"{ticker}: Return vs Drawdown (All Configs)", fontsize=14)
        ax.legend()
        ax.axhline(y=0, color="black", linewidth=0.5)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # --- Chart 3: Roll Method Comparison ---
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle(f"{ticker}: Roll Method Comparison", fontsize=14)

        roll_agg = df.groupby("roll").agg({
            "annual_return_pct": "mean",
            "max_drawdown_pct": lambda x: x.abs().mean(),
            "win_rate": "mean",
        })

        roll_agg["annual_return_pct"].plot(kind="bar", ax=axes[0], color="steelblue", rot=15)
        axes[0].set_title("Avg Annualized Return (%)")
        axes[0].set_ylabel("%")

        roll_agg["max_drawdown_pct"].plot(kind="bar", ax=axes[1], color="indianred", rot=15)
        axes[1].set_title("Avg Max Drawdown (%)")
        axes[1].set_ylabel("%")

        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # --- Chart 4: Win Rate by DTE ---
        fig, ax = plt.subplots(figsize=(8, 6))
        dte_strike = df.groupby(["dte", "strike"])["win_rate"].mean().unstack()
        dte_strike.plot(kind="bar", ax=ax, rot=0)
        ax.set_title(f"{ticker}: Win Rate by DTE & Strike", fontsize=14)
        ax.set_xlabel("DTE")
        ax.set_ylabel("Win Rate (%)")
        ax.legend(title="Strike")
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # --- Chart 5: Premium Collected Heatmap ---
        fig, ax = plt.subplots(figsize=(10, 6))
        # Average across periods for a single heatmap
        heatmap_data = df.groupby(["strike", "roll"])["annual_return_pct"].mean().unstack()
        if not heatmap_data.empty:
            im = ax.imshow(heatmap_data.values, cmap="RdYlGn", aspect="auto")
            ax.set_xticks(range(len(heatmap_data.columns)))
            ax.set_xticklabels(heatmap_data.columns, rotation=30, ha="right")
            ax.set_yticks(range(len(heatmap_data.index)))
            ax.set_yticklabels(heatmap_data.index)
            ax.set_title(f"{ticker}: Avg Annualized Return (%) by Strike × Roll")
            plt.colorbar(im, ax=ax, label="Annualized Return (%)")

            for i in range(len(heatmap_data.index)):
                for j in range(len(heatmap_data.columns)):
                    val = heatmap_data.values[i, j]
                    ax.text(j, i, f"{val:.1f}", ha="center", va="center", fontsize=9)

        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

    print(f"\nCharts saved to {pdf_path}")


# =============================================================================
# Equity Curve Comparison
# =============================================================================

def run_equity_comparison(
    prices: pd.Series,
    ticker: str = "SYN",
    output_dir: str = "results",
):
    """Run a few key configs and plot equity curves side by side."""
    os.makedirs(output_dir, exist_ok=True)

    key_configs = [
        ("ATM 30DTE Hold", BacktestConfig(strike_method="atm", dte=30, roll_method="hold_to_expiry")),
        ("5%OTM 30DTE Hold", BacktestConfig(strike_method="otm_pct", otm_pct=0.05, dte=30, roll_method="hold_to_expiry")),
        ("5%OTM 45DTE Roll@50%", BacktestConfig(strike_method="otm_pct", otm_pct=0.05, dte=45, roll_method="roll_at_profit", roll_profit_pct=0.50)),
        ("10%OTM 30DTE Hold", BacktestConfig(strike_method="otm_pct", otm_pct=0.10, dte=30, roll_method="hold_to_expiry")),
        ("Buy & Hold", None),  # Benchmark
    ]

    fig, ax = plt.subplots(figsize=(14, 8))

    for name, config in key_configs:
        if config is None:
            # Buy & hold benchmark
            shares = 100
            cost = prices.iloc[30] * shares  # align with vol lookback
            equity = prices.iloc[30:] * shares
            equity_normalized = equity / equity.iloc[0] * 100
            ax.plot(equity_normalized.index, equity_normalized.values,
                    label=f"Buy & Hold", linestyle="--", linewidth=2, color="black")
            continue

        try:
            bt = WheelBacktester(prices.copy(), config, ticker)
            result = bt.run()
            equity_normalized = result.equity_curve / result.equity_curve.iloc[0] * 100
            ax.plot(equity_normalized.index, equity_normalized.values,
                    label=f"{name} ({result.annualized_return_pct:.1f}% ann.)")
        except Exception as e:
            print(f"  Skipping {name}: {e}")

    ax.set_title(f"{ticker}: Wheel Strategy Equity Curves Comparison", fontsize=14)
    ax.set_xlabel("Date")
    ax.set_ylabel("Normalized Equity (base=100)")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)

    chart_path = os.path.join(output_dir, f"{ticker}_equity_comparison.png")
    plt.tight_layout()
    plt.savefig(chart_path, dpi=150)
    plt.close(fig)
    print(f"Equity comparison chart saved to {chart_path}")


# =============================================================================
# Multi-Ticker Study
# =============================================================================

def run_multi_ticker_study(
    data_dir: str,
    output_dir: str = "results",
) -> pd.DataFrame:
    """Run the study across all CSV files in a directory.

    Each CSV should be named TICKER.csv with Date and Close columns.
    """
    all_results = []
    csv_files = sorted([f for f in os.listdir(data_dir) if f.endswith(".csv")])

    if not csv_files:
        print(f"No CSV files found in {data_dir}")
        return pd.DataFrame()

    for csv_file in csv_files:
        ticker = csv_file.replace(".csv", "").upper()
        filepath = os.path.join(data_dir, csv_file)
        print(f"\n{'=' * 60}")
        print(f"  Processing: {ticker}")
        print(f"{'=' * 60}")

        try:
            prices = load_prices_csv(filepath)
            df = run_parameter_study(prices, ticker, output_dir)
            if not df.empty:
                all_results.append(df)
                generate_charts(df, output_dir)
                run_equity_comparison(prices, ticker, output_dir)
        except Exception as e:
            print(f"  ERROR processing {ticker}: {e}")

    if all_results:
        combined = pd.concat(all_results, ignore_index=True)
        combined_path = os.path.join(output_dir, "all_tickers_study.csv")
        combined.to_csv(combined_path, index=False)
        print(f"\nCombined results saved to {combined_path}")
        return combined

    return pd.DataFrame()


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Wheel Strategy Parameter Study")
    parser.add_argument("--data", type=str, default=None,
                        help="Directory with CSV price files (TICKER.csv)")
    parser.add_argument("--ticker", type=str, default=None,
                        help="Single CSV file to backtest")
    parser.add_argument("--output", type=str, default="results",
                        help="Output directory for results")
    parser.add_argument("--synthetic", action="store_true",
                        help="Run with synthetic data (for testing)")
    args = parser.parse_args()

    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), args.output
    )

    if args.ticker:
        # Single ticker
        ticker_name = os.path.basename(args.ticker).replace(".csv", "").upper()
        print(f"Loading {args.ticker}...")
        prices = load_prices_csv(args.ticker)
        print(f"Loaded {len(prices)} days for {ticker_name}")
        df = run_parameter_study(prices, ticker_name, output_dir)
        print_summary_tables(df)
        generate_charts(df, output_dir)
        run_equity_comparison(prices, ticker_name, output_dir)

    elif args.data:
        # Multi-ticker
        combined = run_multi_ticker_study(args.data, output_dir)
        if not combined.empty:
            print_summary_tables(combined)

    else:
        # Synthetic data demo
        print("No data provided. Running with synthetic price data...")
        print("(Use --data <dir> or --ticker <file.csv> for real data)\n")

        # Generate multiple synthetic tickers with different characteristics
        synthetics = {
            "STABLE": {"annual_return": 0.08, "annual_vol": 0.15, "start_price": 50},
            "GROWTH": {"annual_return": 0.15, "annual_vol": 0.25, "start_price": 150},
            "VOLATILE": {"annual_return": 0.05, "annual_vol": 0.40, "start_price": 100},
            "DIVIDEND": {"annual_return": 0.06, "annual_vol": 0.18, "start_price": 60},
        }

        all_dfs = []
        for name, params in synthetics.items():
            print(f"\n{'=' * 60}")
            print(f"  Synthetic Ticker: {name}")
            print(f"  Return={params['annual_return']:.0%}, "
                  f"Vol={params['annual_vol']:.0%}, "
                  f"Price=${params['start_price']}")
            print(f"{'=' * 60}")

            prices = generate_synthetic_prices(
                start_price=params["start_price"],
                days=1400,  # ~5.5 years to ensure 5Y period coverage
                annual_return=params["annual_return"],
                annual_vol=params["annual_vol"],
                seed=hash(name) % 2**31,
            )

            df = run_parameter_study(prices, name, output_dir)
            if not df.empty:
                all_dfs.append(df)
                generate_charts(df, output_dir)
                run_equity_comparison(prices, name, output_dir)

        if all_dfs:
            combined = pd.concat(all_dfs, ignore_index=True)
            print_summary_tables(combined)

            # Cross-ticker comparison
            print(f"\n{'=' * 80}")
            print(f"  CROSS-TICKER COMPARISON (Best config per ticker per period)")
            print(f"{'=' * 80}")
            for period in combined["period"].unique():
                print(f"\n  {period}:")
                period_df = combined[combined["period"] == period]
                best_per_ticker = period_df.loc[
                    period_df.groupby("ticker")["annual_return_pct"].idxmax()
                ]
                for _, r in best_per_ticker.iterrows():
                    print(f"    {r['ticker']:<10} {r['strike']:<10} {r['dte']}DTE "
                          f"{r['roll']:<20} → {r['annual_return_pct']:>7.1f}% ann. "
                          f"(DD: {r['max_drawdown_pct']:.1f}%)")


if __name__ == "__main__":
    main()
