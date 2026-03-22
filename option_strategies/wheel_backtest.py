"""
Wheel Strategy Backtester
=========================

Backtests the full wheel strategy (sell CSP → assignment → sell CC → called away)
over historical price data with configurable parameters:

  - Strike selection: ATM, % OTM, delta-based
  - DTE (days to expiration): 30, 45, 60
  - Rolling rules: roll at X% profit, roll at N days before expiry, hold to expiry
  - Time periods: 1Y, 3Y, 5Y
  - Outputs: total ROI, annualized return, max drawdown, win rate, premium collected

Usage:
    from wheel_backtest import WheelBacktester, BacktestConfig
    config = BacktestConfig(strike_method="otm_pct", otm_pct=0.05, dte=30)
    bt = WheelBacktester(prices, config)
    result = bt.run()
    print(result.summary())
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from option_pricing import (
    black_scholes_call,
    black_scholes_put,
    historical_volatility,
    round_strike,
)


# =============================================================================
# Configuration
# =============================================================================

class StrikeMethod(Enum):
    ATM = "atm"              # At the money
    OTM_PCT = "otm_pct"      # % out of the money
    DELTA = "delta"           # Target delta


class RollMethod(Enum):
    HOLD_TO_EXPIRY = "hold_to_expiry"        # No rolling, hold until expiration
    ROLL_AT_PROFIT = "roll_at_profit"        # Roll when X% of max profit achieved
    ROLL_BEFORE_EXPIRY = "roll_before_expiry"  # Roll N days before expiry


@dataclass
class BacktestConfig:
    """Configuration for a wheel strategy backtest."""

    # Strike selection
    strike_method: str = "otm_pct"   # "atm", "otm_pct", "delta"
    otm_pct: float = 0.05           # 5% OTM (for puts: below price, calls: above price)
    target_delta: float = 0.30      # Target delta (absolute value)

    # Expiration
    dte: int = 30                    # Days to expiration

    # Rolling
    roll_method: str = "hold_to_expiry"  # "hold_to_expiry", "roll_at_profit", "roll_before_expiry"
    roll_profit_pct: float = 0.50    # Roll when 50% of max profit is reached
    roll_days_before: int = 7        # Roll when N days remain

    # Covered call strike (when holding shares)
    cc_strike_method: str = "otm_pct"
    cc_otm_pct: float = 0.05        # 5% above cost basis or current price
    cc_above_cost_basis: bool = True  # Strike above cost basis (avoid selling at loss)

    # Market parameters
    risk_free_rate: float = 0.045    # Risk-free rate
    iv_premium: float = 1.2         # IV premium over HV (options tend to be overpriced)
    vol_lookback: int = 30           # HV lookback window

    # Capital
    contracts: int = 1               # Number of contracts
    initial_capital: float = 0.0     # Auto-calculated if 0

    def label(self) -> str:
        """Short label for this config."""
        parts = []
        if self.strike_method == "atm":
            parts.append("ATM")
        elif self.strike_method == "otm_pct":
            parts.append(f"{self.otm_pct:.0%}OTM")
        else:
            parts.append(f"Δ{self.target_delta:.0f}")
        parts.append(f"{self.dte}DTE")
        if self.roll_method == "roll_at_profit":
            parts.append(f"Roll@{self.roll_profit_pct:.0%}")
        elif self.roll_method == "roll_before_expiry":
            parts.append(f"Roll@{self.roll_days_before}d")
        else:
            parts.append("HoldExp")
        return " | ".join(parts)


# =============================================================================
# Trade Log
# =============================================================================

@dataclass
class Trade:
    """Record of a single option trade."""
    trade_type: str        # "CSP" or "CC"
    open_date: str
    close_date: str
    open_price: float      # stock price at open
    close_price: float     # stock price at close
    strike: float
    premium: float         # per share
    dte_at_open: int
    days_held: int
    pnl: float             # total P&L for this trade
    outcome: str           # "expired_otm", "assigned", "rolled", "called_away"
    shares: int = 100


# =============================================================================
# Backtest Result
# =============================================================================

@dataclass
class BacktestResult:
    """Results of a wheel strategy backtest."""

    config: BacktestConfig
    ticker: str
    start_date: str
    end_date: str
    trading_days: int

    # Returns
    initial_capital: float
    final_capital: float
    total_return_pct: float
    annualized_return_pct: float

    # Risk
    max_drawdown_pct: float
    max_drawdown_duration_days: int

    # Trade stats
    total_trades: int
    csp_trades: int
    cc_trades: int
    win_rate: float
    total_premium_collected: float
    total_assignment_pnl: float

    # Cycle stats
    completed_cycles: int
    avg_cycle_days: float

    # Detailed
    trades: list
    equity_curve: pd.Series
    daily_returns: pd.Series

    def summary(self) -> str:
        years = self.trading_days / 252
        lines = [
            f"{'=' * 70}",
            f"  WHEEL BACKTEST: {self.ticker}",
            f"  Config: {self.config.label()}",
            f"  Period: {self.start_date} → {self.end_date} ({years:.1f} years)",
            f"{'=' * 70}",
            f"",
            f"  RETURNS",
            f"    Initial Capital:     ${self.initial_capital:>12,.2f}",
            f"    Final Capital:       ${self.final_capital:>12,.2f}",
            f"    Total Return:         {self.total_return_pct:>11.2f}%",
            f"    Annualized Return:    {self.annualized_return_pct:>11.2f}%",
            f"",
            f"  RISK",
            f"    Max Drawdown:         {self.max_drawdown_pct:>11.2f}%",
            f"    Max DD Duration:      {self.max_drawdown_duration_days:>8} days",
            f"",
            f"  TRADES",
            f"    Total Trades:         {self.total_trades:>8}",
            f"    CSP Trades:           {self.csp_trades:>8}",
            f"    CC Trades:            {self.cc_trades:>8}",
            f"    Win Rate:             {self.win_rate:>10.1f}%",
            f"    Premium Collected:   ${self.total_premium_collected:>12,.2f}",
            f"    Assignment P&L:      ${self.total_assignment_pnl:>12,.2f}",
            f"",
            f"  CYCLES",
            f"    Completed Cycles:     {self.completed_cycles:>8}",
            f"    Avg Cycle Duration:   {self.avg_cycle_days:>8.0f} days",
            f"{'=' * 70}",
        ]
        return "\n".join(lines)


# =============================================================================
# Backtester Engine
# =============================================================================

class WheelBacktester:
    """Backtests the wheel strategy on historical daily price data."""

    def __init__(self, prices: pd.Series, config: BacktestConfig, ticker: str = ""):
        """
        Args:
            prices: pd.Series of daily closing prices with DatetimeIndex.
            config: BacktestConfig with strategy parameters.
            ticker: Ticker symbol for labeling.
        """
        self.prices = prices.dropna()
        self.config = config
        self.ticker = ticker

        # State
        self.phase = "selling_puts"  # or "selling_calls"
        self.shares_held = 0
        self.cost_basis = 0.0
        self.trades: list[Trade] = []
        self.cycle_starts: list[int] = []
        self.cycle_ends: list[int] = []

        # Current position
        self.current_strike = 0.0
        self.current_premium = 0.0
        self.current_open_idx = 0
        self.current_expiry_idx = 0
        self.current_open_price = 0.0

        # Capital tracking
        self.capital = config.initial_capital
        self.equity_history: list[float] = []
        self.dates: list = []

    def _get_vol(self, idx: int) -> float:
        """Get historical volatility at a given index."""
        lookback = self.config.vol_lookback
        start = max(0, idx - lookback)
        window = self.prices.values[start:idx + 1]
        hv = historical_volatility(window, lookback)
        return hv * self.config.iv_premium  # IV typically > HV

    def _select_put_strike(self, price: float, vol: float) -> float:
        """Select put strike based on config."""
        method = self.config.strike_method
        if method == "atm":
            return round_strike(price)
        elif method == "otm_pct":
            return round_strike(price * (1 - self.config.otm_pct))
        elif method == "delta":
            # Approximate: find strike where |delta| ≈ target
            target = self.config.target_delta
            T = self.config.dte / 365
            # Binary search for strike
            lo, hi = price * 0.7, price * 1.0
            for _ in range(50):
                mid = (lo + hi) / 2
                q = black_scholes_put(price, mid, T, self.config.risk_free_rate, vol)
                if abs(q.delta) < target:
                    lo = mid
                else:
                    hi = mid
            return round_strike((lo + hi) / 2)
        return round_strike(price)

    def _select_call_strike(self, price: float, vol: float) -> float:
        """Select covered call strike."""
        method = self.config.cc_strike_method
        if method == "atm":
            strike = round_strike(price)
        elif method == "otm_pct":
            strike = round_strike(price * (1 + self.config.cc_otm_pct))
        else:
            strike = round_strike(price * (1 + self.config.cc_otm_pct))

        # Ensure strike is above cost basis if configured
        if self.config.cc_above_cost_basis and self.cost_basis > 0:
            min_strike = round_strike(self.cost_basis)
            strike = max(strike, min_strike)

        return strike

    def _price_put(self, spot: float, strike: float, vol: float, dte: int) -> float:
        """Price a put option."""
        T = max(dte, 1) / 365
        q = black_scholes_put(spot, strike, T, self.config.risk_free_rate, vol)
        return max(q.price, 0.01)

    def _price_call(self, spot: float, strike: float, vol: float, dte: int) -> float:
        """Price a call option."""
        T = max(dte, 1) / 365
        q = black_scholes_call(spot, strike, T, self.config.risk_free_rate, vol)
        return max(q.price, 0.01)

    def _should_roll(self, current_idx: int, spot: float) -> bool:
        """Check if the position should be rolled."""
        method = self.config.roll_method
        if method == "hold_to_expiry":
            return False

        days_remaining = self.current_expiry_idx - current_idx

        if method == "roll_before_expiry":
            return days_remaining <= self.config.roll_days_before

        if method == "roll_at_profit":
            # Check if we've captured enough premium via time decay
            total_dte = self.current_expiry_idx - self.current_open_idx
            elapsed = current_idx - self.current_open_idx
            if total_dte == 0:
                return False
            # Rough theta decay approximation: premium decays proportional to sqrt(time)
            remaining_frac = math.sqrt(days_remaining / total_dte) if total_dte > 0 else 0
            profit_frac = 1 - remaining_frac
            return profit_frac >= self.config.roll_profit_pct

        return False

    def _open_put(self, idx: int):
        """Open a new CSP position."""
        price = self.prices.values[idx]
        vol = self._get_vol(idx)
        strike = self._select_put_strike(price, vol)
        premium = self._price_put(price, strike, vol, self.config.dte)

        self.current_strike = strike
        self.current_premium = premium
        self.current_open_idx = idx
        self.current_expiry_idx = min(idx + self.config.dte, len(self.prices) - 1)
        self.current_open_price = price

    def _open_call(self, idx: int):
        """Open a new covered call position."""
        price = self.prices.values[idx]
        vol = self._get_vol(idx)
        strike = self._select_call_strike(price, vol)
        premium = self._price_call(price, strike, vol, self.config.dte)

        self.current_strike = strike
        self.current_premium = premium
        self.current_open_idx = idx
        self.current_expiry_idx = min(idx + self.config.dte, len(self.prices) - 1)
        self.current_open_price = price

    def _close_put(self, idx: int, reason: str) -> Trade:
        """Close a CSP position."""
        close_price = self.prices.values[idx]
        shares = self.config.contracts * 100
        premium_total = self.current_premium * shares
        days_held = idx - self.current_open_idx

        if reason == "assigned":
            # Put ITM at expiry: buy shares at strike, but collected premium
            assignment_cost = self.current_strike * shares
            self.cost_basis = self.current_strike - self.current_premium
            self.shares_held = shares
            self.capital -= assignment_cost
            self.capital += premium_total
            pnl = (close_price - self.current_strike + self.current_premium) * shares
            self.phase = "selling_calls"
        elif reason == "expired_otm":
            # Keep full premium
            self.capital += premium_total
            pnl = premium_total
        elif reason == "rolled":
            # Capture partial premium (approximate)
            vol = self._get_vol(idx)
            remaining_dte = self.current_expiry_idx - idx
            current_put_value = self._price_put(close_price, self.current_strike, vol, remaining_dte)
            profit = (self.current_premium - current_put_value) * shares
            self.capital += profit
            pnl = profit
        else:
            pnl = premium_total

        trade = Trade(
            trade_type="CSP",
            open_date=str(self.prices.index[self.current_open_idx].date()),
            close_date=str(self.prices.index[idx].date()),
            open_price=self.current_open_price,
            close_price=close_price,
            strike=self.current_strike,
            premium=self.current_premium,
            dte_at_open=self.current_expiry_idx - self.current_open_idx,
            days_held=days_held,
            pnl=pnl,
            outcome=reason,
            shares=shares,
        )
        self.trades.append(trade)
        return trade

    def _close_call(self, idx: int, reason: str) -> Trade:
        """Close a covered call position."""
        close_price = self.prices.values[idx]
        shares = self.config.contracts * 100
        premium_total = self.current_premium * shares
        days_held = idx - self.current_open_idx

        if reason == "called_away":
            # Shares sold at strike price
            sale_proceeds = self.current_strike * shares
            stock_pnl = (self.current_strike - self.cost_basis) * shares
            self.capital += sale_proceeds + premium_total
            pnl = stock_pnl + premium_total
            self.shares_held = 0
            self.cost_basis = 0.0
            self.phase = "selling_puts"
            self.cycle_ends.append(idx)
        elif reason == "expired_otm":
            # Keep shares + premium
            self.capital += premium_total
            pnl = premium_total
        elif reason == "rolled":
            vol = self._get_vol(idx)
            remaining_dte = self.current_expiry_idx - idx
            current_call_value = self._price_call(close_price, self.current_strike, vol, remaining_dte)
            profit = (self.current_premium - current_call_value) * shares
            self.capital += profit
            pnl = profit
        else:
            pnl = premium_total

        trade = Trade(
            trade_type="CC",
            open_date=str(self.prices.index[self.current_open_idx].date()),
            close_date=str(self.prices.index[idx].date()),
            open_price=self.current_open_price,
            close_price=close_price,
            strike=self.current_strike,
            premium=self.current_premium,
            dte_at_open=self.current_expiry_idx - self.current_open_idx,
            days_held=days_held,
            pnl=pnl,
            outcome=reason,
            shares=shares,
        )
        self.trades.append(trade)
        return trade

    def _equity_at(self, idx: int) -> float:
        """Calculate total equity (cash + stock value)."""
        equity = self.capital
        if self.shares_held > 0:
            equity += self.prices.values[idx] * self.shares_held
        return equity

    def run(self) -> BacktestResult:
        """Run the full backtest."""
        n = len(self.prices)
        if n < self.config.vol_lookback + self.config.dte + 10:
            raise ValueError(f"Need at least {self.config.vol_lookback + self.config.dte + 10} "
                             f"days of data, got {n}")

        # Auto-calculate initial capital if not set
        max_price = self.prices.values.max()
        if self.config.initial_capital <= 0:
            self.capital = max_price * self.config.contracts * 100 * 1.1
        else:
            self.capital = self.config.initial_capital

        initial_capital = self.capital
        start_idx = self.config.vol_lookback  # skip initial lookback window

        # Open first position
        self.cycle_starts.append(start_idx)
        self._open_put(start_idx)
        self.equity_history.append(self._equity_at(start_idx))
        self.dates.append(self.prices.index[start_idx])

        idx = start_idx + 1
        while idx < n:
            price = self.prices.values[idx]

            if self.phase == "selling_puts":
                # Check for roll
                if self._should_roll(idx, price) and idx < self.current_expiry_idx:
                    self._close_put(idx, "rolled")
                    self._open_put(idx)
                # Check for expiration
                elif idx >= self.current_expiry_idx:
                    if price <= self.current_strike:
                        # ITM → assigned
                        self._close_put(idx, "assigned")
                        # Now in selling_calls phase, open a covered call
                        if idx + 1 < n:
                            self._open_call(idx + 1 if idx + 1 < n else idx)
                    else:
                        # OTM → expired worthless
                        self._close_put(idx, "expired_otm")
                        # Open new CSP
                        if idx + 1 < n:
                            self.cycle_starts.append(idx + 1)
                            self._open_put(idx + 1 if idx + 1 < n else idx)

            elif self.phase == "selling_calls":
                # Check for roll
                if self._should_roll(idx, price) and idx < self.current_expiry_idx:
                    self._close_call(idx, "rolled")
                    self._open_call(idx)
                # Check for expiration
                elif idx >= self.current_expiry_idx:
                    if price >= self.current_strike:
                        # ITM → called away
                        self._close_call(idx, "called_away")
                        # Back to selling puts
                        if idx + 1 < n:
                            self.cycle_starts.append(idx + 1)
                            self._open_put(idx + 1 if idx + 1 < n else idx)
                    else:
                        # OTM → keep shares, sell another call
                        self._close_call(idx, "expired_otm")
                        if idx + 1 < n:
                            self._open_call(idx + 1 if idx + 1 < n else idx)

            self.equity_history.append(self._equity_at(idx))
            self.dates.append(self.prices.index[idx])
            idx += 1

        # Build equity curve
        equity_curve = pd.Series(self.equity_history, index=self.dates)
        daily_returns = equity_curve.pct_change().dropna()

        # Calculate metrics
        final_capital = self.equity_history[-1] if self.equity_history else initial_capital
        total_return = (final_capital - initial_capital) / initial_capital * 100
        years = (n - start_idx) / 252
        ann_return = ((final_capital / initial_capital) ** (1 / max(years, 0.01)) - 1) * 100

        # Max drawdown
        peak = equity_curve.expanding().max()
        drawdown = (equity_curve - peak) / peak * 100
        max_dd = drawdown.min()

        # Max drawdown duration
        underwater = drawdown < 0
        dd_groups = (~underwater).cumsum()
        if underwater.any():
            dd_durations = underwater.groupby(dd_groups).sum()
            max_dd_duration = int(dd_durations.max()) if len(dd_durations) > 0 else 0
        else:
            max_dd_duration = 0

        # Trade stats
        csp_trades = [t for t in self.trades if t.trade_type == "CSP"]
        cc_trades = [t for t in self.trades if t.trade_type == "CC"]
        wins = [t for t in self.trades if t.pnl > 0]
        win_rate = (len(wins) / len(self.trades) * 100) if self.trades else 0

        total_premium = sum(t.premium * t.shares for t in self.trades)
        assignment_pnl = sum(
            t.pnl - t.premium * t.shares
            for t in self.trades
            if t.outcome in ("assigned", "called_away")
        )

        # Cycle stats
        completed_cycles = len(self.cycle_ends)
        if completed_cycles > 0 and len(self.cycle_starts) >= completed_cycles:
            cycle_days = [
                self.cycle_ends[i] - self.cycle_starts[i]
                for i in range(completed_cycles)
            ]
            avg_cycle = sum(cycle_days) / len(cycle_days) if cycle_days else 0
        else:
            avg_cycle = 0

        return BacktestResult(
            config=self.config,
            ticker=self.ticker,
            start_date=str(self.prices.index[start_idx].date()),
            end_date=str(self.prices.index[-1].date()),
            trading_days=n - start_idx,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return_pct=total_return,
            annualized_return_pct=ann_return,
            max_drawdown_pct=max_dd,
            max_drawdown_duration_days=max_dd_duration,
            total_trades=len(self.trades),
            csp_trades=len(csp_trades),
            cc_trades=len(cc_trades),
            win_rate=win_rate,
            total_premium_collected=total_premium,
            total_assignment_pnl=assignment_pnl,
            completed_cycles=completed_cycles,
            avg_cycle_days=avg_cycle,
            trades=self.trades,
            equity_curve=equity_curve,
            daily_returns=daily_returns,
        )


# =============================================================================
# Data Helpers
# =============================================================================

def load_prices_csv(filepath: str, date_col: str = "Date", price_col: str = "Close") -> pd.Series:
    """Load price data from CSV file.

    Expected format: CSV with at least Date and Close columns.
    Compatible with Yahoo Finance downloads.
    """
    df = pd.read_csv(filepath, parse_dates=[date_col])
    df = df.sort_values(date_col)
    df = df.set_index(date_col)
    return df[price_col]


def generate_synthetic_prices(
    start_price: float = 100.0,
    days: int = 1260,  # ~5 years
    annual_return: float = 0.10,
    annual_vol: float = 0.25,
    seed: int = 42,
) -> pd.Series:
    """Generate synthetic daily prices using geometric Brownian motion.

    Useful for testing when real data is not available.
    """
    rng = np.random.default_rng(seed)
    dt = 1 / 252
    daily_return = (annual_return - 0.5 * annual_vol**2) * dt
    daily_vol = annual_vol * math.sqrt(dt)

    log_returns = rng.normal(daily_return, daily_vol, days)
    log_prices = np.cumsum(log_returns)
    prices = start_price * np.exp(log_prices)

    dates = pd.bdate_range(start="2020-01-02", periods=days)
    return pd.Series(prices, index=dates, name="Close")


# =============================================================================
# Quick single-run helper
# =============================================================================

def run_single(
    prices: pd.Series,
    ticker: str = "",
    **config_kwargs,
) -> BacktestResult:
    """Quick helper to run a single backtest."""
    config = BacktestConfig(**config_kwargs)
    bt = WheelBacktester(prices, config, ticker)
    return bt.run()
