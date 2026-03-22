"""
Wheel Strategy Candidates
=========================

Criteria for selecting stocks/ETFs suitable for the wheel strategy:

1. LIQUIDITY       — High options volume and tight bid-ask spreads.
2. FUNDAMENTALS    — Strong balance sheet, you'd want to own the stock.
3. PRICE RANGE     — Affordable enough to hold 100 shares per contract.
4. VOLATILITY      — Moderate-to-high IV for decent premiums, but not
                     so volatile that assignment leads to large drawdowns.
5. DIVIDENDS       — Dividend-paying stocks add extra income while holding.
6. NO EARNINGS     — Avoid selling puts right before earnings (binary risk).
7. SECTOR          — Diversify across sectors to reduce correlation risk.

Categories:
  - Blue-Chip / Large-Cap Stocks
  - High-Dividend Stocks
  - ETFs / Index Funds (lower risk, broad diversification)
  - REITs (high dividend, range-bound)
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class WheelCandidate:
    """A stock or ETF evaluated for the wheel strategy."""

    ticker: str
    name: str
    sector: str
    approx_price: float  # approximate price for capital planning
    dividend_yield: float  # annual dividend yield %
    avg_iv_rank: float  # typical IV rank (0-100)
    options_liquidity: str  # "high", "medium", "low"
    capital_per_contract: float  # approx cash needed for 1 CSP
    notes: str = ""

    @property
    def monthly_premium_estimate(self) -> float:
        """Rough estimate of monthly CSP premium (1-2% of strike for ~30 DTE)."""
        return self.approx_price * 0.015  # 1.5% midpoint estimate

    def summary(self) -> str:
        return (
            f"{self.ticker:>6} | {self.name:<30} | {self.sector:<15} | "
            f"~${self.approx_price:>7.0f} | Div: {self.dividend_yield:.1f}% | "
            f"IV Rank: {self.avg_iv_rank:.0f} | Liq: {self.options_liquidity}"
        )


# =============================================================================
# CURATED WHEEL CANDIDATES
# =============================================================================

BLUE_CHIP_STOCKS = [
    WheelCandidate(
        ticker="AAPL", name="Apple Inc.", sector="Technology",
        approx_price=175, dividend_yield=0.5, avg_iv_rank=35,
        options_liquidity="high", capital_per_contract=17500,
        notes="Most liquid options market. Consistent performer.",
    ),
    WheelCandidate(
        ticker="MSFT", name="Microsoft Corp.", sector="Technology",
        approx_price=420, dividend_yield=0.7, avg_iv_rank=30,
        options_liquidity="high", capital_per_contract=42000,
        notes="Cloud growth + dividends. Higher capital requirement.",
    ),
    WheelCandidate(
        ticker="GOOGL", name="Alphabet Inc.", sector="Technology",
        approx_price=175, dividend_yield=0.5, avg_iv_rank=35,
        options_liquidity="high", capital_per_contract=17500,
        notes="Search + cloud dominance. Recently started paying dividends.",
    ),
    WheelCandidate(
        ticker="AMD", name="Advanced Micro Devices", sector="Semiconductors",
        approx_price=160, dividend_yield=0.0, avg_iv_rank=50,
        options_liquidity="high", capital_per_contract=16000,
        notes="Higher IV = better premiums. More volatile, use wider OTM.",
    ),
    WheelCandidate(
        ticker="AMZN", name="Amazon.com Inc.", sector="Consumer/Cloud",
        approx_price=185, dividend_yield=0.0, avg_iv_rank=35,
        options_liquidity="high", capital_per_contract=18500,
        notes="After stock split, much more accessible for wheel.",
    ),
    WheelCandidate(
        ticker="JPM", name="JPMorgan Chase & Co.", sector="Financials",
        approx_price=200, dividend_yield=2.2, avg_iv_rank=30,
        options_liquidity="high", capital_per_contract=20000,
        notes="Strong bank, good dividends. Financials add diversification.",
    ),
    WheelCandidate(
        ticker="DIS", name="Walt Disney Co.", sector="Entertainment",
        approx_price=110, dividend_yield=0.8, avg_iv_rank=35,
        options_liquidity="high", capital_per_contract=11000,
        notes="Lower price = lower capital. Decent premiums around earnings.",
    ),
]

HIGH_DIVIDEND_STOCKS = [
    WheelCandidate(
        ticker="KO", name="Coca-Cola Co.", sector="Consumer Staples",
        approx_price=60, dividend_yield=3.0, avg_iv_rank=20,
        options_liquidity="high", capital_per_contract=6000,
        notes="Dividend aristocrat. Low IV but very low capital requirement.",
    ),
    WheelCandidate(
        ticker="PEP", name="PepsiCo Inc.", sector="Consumer Staples",
        approx_price=170, dividend_yield=2.7, avg_iv_rank=20,
        options_liquidity="high", capital_per_contract=17000,
        notes="Stable consumer staple. Consistent dividends.",
    ),
    WheelCandidate(
        ticker="JNJ", name="Johnson & Johnson", sector="Healthcare",
        approx_price=155, dividend_yield=3.0, avg_iv_rank=20,
        options_liquidity="high", capital_per_contract=15500,
        notes="Dividend king. Defensive sector.",
    ),
    WheelCandidate(
        ticker="ABBV", name="AbbVie Inc.", sector="Pharma",
        approx_price=180, dividend_yield=3.5, avg_iv_rank=30,
        options_liquidity="high", capital_per_contract=18000,
        notes="High dividend + decent IV. Strong pharma pipeline.",
    ),
    WheelCandidate(
        ticker="T", name="AT&T Inc.", sector="Telecom",
        approx_price=22, dividend_yield=5.5, avg_iv_rank=25,
        options_liquidity="high", capital_per_contract=2200,
        notes="Very low capital. High yield. Range-bound = ideal for wheel.",
    ),
]

ETF_INDEX_CANDIDATES = [
    WheelCandidate(
        ticker="SPY", name="SPDR S&P 500 ETF", sector="Broad Market",
        approx_price=520, dividend_yield=1.3, avg_iv_rank=25,
        options_liquidity="high", capital_per_contract=52000,
        notes="Most liquid options in the world. High capital needed.",
    ),
    WheelCandidate(
        ticker="QQQ", name="Invesco QQQ Trust", sector="Nasdaq 100",
        approx_price=440, dividend_yield=0.6, avg_iv_rank=30,
        options_liquidity="high", capital_per_contract=44000,
        notes="Tech-heavy. Higher IV than SPY = better premiums.",
    ),
    WheelCandidate(
        ticker="IWM", name="iShares Russell 2000", sector="Small Cap",
        approx_price=200, dividend_yield=1.3, avg_iv_rank=35,
        options_liquidity="high", capital_per_contract=20000,
        notes="Higher IV than SPY. Good for premium sellers.",
    ),
    WheelCandidate(
        ticker="EEM", name="iShares MSCI Emerging", sector="Emerging Mkts",
        approx_price=42, dividend_yield=2.5, avg_iv_rank=30,
        options_liquidity="high", capital_per_contract=4200,
        notes="Very low capital. Decent premiums from EM volatility.",
    ),
    WheelCandidate(
        ticker="XLF", name="Financial Select SPDR", sector="Financials",
        approx_price=42, dividend_yield=1.6, avg_iv_rank=25,
        options_liquidity="high", capital_per_contract=4200,
        notes="Sector ETF. Low capital, diversified financials exposure.",
    ),
    WheelCandidate(
        ticker="XLE", name="Energy Select SPDR", sector="Energy",
        approx_price=85, dividend_yield=3.5, avg_iv_rank=35,
        options_liquidity="high", capital_per_contract=8500,
        notes="Energy sector. Higher IV + dividends. Cyclical.",
    ),
    WheelCandidate(
        ticker="GLD", name="SPDR Gold Shares", sector="Commodities",
        approx_price=220, dividend_yield=0.0, avg_iv_rank=20,
        options_liquidity="high", capital_per_contract=22000,
        notes="Non-correlated to equities. Portfolio diversifier.",
    ),
    WheelCandidate(
        ticker="TLT", name="iShares 20+ Year Treasury", sector="Bonds",
        approx_price=90, dividend_yield=3.8, avg_iv_rank=30,
        options_liquidity="high", capital_per_contract=9000,
        notes="Bond ETF. Negative correlation to stocks. Good hedge.",
    ),
]

REIT_CANDIDATES = [
    WheelCandidate(
        ticker="O", name="Realty Income Corp.", sector="REIT",
        approx_price=55, dividend_yield=5.5, avg_iv_rank=25,
        options_liquidity="medium", capital_per_contract=5500,
        notes="Monthly dividend. 'The Monthly Dividend Company.'",
    ),
    WheelCandidate(
        ticker="SCHD", name="Schwab US Dividend Equity", sector="Dividend ETF",
        approx_price=78, dividend_yield=3.5, avg_iv_rank=20,
        options_liquidity="medium", capital_per_contract=7800,
        notes="Quality dividend ETF. Lower IV but very stable.",
    ),
]

ALL_CANDIDATES = (
    BLUE_CHIP_STOCKS
    + HIGH_DIVIDEND_STOCKS
    + ETF_INDEX_CANDIDATES
    + REIT_CANDIDATES
)


def filter_by_capital(max_capital: float) -> list[WheelCandidate]:
    """Return candidates affordable within a capital budget."""
    return [c for c in ALL_CANDIDATES if c.capital_per_contract <= max_capital]


def filter_by_sector(sector: str) -> list[WheelCandidate]:
    """Return candidates in a given sector."""
    sector_lower = sector.lower()
    return [c for c in ALL_CANDIDATES if sector_lower in c.sector.lower()]


def filter_by_min_dividend(min_yield: float) -> list[WheelCandidate]:
    """Return candidates with dividend yield >= min_yield."""
    return [c for c in ALL_CANDIDATES if c.dividend_yield >= min_yield]


def rank_by_iv(descending: bool = True) -> list[WheelCandidate]:
    """Rank candidates by IV rank (higher IV = higher premiums)."""
    return sorted(ALL_CANDIDATES, key=lambda c: c.avg_iv_rank, reverse=descending)


def print_candidates(candidates: list[WheelCandidate], title: str = "Candidates"):
    """Pretty-print a list of candidates."""
    print(f"\n{'=' * 100}")
    print(f"  {title}")
    print(f"{'=' * 100}")
    header = f"{'Ticker':>6} | {'Name':<30} | {'Sector':<15} | {'Price':>8} | {'Div%':>5} | {'IV':>3} | {'Liquidity':<6}"
    print(header)
    print("-" * 100)
    for c in candidates:
        print(c.summary())
    print(f"\nTotal: {len(candidates)} candidates")


# --- Example Usage ---
if __name__ == "__main__":
    # Show all candidates
    print_candidates(ALL_CANDIDATES, "All Wheel Strategy Candidates")

    # Filter: what can I wheel with $10,000?
    affordable = filter_by_capital(10000)
    print_candidates(affordable, "Affordable Wheel Candidates (≤ $10,000)")

    # Filter: high dividend picks
    high_div = filter_by_min_dividend(3.0)
    print_candidates(high_div, "High Dividend Candidates (≥ 3.0%)")

    # Rank by IV (best premium potential)
    by_iv = rank_by_iv()
    print_candidates(by_iv, "Ranked by IV (Highest Premium Potential)")
