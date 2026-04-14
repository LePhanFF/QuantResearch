"""
Wheel Strategy Ticker Universe & Entry Criteria
================================================

Defines the ticker universe for the wheel strategy dashboard.
Uses equity ETFs (SPY, SPLG, QQQ, QQQM) for index exposure so
everything trades in a standard brokerage account.

Ticker list (12 underlyings):
  - 4 index ETFs : SPY, SPLG, QQQ, QQQM
  - 2 mega-cap   : AAPL, MSFT
  - 1 financial   : JPM
  - 1 healthcare  : ABBV
  - 1 staple      : KO
  - 1 REIT        : O
  - 1 dividend ETF: SCHD
  - 1 small-cap   : IWM
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
    # ── Index ETFs ──
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

    # ── Mega-cap tech ──
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

    # ── Financials ──
    WheelTicker(
        ticker="JPM", name="JPMorgan Chase & Co.", sector="Financials",
        instrument="stock", approx_price=308, multiplier=100,
        notional_per_contract=30_800, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=860,
        dividend_yield=2.0, quality_score=9,
        notes="Best-in-class US bank.",
    ),

    # ── Healthcare ──
    WheelTicker(
        ticker="ABBV", name="AbbVie Inc.", sector="Healthcare",
        instrument="stock", approx_price=211, multiplier=100,
        notional_per_contract=21_100, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=370,
        dividend_yield=3.2, quality_score=8,
        notes="High dividend + decent IV.",
    ),

    # ── Consumer staples ──
    WheelTicker(
        ticker="KO", name="Coca-Cola Co.", sector="Consumer Staples",
        instrument="stock", approx_price=78, multiplier=100,
        notional_per_contract=7_800, avg_iv_rank=20,
        options_liquidity="high", market_cap_b=335,
        dividend_yield=2.9, quality_score=9,
        notes="Dividend aristocrat. Low IV = often a BUY STOCK candidate.",
    ),

    # ── REIT ──
    WheelTicker(
        ticker="O", name="Realty Income Corp.", sector="REIT",
        instrument="stock", approx_price=63, multiplier=100,
        notional_per_contract=6_300, avg_iv_rank=25,
        options_liquidity="medium", market_cap_b=55,
        dividend_yield=5.4, quality_score=8,
        notes="Monthly dividend. Low capital.",
    ),

    # ── Dividend ETF ──
    WheelTicker(
        ticker="SCHD", name="Schwab US Dividend Equity", sector="Dividend ETF",
        instrument="etf", approx_price=31, multiplier=100,
        notional_per_contract=3_100, avg_iv_rank=20,
        options_liquidity="medium", market_cap_b=70,
        dividend_yield=3.6, quality_score=9,
        notes="Cheapest entry. Broad dividend exposure.",
    ),

    # ── Small-cap ETF ──
    WheelTicker(
        ticker="IWM", name="iShares Russell 2000", sector="Small Cap",
        instrument="etf", approx_price=259, multiplier=100,
        notional_per_contract=25_900, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=65,
        dividend_yield=1.3, quality_score=8,
        notes="Higher IV than SPY/QQQ. Good premium seller.",
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
