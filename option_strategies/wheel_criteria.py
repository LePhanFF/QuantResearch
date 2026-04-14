"""
Wheel Strategy Ticker Universe & Entry Criteria
================================================

74 tickers grouped into 7 categories for diversified wheel income:

  INDEX ETFs (9)        : SPY, SPLG, QQQ, QQQM, DIA, XLK, XLV, XLI, XLRE
  MEGA-CAP (6)          : AAPL, MSFT, AMZN, GOOGL, META, BRK-B
  HIGH IV / GROWTH (6)  : NVDA, AMD, TSLA, NFLX, CRM, DIS
  DIVIDEND STAPLES (4)  : KO, PEP, JNJ, (+ MO, PM in income)
  FINANCIALS (7)        : JPM, BAC, V, MA, C, GS, XLF
  INCOME / YIELD (16)   : ABBV, O, T, VZ, MO, PM, CVX, XOM, PFE, BMY,
                          SCHD, VYM, JEPI, SPG, VNQ, XLE
  HEDGES / ALTS (4)     : IWM, GLD, TLT, EEM

Sizing guide:
  Small ($10-25k) : T, PFE, SCHD, SPLG, XLRE, XLF, XLE, BAC, VZ, MO, EEM, O, BMY, JEPI
  Mid ($25-50k)   : + QQQM, AAPL, AMD, NVDA, DIS, NFLX, KO, TLT, VNQ, AMZN, CRM, C
  Large ($50k+)   : + SPY, QQQ, MSFT, GOOGL, META, BRK-B, JPM, V, MA, GS, GLD, DIA, IWM
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
    WheelTicker(
        ticker="DIA", name="SPDR Dow Jones ETF", sector="Index",
        instrument="etf", approx_price=482, multiplier=100,
        notional_per_contract=48_200, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=35,
        dividend_yield=1.6, quality_score=9,
        notes="Dow 30 blue chips. Higher dividend than SPY. Value tilt.",
    ),
    WheelTicker(
        ticker="XLK", name="Technology Select SPDR", sector="Technology",
        instrument="etf", approx_price=146, multiplier=100,
        notional_per_contract=14_600, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=70,
        dividend_yield=0.6, quality_score=9,
        notes="Tech sector ETF. Mid-capital alternative to QQQ.",
    ),
    WheelTicker(
        ticker="XLV", name="Health Care Select SPDR", sector="Healthcare",
        instrument="etf", approx_price=148, multiplier=100,
        notional_per_contract=14_800, avg_iv_rank=20,
        options_liquidity="high", market_cap_b=40,
        dividend_yield=1.5, quality_score=9,
        notes="Broad healthcare sector. Defensive, lower IV.",
    ),
    WheelTicker(
        ticker="XLI", name="Industrial Select SPDR", sector="Industrials",
        instrument="etf", approx_price=173, multiplier=100,
        notional_per_contract=17_300, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=20,
        dividend_yield=1.3, quality_score=8,
        notes="Industrials sector. Cyclical, infrastructure-linked.",
    ),
    WheelTicker(
        ticker="XLRE", name="Real Estate Select SPDR", sector="Real Estate",
        instrument="etf", approx_price=43, multiplier=100,
        notional_per_contract=4_300, avg_iv_rank=25,
        options_liquidity="medium", market_cap_b=8,
        dividend_yield=3.2, quality_score=8,
        notes="REIT sector ETF. Very low capital. Rate sensitive.",
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
    WheelTicker(
        ticker="GOOGL", name="Alphabet Inc.", sector="Technology",
        instrument="stock", approx_price=321, multiplier=100,
        notional_per_contract=32_100, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=2_000,
        dividend_yield=0.5, quality_score=10,
        notes="Search + Cloud + AI. Recently started paying dividends.",
    ),
    WheelTicker(
        ticker="META", name="Meta Platforms Inc.", sector="Technology",
        instrument="stock", approx_price=635, multiplier=100,
        notional_per_contract=63_500, avg_iv_rank=40,
        options_liquidity="high", market_cap_b=1_600,
        dividend_yield=0.3, quality_score=9,
        notes="Social + AI + Metaverse. High IV = great premiums. Capital heavy.",
    ),
    WheelTicker(
        ticker="BRK-B", name="Berkshire Hathaway B", sector="Conglomerate",
        instrument="stock", approx_price=480, multiplier=100,
        notional_per_contract=48_000, avg_iv_rank=20,
        options_liquidity="high", market_cap_b=1_100,
        dividend_yield=0.0, quality_score=10,
        notes="Buffett's conglomerate. Ultra-quality, low IV. Often a BUY STOCK.",
    ),

    # =================================================================
    # GROUP 3: HIGH IV / GROWTH  (best premiums, more volatile)
    # =================================================================
    WheelTicker(
        ticker="NVDA", name="NVIDIA Corp.", sector="Semiconductors",
        instrument="stock", approx_price=189, multiplier=100,
        notional_per_contract=18_900, avg_iv_rank=50,
        options_liquidity="high", market_cap_b=4_600,
        dividend_yield=0.0, quality_score=9,
        notes="AI leader. Very high IV = excellent premiums. Use 0.15-0.20 delta.",
    ),
    WheelTicker(
        ticker="AVGO", name="Broadcom Inc.", sector="Semiconductors",
        instrument="stock", approx_price=379, multiplier=100,
        notional_per_contract=37_900, avg_iv_rank=40,
        options_liquidity="high", market_cap_b=880,
        dividend_yield=1.0, quality_score=9,
        notes="AI + networking chips. Dividend-paying semi. High IV.",
    ),
    WheelTicker(
        ticker="TSM", name="Taiwan Semiconductor", sector="Semiconductors",
        instrument="stock", approx_price=380, multiplier=100,
        notional_per_contract=38_000, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=1_970,
        dividend_yield=1.0, quality_score=10,
        notes="World's foundry. Makes chips for AAPL/NVDA/AMD. Geopolitical risk.",
    ),
    WheelTicker(
        ticker="AMD", name="Advanced Micro Devices", sector="Semiconductors",
        instrument="stock", approx_price=247, multiplier=100,
        notional_per_contract=24_700, avg_iv_rank=50,
        options_liquidity="high", market_cap_b=400,
        dividend_yield=0.0, quality_score=8,
        notes="High IV = best premiums. Use wider OTM (0.15-0.20 delta).",
    ),
    WheelTicker(
        ticker="TXN", name="Texas Instruments", sector="Semiconductors",
        instrument="stock", approx_price=216, multiplier=100,
        notional_per_contract=21_600, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=195,
        dividend_yield=2.8, quality_score=9,
        notes="Analog chip leader. Dividend aristocrat among semis.",
    ),
    WheelTicker(
        ticker="INTC", name="Intel Corp.", sector="Semiconductors",
        instrument="stock", approx_price=62, multiplier=100,
        notional_per_contract=6_200, avg_iv_rank=45,
        options_liquidity="high", market_cap_b=265,
        dividend_yield=0.0, quality_score=7,
        notes="Turnaround play. Very low capital, high IV = good premiums.",
    ),
    WheelTicker(
        ticker="TSLA", name="Tesla Inc.", sector="Auto/Energy",
        instrument="stock", approx_price=352, multiplier=100,
        notional_per_contract=35_200, avg_iv_rank=60,
        options_liquidity="high", market_cap_b=1_100,
        dividend_yield=0.0, quality_score=7,
        notes="Highest IV on list. Huge premiums but volatile. Use 0.15 delta max.",
    ),
    WheelTicker(
        ticker="NFLX", name="Netflix Inc.", sector="Entertainment",
        instrument="stock", approx_price=103, multiplier=100,
        notional_per_contract=10_300, avg_iv_rank=40,
        options_liquidity="high", market_cap_b=450,
        dividend_yield=0.0, quality_score=8,
        notes="Streaming leader. Low capital, decent IV. Watch earnings.",
    ),
    WheelTicker(
        ticker="CRM", name="Salesforce Inc.", sector="Software",
        instrument="stock", approx_price=173, multiplier=100,
        notional_per_contract=17_300, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=165,
        dividend_yield=0.6, quality_score=8,
        notes="Enterprise SaaS leader. Recently started dividends.",
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
    # GROUP 4: DIVIDEND STAPLES & CONSUMER  (quality you want to own)
    # =================================================================
    WheelTicker(
        ticker="COST", name="Costco Wholesale", sector="Consumer Staples",
        instrument="stock", approx_price=974, multiplier=100,
        notional_per_contract=97_400, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=430,
        dividend_yield=0.5, quality_score=10,
        notes="Premium quality retailer. Very high capital. Low IV = buy stock.",
    ),
    WheelTicker(
        ticker="WMT", name="Walmart Inc.", sector="Consumer Staples",
        instrument="stock", approx_price=125, multiplier=100,
        notional_per_contract=12_500, avg_iv_rank=20,
        options_liquidity="high", market_cap_b=680,
        dividend_yield=1.0, quality_score=10,
        notes="Largest retailer. Defensive, dividend grower.",
    ),
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
        ticker="MCD", name="McDonald's Corp.", sector="Consumer Staples",
        instrument="stock", approx_price=302, multiplier=100,
        notional_per_contract=30_200, avg_iv_rank=20,
        options_liquidity="high", market_cap_b=220,
        dividend_yield=2.3, quality_score=9,
        notes="Dividend aristocrat. Global franchise. Defensive.",
    ),
    WheelTicker(
        ticker="HD", name="Home Depot Inc.", sector="Consumer",
        instrument="stock", approx_price=341, multiplier=100,
        notional_per_contract=34_100, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=340,
        dividend_yield=2.5, quality_score=9,
        notes="Home improvement leader. Cyclical but quality dividend.",
    ),
    WheelTicker(
        ticker="LOW", name="Lowe's Companies", sector="Consumer",
        instrument="stock", approx_price=247, multiplier=100,
        notional_per_contract=24_700, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=140,
        dividend_yield=1.9, quality_score=8,
        notes="Home improvement #2. Pairs with HD, slightly higher IV.",
    ),
    WheelTicker(
        ticker="TGT", name="Target Corp.", sector="Consumer Staples",
        instrument="stock", approx_price=119, multiplier=100,
        notional_per_contract=11_900, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=55,
        dividend_yield=3.7, quality_score=8,
        notes="Higher IV + dividend. More volatile than WMT/COST.",
    ),
    WheelTicker(
        ticker="SBUX", name="Starbucks Corp.", sector="Consumer Staples",
        instrument="stock", approx_price=98, multiplier=100,
        notional_per_contract=9_800, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=110,
        dividend_yield=2.5, quality_score=8,
        notes="Global coffee brand. Turnaround story. Decent premium.",
    ),
    WheelTicker(
        ticker="NKE", name="Nike Inc.", sector="Consumer",
        instrument="stock", approx_price=44, multiplier=100,
        notional_per_contract=4_400, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=65,
        dividend_yield=2.2, quality_score=7,
        notes="Very low capital. At multi-year lows. Turnaround candidate.",
    ),
    WheelTicker(
        ticker="JNJ", name="Johnson & Johnson", sector="Healthcare",
        instrument="stock", approx_price=238, multiplier=100,
        notional_per_contract=23_800, avg_iv_rank=20,
        options_liquidity="high", market_cap_b=575,
        dividend_yield=3.0, quality_score=9,
        notes="Dividend king. 60+ years of increases. Defensive healthcare.",
    ),
    WheelTicker(
        ticker="UNH", name="UnitedHealth Group", sector="Healthcare",
        instrument="stock", approx_price=316, multiplier=100,
        notional_per_contract=31_600, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=580,
        dividend_yield=1.6, quality_score=10,
        notes="Largest health insurer. Quality compounder.",
    ),
    WheelTicker(
        ticker="LLY", name="Eli Lilly & Co.", sector="Healthcare",
        instrument="stock", approx_price=935, multiplier=100,
        notional_per_contract=93_500, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=890,
        dividend_yield=0.6, quality_score=9,
        notes="GLP-1 leader. Very high capital. Premium growth pharma.",
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
        ticker="BAC", name="Bank of America Corp.", sector="Financials",
        instrument="stock", approx_price=53, multiplier=100,
        notional_per_contract=5_300, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=330,
        dividend_yield=2.3, quality_score=8,
        notes="Low capital bank play. Pairs with JPM for size diversity.",
    ),
    WheelTicker(
        ticker="V", name="Visa Inc.", sector="Financials",
        instrument="stock", approx_price=309, multiplier=100,
        notional_per_contract=30_900, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=620,
        dividend_yield=0.7, quality_score=10,
        notes="Payment network duopoly. Premium quality, lower IV.",
    ),
    WheelTicker(
        ticker="MA", name="Mastercard Inc.", sector="Financials",
        instrument="stock", approx_price=509, multiplier=100,
        notional_per_contract=50_900, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=470,
        dividend_yield=0.6, quality_score=10,
        notes="Payment network duopoly. Capital heavy.",
    ),
    WheelTicker(
        ticker="C", name="Citigroup Inc.", sector="Financials",
        instrument="stock", approx_price=126, multiplier=100,
        notional_per_contract=12_600, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=240,
        dividend_yield=2.8, quality_score=7,
        notes="Turnaround story. Higher IV than JPM, decent dividend.",
    ),
    WheelTicker(
        ticker="GS", name="Goldman Sachs Group", sector="Financials",
        instrument="stock", approx_price=891, multiplier=100,
        notional_per_contract=89_100, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=290,
        dividend_yield=2.0, quality_score=9,
        notes="Investment bank leader. Very high capital per contract.",
    ),
    WheelTicker(
        ticker="XLF", name="Financial Select SPDR", sector="Financials",
        instrument="etf", approx_price=52, multiplier=100,
        notional_per_contract=5_200, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=45,
        dividend_yield=1.5, quality_score=8,
        notes="Broad financials exposure. Low capital alternative to single stocks.",
    ),

    # =================================================================
    # GROUP 6: INCOME / YIELD  (high dividends, steady income)
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
        ticker="VZ", name="Verizon Communications", sector="Telecom",
        instrument="stock", approx_price=45, multiplier=100,
        notional_per_contract=4_500, avg_iv_rank=20,
        options_liquidity="high", market_cap_b=190,
        dividend_yield=5.8, quality_score=7,
        notes="Highest dividend yield on list. Very low capital. Range-bound.",
    ),
    WheelTicker(
        ticker="MO", name="Altria Group Inc.", sector="Consumer Staples",
        instrument="stock", approx_price=67, multiplier=100,
        notional_per_contract=6_700, avg_iv_rank=20,
        options_liquidity="high", market_cap_b=115,
        dividend_yield=7.0, quality_score=7,
        notes="Tobacco. Ultra-high yield. Range-bound, low capital.",
    ),
    WheelTicker(
        ticker="PM", name="Philip Morris Intl", sector="Consumer Staples",
        instrument="stock", approx_price=163, multiplier=100,
        notional_per_contract=16_300, avg_iv_rank=20,
        options_liquidity="high", market_cap_b=250,
        dividend_yield=3.5, quality_score=8,
        notes="International tobacco + IQOS. Higher quality than MO.",
    ),
    WheelTicker(
        ticker="CVX", name="Chevron Corp.", sector="Energy",
        instrument="stock", approx_price=192, multiplier=100,
        notional_per_contract=19_200, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=340,
        dividend_yield=4.0, quality_score=9,
        notes="Integrated oil major. Strong dividend, cyclical premium.",
    ),
    WheelTicker(
        ticker="XOM", name="Exxon Mobil Corp.", sector="Energy",
        instrument="stock", approx_price=153, multiplier=100,
        notional_per_contract=15_300, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=630,
        dividend_yield=3.4, quality_score=9,
        notes="Largest oil company. Dividend aristocrat. Cyclical.",
    ),
    WheelTicker(
        ticker="PFE", name="Pfizer Inc.", sector="Healthcare",
        instrument="stock", approx_price=27, multiplier=100,
        notional_per_contract=2_700, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=155,
        dividend_yield=5.8, quality_score=7,
        notes="Pharma giant at multi-year lows. Very low capital, high yield.",
    ),
    WheelTicker(
        ticker="BMY", name="Bristol-Myers Squibb", sector="Healthcare",
        instrument="stock", approx_price=58, multiplier=100,
        notional_per_contract=5_800, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=120,
        dividend_yield=4.0, quality_score=7,
        notes="Big pharma. High yield, low capital. Watch patent cliffs.",
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
        ticker="VYM", name="Vanguard High Div Yield", sector="Dividend ETF",
        instrument="etf", approx_price=153, multiplier=100,
        notional_per_contract=15_300, avg_iv_rank=20,
        options_liquidity="medium", market_cap_b=60,
        dividend_yield=2.7, quality_score=9,
        notes="Broad high-yield ETF. Higher quality than individual yield traps.",
    ),
    WheelTicker(
        ticker="JEPI", name="JPMorgan Equity Premium", sector="Income ETF",
        instrument="etf", approx_price=58, multiplier=100,
        notional_per_contract=5_800, avg_iv_rank=15,
        options_liquidity="medium", market_cap_b=37,
        dividend_yield=7.5, quality_score=8,
        notes="Covered call ETF. Monthly income. Low IV = BUY STOCK candidate.",
    ),
    WheelTicker(
        ticker="SPG", name="Simon Property Group", sector="REIT",
        instrument="stock", approx_price=201, multiplier=100,
        notional_per_contract=20_100, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=65,
        dividend_yield=4.5, quality_score=8,
        notes="Premier mall REIT. Higher yield + IV than O.",
    ),
    WheelTicker(
        ticker="VNQ", name="Vanguard Real Estate ETF", sector="REIT",
        instrument="etf", approx_price=93, multiplier=100,
        notional_per_contract=9_300, avg_iv_rank=25,
        options_liquidity="medium", market_cap_b=35,
        dividend_yield=3.5, quality_score=8,
        notes="Broad REIT exposure. Diversified real estate income.",
    ),
    WheelTicker(
        ticker="XLE", name="Energy Select SPDR", sector="Energy",
        instrument="etf", approx_price=57, multiplier=100,
        notional_per_contract=5_700, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=40,
        dividend_yield=3.3, quality_score=8,
        notes="Energy sector ETF. Higher IV + dividends. Cyclical.",
    ),

    # =================================================================
    # GROUP 6b: INDUSTRIALS & DEFENSE  (cyclical income, infrastructure)
    # =================================================================
    WheelTicker(
        ticker="CAT", name="Caterpillar Inc.", sector="Industrials",
        instrument="stock", approx_price=789, multiplier=100,
        notional_per_contract=78_900, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=385,
        dividend_yield=1.4, quality_score=9,
        notes="Infrastructure king. Very high capital. Cyclical bellwether.",
    ),
    WheelTicker(
        ticker="HON", name="Honeywell Intl", sector="Industrials",
        instrument="stock", approx_price=232, multiplier=100,
        notional_per_contract=23_200, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=150,
        dividend_yield=2.0, quality_score=9,
        notes="Diversified industrial. Steady dividend, aerospace exposure.",
    ),
    WheelTicker(
        ticker="GE", name="GE Aerospace", sector="Industrials",
        instrument="stock", approx_price=317, multiplier=100,
        notional_per_contract=31_700, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=340,
        dividend_yield=0.6, quality_score=9,
        notes="Pure-play aerospace post-spinoff. Growth + defense.",
    ),
    WheelTicker(
        ticker="RTX", name="RTX Corp.", sector="Defense",
        instrument="stock", approx_price=202, multiplier=100,
        notional_per_contract=20_200, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=260,
        dividend_yield=2.1, quality_score=9,
        notes="Defense + aerospace. Dividend payer. Geopolitical hedge.",
    ),
    WheelTicker(
        ticker="LMT", name="Lockheed Martin", sector="Defense",
        instrument="stock", approx_price=611, multiplier=100,
        notional_per_contract=61_100, avg_iv_rank=20,
        options_liquidity="high", market_cap_b=145,
        dividend_yield=2.5, quality_score=9,
        notes="Premier defense contractor. High capital, stable dividend.",
    ),
    WheelTicker(
        ticker="UPS", name="United Parcel Service", sector="Industrials",
        instrument="stock", approx_price=102, multiplier=100,
        notional_per_contract=10_200, avg_iv_rank=30,
        options_liquidity="high", market_cap_b=85,
        dividend_yield=5.3, quality_score=8,
        notes="Logistics leader. High yield at current levels.",
    ),
    WheelTicker(
        ticker="NEE", name="NextEra Energy", sector="Utilities",
        instrument="stock", approx_price=91, multiplier=100,
        notional_per_contract=9_100, avg_iv_rank=25,
        options_liquidity="high", market_cap_b=185,
        dividend_yield=2.7, quality_score=9,
        notes="Largest utility. Renewable energy leader. Defensive income.",
    ),
    WheelTicker(
        ticker="SO", name="Southern Company", sector="Utilities",
        instrument="stock", approx_price=95, multiplier=100,
        notional_per_contract=9_500, avg_iv_rank=15,
        options_liquidity="high", market_cap_b=105,
        dividend_yield=3.4, quality_score=8,
        notes="Regulated utility. Ultra-stable. Low IV = buy stock.",
    ),
    WheelTicker(
        ticker="EOG", name="EOG Resources", sector="Energy",
        instrument="stock", approx_price=133, multiplier=100,
        notional_per_contract=13_300, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=75,
        dividend_yield=2.8, quality_score=8,
        notes="Top shale producer. High IV + dividend. Pairs with CVX/XOM.",
    ),
    WheelTicker(
        ticker="SLB", name="Schlumberger Ltd.", sector="Energy",
        instrument="stock", approx_price=51, multiplier=100,
        notional_per_contract=5_100, avg_iv_rank=35,
        options_liquidity="high", market_cap_b=70,
        dividend_yield=2.5, quality_score=7,
        notes="Oilfield services. Low capital, higher IV. Cyclical.",
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
