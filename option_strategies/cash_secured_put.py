"""
Cash-Secured Put (CSP) Strategy
===============================

A cash-secured put is an options strategy where you sell (write) a put option
while holding enough cash to buy the underlying stock if assigned.

Key Concepts:
- You collect premium upfront when selling the put.
- You are obligated to buy the stock at the strike price if assigned.
- Maximum profit = premium received.
- Maximum loss = strike price - premium received (if stock goes to $0).
- Breakeven = strike price - premium received.

When to Use:
- Bullish or neutral outlook on the underlying.
- Willing to own the stock at the strike price.
- Want to generate income while waiting to buy at a lower price.

Risk Management:
- Only sell puts on stocks you want to own.
- Keep strike price at or below your target buy price.
- Monitor position delta and adjust if outlook changes.
- Consider rolling down/out if the trade moves against you.
"""

import math
from dataclasses import dataclass


@dataclass
class CashSecuredPut:
    """Represents a cash-secured put position."""

    ticker: str
    current_price: float
    strike_price: float
    premium: float
    contracts: int
    days_to_expiration: int

    @property
    def shares(self) -> int:
        """Total shares controlled (100 per contract)."""
        return self.contracts * 100

    @property
    def total_premium(self) -> float:
        """Total premium collected."""
        return self.premium * self.shares

    @property
    def cash_required(self) -> float:
        """Cash needed to secure the put (collateral)."""
        return self.strike_price * self.shares

    @property
    def breakeven_price(self) -> float:
        """Price at which the trade breaks even."""
        return self.strike_price - self.premium

    @property
    def max_profit(self) -> float:
        """Maximum profit if the option expires worthless."""
        return self.total_premium

    @property
    def max_loss(self) -> float:
        """Maximum loss if stock goes to $0."""
        return self.cash_required - self.total_premium

    @property
    def return_on_capital(self) -> float:
        """Return on capital as a percentage."""
        if self.cash_required == 0:
            return 0.0
        return (self.total_premium / self.cash_required) * 100

    @property
    def annualized_return(self) -> float:
        """Annualized return on capital."""
        if self.days_to_expiration == 0:
            return 0.0
        return self.return_on_capital * (365 / self.days_to_expiration)

    def profit_at_price(self, price_at_expiration: float) -> float:
        """Calculate profit/loss at a given expiration price."""
        if price_at_expiration >= self.strike_price:
            # Put expires worthless, keep full premium
            return self.total_premium
        else:
            # Assigned: buy stock at strike, current value is lower
            loss_per_share = self.strike_price - price_at_expiration
            return self.total_premium - (loss_per_share * self.shares)

    def summary(self) -> str:
        """Print a summary of the position."""
        lines = [
            f"=== Cash-Secured Put: {self.ticker} ===",
            f"Current Price:      ${self.current_price:>10.2f}",
            f"Strike Price:       ${self.strike_price:>10.2f}",
            f"Premium:            ${self.premium:>10.2f}",
            f"Contracts:           {self.contracts:>10}",
            f"Days to Expiration:  {self.days_to_expiration:>10}",
            f"---",
            f"Cash Required:      ${self.cash_required:>10.2f}",
            f"Total Premium:      ${self.total_premium:>10.2f}",
            f"Breakeven Price:    ${self.breakeven_price:>10.2f}",
            f"Max Profit:         ${self.max_profit:>10.2f}",
            f"Max Loss:           ${self.max_loss:>10.2f}",
            f"Return on Capital:   {self.return_on_capital:>9.2f}%",
            f"Annualized Return:   {self.annualized_return:>9.2f}%",
        ]
        return "\n".join(lines)


def select_strike(current_price: float, target_discount: float = 0.05) -> float:
    """Suggest a strike price at a target discount from current price.

    Args:
        current_price: Current stock price.
        target_discount: Desired discount (e.g., 0.05 = 5% below current).

    Returns:
        Suggested strike price rounded to nearest dollar.
    """
    raw_strike = current_price * (1 - target_discount)
    return round(raw_strike)


def evaluate_csp(
    ticker: str,
    current_price: float,
    strike_price: float,
    premium: float,
    contracts: int = 1,
    days_to_expiration: int = 30,
    min_annualized_return: float = 12.0,
) -> dict:
    """Evaluate whether a CSP trade meets minimum return criteria.

    Args:
        ticker: Stock ticker symbol.
        current_price: Current stock price.
        strike_price: Put strike price.
        premium: Premium per share.
        contracts: Number of contracts.
        days_to_expiration: Days until expiration.
        min_annualized_return: Minimum acceptable annualized return (%).

    Returns:
        Dictionary with trade evaluation details.
    """
    csp = CashSecuredPut(
        ticker=ticker,
        current_price=current_price,
        strike_price=strike_price,
        premium=premium,
        contracts=contracts,
        days_to_expiration=days_to_expiration,
    )

    meets_criteria = csp.annualized_return >= min_annualized_return
    otm_percentage = ((current_price - strike_price) / current_price) * 100

    return {
        "ticker": ticker,
        "position": csp,
        "meets_criteria": meets_criteria,
        "annualized_return": csp.annualized_return,
        "otm_percentage": otm_percentage,
        "summary": csp.summary(),
    }


# --- Example Usage ---
if __name__ == "__main__":
    # Example: Selling a cash-secured put on AAPL
    trade = evaluate_csp(
        ticker="AAPL",
        current_price=175.00,
        strike_price=170.00,
        premium=2.50,
        contracts=1,
        days_to_expiration=30,
    )

    print(trade["summary"])
    print(f"\nOTM%: {trade['otm_percentage']:.2f}%")
    print(f"Meets criteria (>12% annualized): {trade['meets_criteria']}")
