"""
The Wheel Strategy
==================

The Wheel is a systematic income-generating options strategy that cycles
between selling cash-secured puts and covered calls on the same underlying.

Cycle:
  1. SELL CASH-SECURED PUT  →  collect premium
     - If expires OTM → keep premium, repeat step 1
     - If assigned     → you now own shares, go to step 2

  2. SELL COVERED CALL on assigned shares  →  collect premium
     - If expires OTM → keep premium, repeat step 2
     - If called away  → shares sold at strike, collect premium, go to step 1

Benefits:
  - Consistent income from premium collection on both sides.
  - You buy stocks at a discount (put strike - premium).
  - You sell stocks at a premium (call strike + premium).
  - Works well in sideways / slightly bullish markets.

Risks:
  - Stock drops significantly after put assignment (unrealized loss).
  - Stock rallies past covered call strike (capped upside).
  - Requires enough capital to hold 100 shares per contract.

Ideal Conditions:
  - High implied volatility (higher premiums).
  - Stocks with solid fundamentals you'd want to own.
  - Sideways to moderately bullish price action.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from cash_secured_put import CashSecuredPut


class WheelPhase(Enum):
    """Current phase of the wheel strategy."""
    SELLING_PUTS = "selling_puts"
    HOLDING_STOCK_SELLING_CALLS = "holding_stock_selling_calls"


@dataclass
class CoveredCall:
    """Represents a covered call position."""

    ticker: str
    cost_basis: float  # per share, after put assignment
    current_price: float
    strike_price: float
    premium: float
    contracts: int
    days_to_expiration: int

    @property
    def shares(self) -> int:
        return self.contracts * 100

    @property
    def total_premium(self) -> float:
        return self.premium * self.shares

    @property
    def max_profit(self) -> float:
        """Max profit if called away at strike."""
        gain_per_share = (self.strike_price - self.cost_basis) + self.premium
        return gain_per_share * self.shares

    @property
    def breakeven_price(self) -> float:
        """Breakeven considering cost basis and premium collected."""
        return self.cost_basis - self.premium

    @property
    def return_if_called(self) -> float:
        """Return percentage if shares are called away."""
        if self.cost_basis == 0:
            return 0.0
        gain = (self.strike_price - self.cost_basis + self.premium) / self.cost_basis
        return gain * 100

    @property
    def annualized_return_if_called(self) -> float:
        if self.days_to_expiration == 0:
            return 0.0
        return self.return_if_called * (365 / self.days_to_expiration)

    def profit_at_price(self, price_at_expiration: float) -> float:
        """Calculate profit/loss at a given expiration price."""
        if price_at_expiration >= self.strike_price:
            # Called away
            gain_per_share = self.strike_price - self.cost_basis + self.premium
        else:
            # Keep shares
            gain_per_share = price_at_expiration - self.cost_basis + self.premium
        return gain_per_share * self.shares

    def summary(self) -> str:
        lines = [
            f"=== Covered Call: {self.ticker} ===",
            f"Cost Basis:         ${self.cost_basis:>10.2f}",
            f"Current Price:      ${self.current_price:>10.2f}",
            f"Strike Price:       ${self.strike_price:>10.2f}",
            f"Premium:            ${self.premium:>10.2f}",
            f"Contracts:           {self.contracts:>10}",
            f"Days to Expiration:  {self.days_to_expiration:>10}",
            f"---",
            f"Total Premium:      ${self.total_premium:>10.2f}",
            f"Breakeven:          ${self.breakeven_price:>10.2f}",
            f"Max Profit:         ${self.max_profit:>10.2f}",
            f"Return if Called:    {self.return_if_called:>9.2f}%",
            f"Annualized (called): {self.annualized_return_if_called:>8.2f}%",
        ]
        return "\n".join(lines)


@dataclass
class WheelTracker:
    """Track the full wheel strategy lifecycle on a single ticker."""

    ticker: str
    capital: float
    phase: WheelPhase = WheelPhase.SELLING_PUTS
    cost_basis: Optional[float] = None
    shares_held: int = 0
    total_premium_collected: float = 0.0
    completed_cycles: int = 0
    trade_log: list = field(default_factory=list)

    def sell_put(self, strike: float, premium: float, contracts: int, dte: int) -> CashSecuredPut:
        """Enter the put-selling phase."""
        if self.phase != WheelPhase.SELLING_PUTS:
            raise ValueError("Must be in SELLING_PUTS phase to sell puts.")

        csp = CashSecuredPut(
            ticker=self.ticker,
            current_price=strike,  # approximate
            strike_price=strike,
            premium=premium,
            contracts=contracts,
            days_to_expiration=dte,
        )

        if csp.cash_required > self.capital:
            raise ValueError(
                f"Insufficient capital: need ${csp.cash_required:.2f}, "
                f"have ${self.capital:.2f}"
            )

        self.total_premium_collected += csp.total_premium
        self.trade_log.append({
            "action": "SELL_PUT",
            "strike": strike,
            "premium": premium,
            "contracts": contracts,
            "dte": dte,
            "total_premium": csp.total_premium,
        })
        return csp

    def put_assigned(self, strike: float, premium: float, contracts: int):
        """Handle put assignment — transition to covered call phase."""
        shares = contracts * 100
        self.cost_basis = strike - premium  # effective cost basis
        self.shares_held = shares
        self.capital -= strike * shares
        self.phase = WheelPhase.HOLDING_STOCK_SELLING_CALLS
        self.trade_log.append({
            "action": "PUT_ASSIGNED",
            "strike": strike,
            "cost_basis": self.cost_basis,
            "shares": shares,
        })

    def put_expired(self, premium_collected: float):
        """Put expired OTM — stay in put-selling phase."""
        self.capital += premium_collected
        self.trade_log.append({
            "action": "PUT_EXPIRED_OTM",
            "premium_kept": premium_collected,
        })

    def sell_call(
        self, current_price: float, strike: float, premium: float, contracts: int, dte: int
    ) -> CoveredCall:
        """Sell a covered call on held shares."""
        if self.phase != WheelPhase.HOLDING_STOCK_SELLING_CALLS:
            raise ValueError("Must hold shares to sell covered calls.")

        cc = CoveredCall(
            ticker=self.ticker,
            cost_basis=self.cost_basis,
            current_price=current_price,
            strike_price=strike,
            premium=premium,
            contracts=contracts,
            days_to_expiration=dte,
        )

        self.total_premium_collected += cc.total_premium
        self.trade_log.append({
            "action": "SELL_CALL",
            "strike": strike,
            "premium": premium,
            "contracts": contracts,
            "dte": dte,
            "total_premium": cc.total_premium,
        })
        return cc

    def call_assigned(self, strike: float, premium: float, contracts: int):
        """Shares called away — cycle complete, back to selling puts."""
        shares = contracts * 100
        self.capital += strike * shares
        self.shares_held = 0
        self.cost_basis = None
        self.phase = WheelPhase.SELLING_PUTS
        self.completed_cycles += 1
        self.trade_log.append({
            "action": "CALL_ASSIGNED",
            "strike": strike,
            "shares_sold": shares,
            "cycle_completed": self.completed_cycles,
        })

    def call_expired(self, premium_collected: float):
        """Call expired OTM — keep shares and premium, sell another call."""
        self.capital += premium_collected
        self.trade_log.append({
            "action": "CALL_EXPIRED_OTM",
            "premium_kept": premium_collected,
        })

    def status(self) -> str:
        lines = [
            f"=== Wheel Strategy: {self.ticker} ===",
            f"Phase:               {self.phase.value}",
            f"Capital:            ${self.capital:>10.2f}",
            f"Shares Held:         {self.shares_held:>10}",
            f"Cost Basis:         ${self.cost_basis or 0:>10.2f}",
            f"Total Premium:      ${self.total_premium_collected:>10.2f}",
            f"Completed Cycles:    {self.completed_cycles:>10}",
            f"Trades:              {len(self.trade_log):>10}",
        ]
        return "\n".join(lines)


# --- Example: Full Wheel Cycle ---
if __name__ == "__main__":
    # Start with $20,000 capital, wheel on AAPL
    wheel = WheelTracker(ticker="AAPL", capital=20000.00)

    # Phase 1: Sell a cash-secured put
    print("--- Step 1: Sell Cash-Secured Put ---")
    csp = wheel.sell_put(strike=170, premium=2.50, contracts=1, dte=30)
    print(csp.summary())

    # Scenario: Put gets assigned
    print("\n--- Step 2: Put Assigned ---")
    wheel.put_assigned(strike=170, premium=2.50, contracts=1)
    print(wheel.status())

    # Phase 2: Sell a covered call
    print("\n--- Step 3: Sell Covered Call ---")
    cc = wheel.sell_call(
        current_price=168.00, strike=175, premium=2.00, contracts=1, dte=30
    )
    print(cc.summary())

    # Scenario: Call gets assigned (shares called away)
    print("\n--- Step 4: Call Assigned (Cycle Complete) ---")
    wheel.call_assigned(strike=175, premium=2.00, contracts=1)
    print(wheel.status())

    # Summary
    print(f"\nTotal premium earned over 1 full cycle: ${wheel.total_premium_collected:.2f}")
