# Wheel Strategy Terminal

A Bloomberg-style live options income dashboard that scans 80+ tickers for wheel strategy opportunities: when to sell puts, buy stock, roll positions, or sell covered calls.

**Live demo**: [quantresearch-292122978848.us-central1.run.app](https://quantresearch-292122978848.us-central1.run.app/)

## What It Does

The terminal scans the market in real-time and tells you exactly what to do with each ticker based on quantitative criteria. No guesswork.

### Dashboard Tabs

| Tab | What You See |
|---|---|
| **Opportunities** | All 80+ tickers sorted by IV rank, RSI, P/E with buy/sell signals |
| **Sell Puts** | Only tickers where selling a cash-secured put is the best move |
| **Accumulate** | Tickers to buy outright (IV too low for premiums to matter) |
| **Stand Aside** | Overbought, falling knives, or earnings risk - don't touch |
| **Basket** | Portfolio builder with pie charts, income estimates, 5Y backtest, risk slider |
| **Heatmap** | Sector-level heat map: oversold/overbought, click to drill into tickers |
| **Playbook** | Complete decision rules for every phase of the wheel |

### Ticker Detail (click any ticker)

Four sub-tabs on the right panel:

| Sub-Tab | Content |
|---|---|
| **Signal** | Entry action, valuation (P/E, PEG, P/B), technicals (RSI, SMA, 52w), CSP/CC setup |
| **Chart** | TradingView-style candlesticks, 20/50 EMA, 200 SMA, RSI-14, earnings markers, volume profile, buy/sell signal overlays. Timeframes: 1D/5D/1M/3M/6M/1Y/2Y/5Y |
| **Options** | Full option chain with delta, bid/ask/last, IV, OI. Auto-recommends best expiry (30-45 DTE) and optimal strikes (0.20-0.30 delta). Earnings flag on expirations |
| **Fundamentals** | Company profile, profitability (margins, ROE, ROA), balance sheet (cash, debt, FCF), dividends, growth rates, analyst targets, recent news |

### Chart Features

- Candlestick chart with 20 EMA (yellow), 50 EMA (blue), 200 SMA (purple dashed)
- RSI-14 sub-chart with overbought (70) and oversold (30) lines
- Toggle overlays: **Vol Profile** (TradingView-style horizontal buy/sell bars with POC), **Earnings** (historical + upcoming), **SMA Signals**
- Signal markers on chart:
  - Green arrow = SELL PUT (RSI < 30, above 200 SMA, IV rich)
  - Blue arrow = BUY STOCK (RSI oversold)
  - Purple circle = 200 SMA support touch
  - Yellow arrow = OVERBOUGHT (RSI > 70)
  - Red arrow = SELL CALL (RSI > 75)
  - Orange square = EARNINGS (with date + EPS estimate/actual)
- 8 timeframes from 15-minute intraday to 5-year daily

### Portfolio Basket Builder

- Preset sizes: $25K, $50K, $100K, $300K, $1M
- Risk tolerance slider (5-40% max drawdown)
- Composite scoring: yield + value + momentum + risk
- Concentration limits: 20% per ticker, 35% per sector, 25% cash buffer
- Pie charts for ticker and sector allocation
- Annual income estimate (dividends + option premiums)
- 5-year portfolio backtest with equity curve, drawdown chart, Sharpe ratio, vs SPY benchmark
- Year-by-year return breakdown

### Gemini AI Assistant

- Slide-out chat panel (AI button, bottom-right)
- Powered by Gemini 2.5 Flash with function-calling (agentic, not RAG)
- 5 tools Gemini can call interactively:
  - `get_scan_summary()` - all tickers ranked by ROC
  - `get_ticker_detail(ticker)` - deep dive on any ticker
  - `get_sector_heatmap()` - sector-level analysis
  - `get_best_puts(max_capital)` - top put opportunities
  - `get_best_buys()` - best accumulation candidates
- Full wheel playbook in system prompt
- Ticker context auto-loaded when you click a ticker

### Interactive Guided Tour

Click the green **Guide** button (next to Playbook) to start a 15-step interactive walkthrough that highlights every feature of the dashboard with tooltips. Restart anytime.

Tour steps are defined in `option_strategies/dashboard/static/tour.js` — edit the `TOUR_STEPS` array to add, remove, or reorder steps. No rebuild needed for content changes.

### Search & Clickable Tickers

- **Search box** at top of ticker table — type any ticker, company name, or sector to filter instantly
- **Clickable tickers in Gemini chat** — when AI suggests a ticker like SLB, click it to jump directly to that ticker's detail view

## The Playbook

### Phase 1: Entry

```
IV Rank >= 50  -->  SELL PUT at 0.20 delta, 30-45 DTE
IV Rank 30-50  -->  SELL PUT at 0.25 delta, 30-45 DTE
IV Rank < 20   -->  BUY STOCK outright
```

Additional smart filters:
- RSI > 70 + P/E > 40 = STAND ASIDE (overbought + expensive)
- RSI < 30 + above 200 SMA = prime accumulation (BUY or aggressive PUT)
- 10-25% off 52-week high = pullback sweet spot
- \>10% below 200 SMA = falling knife, STAND ASIDE
- Earnings inside DTE = STAND ASIDE

### Phase 2: Put Management

```
50% profit      -->  CLOSE, re-sell 30-45 DTE
ITM < 3%        -->  ROLL SAME STRIKE +30d (credit only)
ITM 3-8%        -->  ROLL DOWN 1-2 strikes +45d (credit only)
ITM > 8%        -->  ACCEPT ASSIGNMENT
```
**Never roll for a debit.**

### Phase 3: Covered Call After Assignment

```
Stock > 5% above cost basis  -->  0.30-0.40 delta (get called away)
Stock near cost basis        -->  0.25 delta (standard)
Stock 2-10% below basis      -->  0.15-0.20 delta (patient)
Stock > 10% below basis      -->  0.10-0.15 delta (wait)
```
**Never sell a call below adjusted cost basis.**

### Phase 4: Call Management

```
50% profit                   -->  Close, re-sell
ITM <= 7 DTE, above basis   -->  LET CALL AWAY (cycle complete)
ITM <= 7 DTE, below basis   -->  Roll up and out
Stock fell > 8%              -->  Roll call down (above basis)
```

## Ticker Universe (80+ tickers, 7 groups)

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
    app.py              FastAPI backend (10 API endpoints)
    daily_scanner.py    Live scanner engine
    gemini_prompt.py    AI system prompt with full playbook
    templates/
      index.html        Single-page dashboard UI
    static/
      style.css         Dark terminal theme
  wheel_criteria.py     Ticker universe + entry evaluation
  wheel_decision_engine.py  Full lifecycle rules
  option_pricing.py     Black-Scholes pricing
  Dockerfile            Container definition
  service.yaml          Cloud Run manifest
  requirements.txt      Python dependencies
```

### API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/scan` | Run live scan on all tickers |
| `GET /api/latest` | Return cached last scan |
| `GET /api/chart/{ticker}?tf=1Y` | OHLCV + indicators + signals + earnings + volume profile |
| `GET /api/options/{ticker}?expiry=...` | Option chain with delta + recommended strikes |
| `GET /api/fundamentals/{ticker}` | Company profile, financials, news |
| `GET /api/basket?size=50000&max_dd=20` | Optimized portfolio basket |
| `GET /api/basket/backtest?size=50000` | 5-year portfolio backtest |
| `GET /api/heatmap` | Sector-level heat map |
| `GET /api/playbook` | Decision rules as JSON |
| `POST /api/chat` | Gemini AI chat with function calling |
| `POST /api/login` | Password authentication |

## Run Locally

```bash
cd option_strategies
pip install -r requirements.txt
uvicorn dashboard.app:app --port 8080
```

Or with Docker:
```bash
cd option_strategies
docker build -t wheel-dashboard .
docker run -p 8080:8080 \
  -e DASHBOARD_PASSWORD=rockit \
  -e GEMINI_API_KEY=your-key \
  wheel-dashboard
```

## Deploy to GCP Cloud Run

```bash
cd option_strategies
gcloud run deploy wheel-dashboard \
  --source=. \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars="DASHBOARD_PASSWORD=rockit,GEMINI_API_KEY=your-key"
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DASHBOARD_PASSWORD` | `rockit` | Login password |
| `GEMINI_API_KEY` | (none) | Google Gemini API key for AI chat |
| `PORT` | `8080` | Server port |

## Roadmap

### Completed
- [x] Decision engine (entry, put mgmt, CC, call mgmt)
- [x] Live scanner with 80+ tickers, RSI, IVR, P/E, trend
- [x] Bloomberg-style dashboard with sortable/filterable table
- [x] TradingView charts with EMAs, RSI, volume, 8 timeframes
- [x] Chart signals (buy/sell/support/overbought overlays)
- [x] Earnings markers (historical + upcoming with EPS)
- [x] Volume profile (TradingView-style horizontal buy/sell bars)
- [x] Option chain with delta, recommended strikes, earnings flags
- [x] Company fundamentals + news
- [x] Portfolio basket builder with risk slider and 5Y backtest
- [x] Sector heatmap
- [x] Gemini AI chat with function calling (agentic)
- [x] Password protection
- [x] Docker + Cloud Run deployment

### Next Up
- [ ] Earnings calendar integration (auto-skip earnings in signals)
- [ ] Real IV rank from option chain (replace HV proxy)
- [ ] Position tracker (track open puts, assigned shares, active CCs)
- [ ] Roll advisor with live chain ("roll to X strike for $Y credit")
- [ ] Alerts / notifications (Slack/email on entry signals)
- [ ] Scheduled auto-scan (Cloud Scheduler cron)
- [ ] P&L tracking (log trades, cumulative premium income)
- [ ] MCP server (expose tools for any AI agent)
- [ ] Broker integration (IBKR API for positions + execution)
- [ ] Correlation matrix (portfolio clustering detection)
- [ ] Greeks dashboard (portfolio-level delta, theta, vega)
- [ ] Dynamic ticker discovery (screen full market, not just curated list)

## Data Sources

- **Price data**: Yahoo Finance via yfinance (real-time during market hours)
- **Option chains**: Yahoo Finance (bid/ask live during hours, last price after hours)
- **Fundamentals**: Yahoo Finance (P/E, margins, balance sheet, news)
- **Earnings**: Yahoo Finance (historical + upcoming dates with EPS)
- **IV Rank**: Realized volatility rank over 180 trading days (proxy)
- **Signals**: RSI-14 crossovers, 200 SMA support, IV rank thresholds
