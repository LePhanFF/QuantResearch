"""
Wheel Strategy Ticker Universe & Entry Criteria
================================================

23 tickers grouped into 7 categories for diversified wheel income:

  INDEX ETFs (4)       : SPY, SPLG, QQQ, QQQM
  MEGA-CAP TECH (3)    : AAPL, MSFT, AMZN
  HIGH IV / GROWTH (2) : AMD, DIS
  DIVIDEND STAPLES (3) : KO, PEP, JNJ
  FINANCIALS (2)       : JPM, XLF
  INCOME / YIELD (5)   : ABBV, O, T, SCHD, XLE
  HEDGES / ALTS (4)    : IWM, GLD, TLT, EEM

Small accounts ($10-25k): T, SCHD, O, SPLG, XLF, XLE, EEM
Mid accounts ($25-50k):   + QQQM, AAPL, AMD, DIS, KO, PEP, TLT
Large accounts ($50k+):   + SPY, QQQ, MSFT, AMZN, JPM, JNJ, GLD, IWM, ABBV
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class WheelTicker:
    ticker: str
    name: str
    sector: str
    instrument: str          # "stock" or "etf"
    approx_price: float
    multiplier: int          # always 100 for equities/ETFs
    notional_per_contract: float
    avg_iv_rank: float
    options_liquidity: str   # "high", "medium", "low"
    market_cap_b: float
    dividend_yield: float
    quality_score: int       # 1-10
    notes: str = ""

    def position_cost(self, contracts: int = 1) -> float:
        return self.notional_per_contract * contracts

    def summary(self) -> str:
        return (
            f"{self.ticker:>5} | {self.name:<28} | {self.sector:<15} | "
            f"${self.approx_price:>8.2f} | "
            f"capital: ${self.notional_per_contract:>8,.0f} | "
            f"IVr {self.avg_iv_rank:>2.0f} | Q{self.quality_score}/10"
        )


# =====================================================================
# TICKER UNIVERSE (April 2026 approximate prices)
# =====================================================================

WHEEL_TICKERS: list[WheelTicker] = [

    # =================================================================
    # GROUP 1: INDEX ETFs  (broad market exposure, size with mini/full)
    # =================================================================
    WheelTicker(
        ticker="SPY", name="SPDR S&P 500 ETF", sector="Index",
        instrument="etf", approx_price=686, multiplier=100,
        notional_per_contract=68_600, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=550,
        dividend_yield=1.3, quality_score=10,
        notes="Most liquid options on earth. High capital per contract.",
    ),
    WheelTicker(
        ticker="SPLG", name="SPDR Portfolio S&P 500", sector="Index",
        instrument="etf", approx_price=80, multiplier=100,
        notional_per_contract=8_000, avg_iv_rank=25,
        options_liquidity="low", market_cap_b=45,
        dividend_yield=1.3, quality_score=9,
        notes="Mini SPY. ~1/9th the capital. Lower options liquidity — use limit orders.",
    ),
    WheelTicker(
        ticker="QQQ", name="Invesco QQQ Trust", sector="Nasdaq 100",
        instrument="etf", approx_price=617, multiplier=100,
        notional_per_contract=61_700, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=280,
        dividend_yield=0.6, quality_score=10,
        notes="Tech-heavy. Higher IV than SPY = better premiums.",
    ),
    WheelTicker(
        ticker="QQQM", name="Invesco Nasdaq-100 ETF", sector="Nasdaq 100",
        instrument="etf", approx_price=254, multiplier=100,
        notional_per_contract=25_400, avg_iv_rank=30,
        options_liquidity="medium", market_cap_b=35,
        dividend_yield=0.6, quality_score=9,
        notes="Mini QQQ. ~2/5th the capital. Moderate liquidity.",
    ),

    # =================================================================
    # GROUP 2: MEGA-CAP TECH  (liquid, high quality, growth)
    # =================================================================
    WheelTicker(
        ticker="AAPL", name="Apple Inc.", sector="Technology",
        instrument="stock", approx_price=258, multiplier=100,
        notional_per_contract=25_800, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=3_900,
        dividend_yield=0.4, quality_score=10,
        notes="Most liquid single-stock options.",
    ),
    WheelTicker(
        ticker="MSFT", name="Microsoft Corp.", sector="Technology",
        instrument="stock", approx_price=368, multiplier=100,
        notional_per_contract=36_800, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=2_750,
        dividend_yield=0.9, quality_score=10,
        notes="Cloud + AI. Capital heavy.",
    ),
    WheelTicker(
        ticker="AMZN", name="Amazon.com Inc.", sector="Technology",
        instrument="stock", approx_price=240, multiplier=100,
        notional_per_contract=24_000, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=2_000,
        dividend_yield=0.0, quality_score=10,
        notes="Post-split, accessible for wheel. Cloud + retail dominance.",
    ),

    # =================================================================
    # GROUP 3: HIGH IV / GROWTH  (best premiums, more volatile)
    # =================================================================
    WheelTicker(
        ticker="AMD", name="Advanced Micro Devices", sector="Semiconductors",
        instrument="stock", approx_price=247, multiplier=100,
        notional_per_contract=24_700, avg_iv_rank=50,
        options_liquidity="high", market_cap_b=400,
        dividend_yield=0.0, quality_score=8,
        notes="Highest IV on list = best premiums. Use wider OTM (0.15-0.20 delta).",
    ),
    WheelTicker(
        ticker="DIS", name="Walt Disney Co.", sector="Entertainment",
        instrument="stock", approx_price=101, multiplier=100,
        notional_per_contract=10_100, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=185,
        dividend_yield=0.9, quality_score=8,
        notes="Moderate capital, decent IV. Theme parks + streaming.",
    ),

    # =================================================================
    # GROUP 4: DIVIDEND STAPLES  (low vol, steady income, buy stock often)
    # =================================================================
    WheelTicker(
        ticker="KO", name="Coca-Cola Co.", sector="Consumer Staples",
        instrument="stock", approx_price=78, multiplier=100,
        notional_per_contract=7_800, avg_iv_rank=20,
        options_liquidity="high", market_cap_b=335,
        dividend_yield=2.9, quality_score=9,
        notes="Dividend aristocrat. Low IV = often a BUY STOCK candidate.",
    ),
    WheelTicker(
        ticker="PEP", name="PepsiCo Inc.", sector="Consumer Staples",
        instrument="stock", approx_price=156, multiplier=100,
        notional_per_contract=15_600, avg_iv_rank=20,
        options_liquidity="high", market_cap_b=215,
        dividend_yield=3.5, quality_score=9,
        notes="Dividend aristocrat. Stable, pairs with KO for staples exposure.",
    ),
    WheelTicker(
        ticker="JNJ", name="Johnson & Johnson", sector="Healthcare",
        instrument="stock", approx_price=238, multiplier=100,
        notional_per_contract=23_800, avg_iv_rank=20,
        options_liquidity="high", market_cap_b=575,
        dividend_yield=3.0, quality_score=9,
        notes="Dividend king. 60+ years of increases. Defensive healthcare.",
    ),

    # =================================================================
    # GROUP 5: FINANCIALS  (sector diversification, dividends)
    # =================================================================
    WheelTicker(
        ticker="JPM", name="JPMorgan Chase & Co.", sector="Financials",
        instrument="stock", approx_price=308, multiplier=100,
        notional_per_contract=30_800, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=860,
        dividend_yield=2.0, quality_score=9,
        notes="Best-in-class US bank.",
    ),
    WheelTicker(
        ticker="XLF", name="Financial Select SPDR", sector="Financials",
        instrument="etf", approx_price=52, multiplier=100,
        notional_per_contract=5_200, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=45,
        dividend_yield=1.5, quality_score=8,
        notes="Broad financials exposure. Low capital alternative to JPM.",
    ),

    # =================================================================
    # GROUP 6: INCOME / YIELD  (high dividends, lower growth)
    # =================================================================
    WheelTicker(
        ticker="ABBV", name="AbbVie Inc.", sector="Healthcare",
        instrument="stock", approx_price=211, multiplier=100,
        notional_per_contract=21_100, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=370,
        dividend_yield=3.2, quality_score=8,
        notes="High dividend + decent IV. Pharma pipeline risk at earnings.",
    ),
    WheelTicker(
        ticker="O", name="Realty Income Corp.", sector="REIT",
        instrument="stock", approx_price=63, multiplier=100,
        notional_per_contract=6_300, avg_iv_rank=25,
        options_liquidity="medium", market_cap_b=55,
        dividend_yield=5.4, quality_score=8,
        notes="Monthly dividend. Low capital. Rate sensitive.",
    ),
    WheelTicker(
        ticker="T", name="AT&T Inc.", sector="Telecom",
        instrument="stock", approx_price=26, multiplier=100,
        notional_per_contract=2_600, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=185,
        dividend_yield=4.0, quality_score=7,
        notes="Lowest capital on list. Range-bound = ideal wheel candidate.",
    ),
    WheelTicker(
        ticker="SCHD", name="Schwab US Dividend Equity", sector="Dividend ETF",
        instrument="etf", approx_price=31, multiplier=100,
        notional_per_contract=3_100, avg_iv_rank=20,
        options_liquidity="medium", market_cap_b=70,
        dividend_yield=3.6, quality_score=9,
        notes="Cheapest entry. Broad dividend exposure.",
    ),
    WheelTicker(
        ticker="XLE", name="Energy Select SPDR", sector="Energy",
        instrument="etf", approx_price=57, multiplier=100,
        notional_per_contract=5_700, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=40,
        dividend_yield=3.3, quality_score=8,
        notes="Energy sector. Higher IV + dividends. Cyclical diversifier.",
    ),

    # =================================================================
    # GROUP 7: HEDGES / ALTERNATIVES  (non-correlated, portfolio balance)
    # =================================================================
    WheelTicker(
        ticker="IWM", name="iShares Russell 2000", sector="Small Cap",
        instrument="etf", approx_price=259, multiplier=100,
        notional_per_contract=25_900, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=65,
        dividend_yield=1.3, quality_score=8,
        notes="Higher IV than SPY/QQQ. Small-cap diversification.",
    ),
    WheelTicker(
        ticker="GLD", name="SPDR Gold Shares", sector="Commodities",
        instrument="etf", approx_price=435, multiplier=100,
        notional_per_contract=43_500, avg_iv_rank=20,
        options_liquidity="high", market_cap_b=80,
        dividend_yield=0.0, quality_score=8,
        notes="Non-correlated to equities. Portfolio hedge. Capital heavy.",
    ),
    WheelTicker(
        ticker="TLT", name="iShares 20+ Year Treasury", sector="Bonds",
        instrument="etf", approx_price=87, multiplier=100,
        notional_per_contract=8_700, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=55,
        dividend_yield=3.8, quality_score=8,
        notes="Bond ETF. Negative equity correlation. Rate-sensitive hedge.",
    ),
    WheelTicker(
        ticker="EEM", name="iShares MSCI Emerging", sector="Emerging Markets",
        instrument="etf", approx_price=61, multiplier=100,
        notional_per_contract=6_100, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=20,
        dividend_yield=2.5, quality_score=7,
        notes="Low capital. EM volatility = decent premiums. Geographic diversifier.",
    ),
]

TICKER_MAP = {t.ticker: t for t in WHEEL_TICKERS}


# =====================================================================
# Entry evaluation (delegates to decision engine)
# =====================================================================

@dataclass
class TradeSignal:
    ticker: str
    action: str
    reason: str
    suggested_delta: Optional[float] = None
    suggested_dte_range: Optional[tuple[int, int]] = None


def evaluate(
    t: WheelTicker,
    *,
    current_iv_rank: float,
    above_200_sma: bool,
    earnings_within_dte: bool,
    in_strong_uptrend: bool = False,
    pct_from_200_sma: float = 0.0,
    ex_div_before_expiry: bool = False,
) -> TradeSignal:
    from wheel_decision_engine import evaluate_entry, Action

    decision = evaluate_entry(
        quality_score=t.quality_score,
        iv_rank=current_iv_rank,
        above_200_sma=above_200_sma,
        pct_from_200_sma=pct_from_200_sma,
        earnings_within_dte=earnings_within_dte,
        in_strong_uptrend=in_strong_uptrend,
        ex_div_before_expiry=ex_div_before_expiry,
    )

    action_str = {
        Action.SELL_PUT: "SELL_PUT",
        Action.BUY_STOCK: "BUY_STOCK",
        Action.STAND_ASIDE: "STAND_ASIDE",
    }.get(decision.action, "STAND_ASIDE")

    dte_range = None
    if decision.target_dte:
        dte_range = (decision.target_dte - 5, decision.target_dte + 10)

    return TradeSignal(
        ticker=t.ticker,
        action=action_str,
        reason=decision.reason,
        suggested_delta=decision.target_delta,
        suggested_dte_range=dte_range,
    )


def filter_by_account_size(account_size: float) -> list[WheelTicker]:
    max_per = account_size * 0.20
    return [t for t in WHEEL_TICKERS if t.position_cost() <= max_per]
