# Wheel Strategy Terminal

A live options income dashboard that scans 80+ tickers for wheel strategy opportunities: when to sell puts, buy stock, roll positions, or sell covered calls.

**Live demo**: [quantresearch-292122978848.us-central1.run.app](https://quantresearch-292122978848.us-central1.run.app/)

## What It Does

The terminal scans the market in real-time and tells you exactly what to do with each ticker based on quantitative criteria. No guesswork.

### Dashboard Views

| Tab | What You See |
|---|---|
| **Opportunities** | All 80 tickers sorted by IV rank, RSI, P/E with buy/sell signals |
| **Sell Puts** | Only tickers where selling a cash-secured put is the best move |
| **Accumulate** | Tickers to buy outright (IV too low for premiums to matter) |
| **Stand Aside** | Overbought, falling knives, or earnings risk - don't touch |
| **Basket** | Portfolio builder with pie charts, income estimates, 5Y backtest |
| **Playbook** | Complete decision rules for every phase of the wheel |

### What To Look For In Each Ticker

When you click a ticker, the dashboard shows:

**Chart (top right)**
- Candlestick chart with 20 EMA (yellow), 50 EMA (blue), 200 SMA (purple dashed)
- RSI-14 sub-chart with overbought (70) and oversold (30) lines
- Volume bars
- **Signal markers on the chart:**
  - Green arrow up = **SELL PUT** (RSI crossed below 30, above 200 SMA, IV rank > 30)
  - Blue arrow up = **BUY STOCK** (RSI oversold below 25, above 200 SMA)
  - Purple circle = **200 SMA support touch** (accumulation zone)
  - Yellow arrow down = **OVERBOUGHT** (RSI crossed above 70 - don't chase)
  - Red arrow down = **SELL CALL** (RSI > 75 - sell covered call aggressively)

**Detail panel (below chart)**
- Signal, delta, risk/reward rating, reasoning
- Valuation: P/E, forward P/E, PEG, Price/Book, EV/EBITDA
- Technicals: RSI, vs 50/200 SMA, 52-week position, 6-week return
- CSP setup: strike, premium, delta, annualized ROC, capital required
- If assigned: cost basis, covered call strike/premium/delta

**Option chain (below detail)**
- All strikes with delta, bid/ask/last, IV%, volume, open interest
- ATM row highlighted, auto-scrolls to center
- Expiry selector, puts/calls/both toggle

**Fundamentals (bottom)**
- Company profile, sector, industry
- Profitability: margins, ROE, ROA, growth rates
- Balance sheet: cash, debt, FCF
- Dividends: yield, payout ratio
- Recent news headlines with links

## The Playbook: When To Do What

### Phase 1: Entry (No Position)

```
IV Rank >= 50  -->  SELL PUT at 0.20 delta, 30-45 DTE
IV Rank 30-50  -->  SELL PUT at 0.25 delta, 30-45 DTE
IV Rank < 20   -->  BUY STOCK outright (premium not worth it)
```

**Sell put when:**
- IV Rank >= 30 (premium is at least average)
- RSI < 50 (not overbought)
- Above 200-day SMA (uptrend intact)
- No earnings within DTE window
- P/E not stretched above 40 with RSI > 70

**Buy stock outright when:**
- IV Rank < 20 (premium too thin for CSP)
- RSI < 30 + cheap P/E + above 200 SMA (prime accumulation dip)
- 10-25% pullback from 52-week high (pullback sweet spot)
- Strong breakout with low IV (don't miss the move)
- Ex-dividend before CSP expiry

**Stand aside when:**
- RSI > 70 AND P/E > 40 (overbought + expensive)
- Price > 10% below 200 SMA (falling knife)
- Below 200 SMA + IV Rank > 80 (crisis)
- Earnings inside the DTE window

### Phase 2: Manage Open Put

```
50% profit      -->  CLOSE, re-sell new 30-45 DTE
OTM, > 21 DTE   -->  HOLD (theta working)
OTM, <= 21 DTE   -->  Roll same strike +30d or close if >30% profit

ITM < 3%        -->  ROLL SAME STRIKE +30 days (must be for credit)
ITM 3-8%        -->  ROLL DOWN 1-2 strikes +45 days (must be for credit)
ITM > 8%        -->  ACCEPT ASSIGNMENT (rolling is too expensive)
```

**Never roll for a debit.** If you can't get a credit, take the shares.

### Phase 3: After Assignment (Sell Covered Call)

```
Stock > 5% above cost basis   -->  0.30-0.40 delta CC (get called away)
Stock near cost basis (+/-2%)  -->  0.25 delta CC (standard income)
Stock 2-10% below basis       -->  0.15-0.20 delta CC (patient)
Stock > 10% below basis       -->  0.10-0.15 delta CC (wait for recovery)
```

**Never sell a call below your adjusted cost basis** (strike - total premium collected).

### Phase 4: Manage Open Call

```
50% profit                    -->  Close, re-sell
ITM, <= 7 DTE, above basis   -->  LET IT GET CALLED AWAY (cycle complete!)
ITM, <= 7 DTE, below basis   -->  Roll up and out
Stock fell > 8% below strike  -->  Roll call down (never below cost basis)
```

Called away = cycle complete. Back to selling puts.

### Risk Limits

- Max 20% of account in any single ticker
- Max 35% in any single sector
- Keep 25% cash buffer for assignments
- DTE sweet spot: 30-45 days

## Ticker Universe (80 tickers)

| Group | Tickers |
|---|---|
| **Index ETFs** | SPY, SPLG, QQQ, QQQM, DIA, XLK, XLV, XLI, XLRE |
| **Mega-Cap** | AAPL, MSFT, AMZN, GOOGL, META, BRK-B |
| **Growth / Semis** | NVDA, AVGO, TSM, AMD, TXN, INTC, MU, MRVL, TSLA, NFLX, CRM, DIS, SOFI, NU, MELI |
| **Consumer / Healthcare** | COST, WMT, KO, PEP, MCD, HD, LOW, TGT, SBUX, NKE, JNJ, UNH, LLY |
| **Financials** | JPM, BAC, V, MA, C, GS, XLF |
| **Income / Industrials** | ABBV, O, T, VZ, MO, PM, CVX, XOM, PFE, BMY, SCHD, VYM, JEPI, SPG, VNQ, XLE, CAT, HON, GE, RTX, LMT, UPS, NEE, SO, EOG, SLB |
| **Hedges / Alts** | IWM, GLD, TLT, EEM |

## Architecture

```
option_strategies/
  dashboard/
    app.py              FastAPI backend (7 API endpoints)
    daily_scanner.py    Live scanner engine (fetches prices, computes signals)
    templates/
      index.html        Single-page dashboard UI
    static/
      style.css         Dark terminal theme
  wheel_criteria.py     Ticker universe + entry evaluation
  wheel_decision_engine.py  Full lifecycle rules (entry/roll/assignment/CC)
  option_pricing.py     Black-Scholes pricing
  Dockerfile            Container definition
  service.yaml          Cloud Run manifest
  requirements.txt      Python dependencies
```

### API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/scan` | Run live scan on all tickers (fetches real-time data) |
| `GET /api/latest` | Return cached last scan |
| `GET /api/chart/{ticker}?tf=1Y` | OHLCV + indicators + signals (1D/5D/1M/3M/6M/1Y/2Y/5Y) |
| `GET /api/options/{ticker}?expiry=YYYY-MM-DD` | Option chain with delta |
| `GET /api/fundamentals/{ticker}` | Company profile, financials, news |
| `GET /api/basket?size=50000&max_dd=20` | Optimized portfolio basket |
| `GET /api/basket/backtest?size=50000&max_dd=20` | 5-year portfolio backtest |
| `GET /api/playbook` | Decision rules as JSON |

## Run Locally

```bash
cd option_strategies
pip install -r requirements.txt
uvicorn dashboard.app:app --port 8080
# Open http://localhost:8080
```

Or with Docker:

```bash
cd option_strategies
docker build -t wheel-dashboard .
docker run -p 8080:8080 wheel-dashboard
```

## Deploy to GCP Cloud Run

```bash
cd option_strategies
gcloud run deploy wheel-dashboard \
  --source=. \
  --region=us-central1 \
  --allow-unauthenticated
```

## Data Sources

- **Price data**: Yahoo Finance via yfinance (real-time during market hours)
- **Option chains**: Yahoo Finance (bid/ask live during market hours, last price after hours)
- **Fundamentals**: Yahoo Finance (P/E, margins, balance sheet, news)
- **IV Rank**: Computed as realized volatility rank over 180 trading days (proxy for true IV rank)
- **Signals**: RSI-14 crossovers, 200 SMA support, IV rank thresholds
