# Polymarket Trading Strategies with Claude AI

A research compendium of 5 profitable strategies people are using with Claude and AI to trade on Polymarket, the decentralized prediction market platform on Polygon.

## Background

Polymarket is a prediction market where users buy and sell shares in event outcomes (YES/NO) priced between $0.00 and $1.00. The price reflects the market's implied probability. When an event resolves, winning shares pay $1.00 and losing shares pay $0.00.

In 2025-2026, AI-powered trading bots — particularly those built with Claude — have emerged as dominant players. One viral example achieved a reported 1,322% return on a $1,000 investment in 48 hours. Another turned $313 into $414,000 in a single month trading crypto markets with a 98% win rate.

### Platform Basics

- **Fee structure**: 2% on profitable outcomes
- **Settlement**: On-chain (Polygon), using Conditional Token Framework (ERC-1155)
- **Order book**: Hybrid — off-chain matching, on-chain settlement
- **API**: Official Python SDK [`py-clob-client`](https://github.com/Polymarket/py-clob-client) (934 stars)
- **Market types**: Binary (YES/NO), Multi-outcome (NegRisk), Short-duration (5m/15m crypto)

---

## Strategy 1: Weather Forecast Arbitrage

**Edge**: Professional weather forecasts (NOAA, GFS, NWS) are more accurate than crowd-sourced Polymarket odds.

### How It Works

Polymarket hosts daily weather markets: "Will NYC high temperature exceed 75F tomorrow?" priced by crowd sentiment. Meanwhile, NOAA's 31-member GFS ensemble model produces calibrated probability distributions for temperature outcomes. When Polymarket prices diverge from the scientific forecast, the bot trades the gap.

### Claude's Role

- Parses and interprets raw NWS/GFS forecast data
- Compares ensemble probability distributions to Polymarket prices
- Identifies statistically significant mispricings
- Generates trade decisions with Kelly criterion position sizing

### Reported Results

| Trader | Profit | Period | Markets |
|--------|--------|--------|---------|
| Anonymous bot | $1,000 -> $24,000 | Since Apr 2025 | London weather |
| meropi | ~$30,000 | Ongoing | Micro bets ($1-3) at $0.01/share |
| 1pixel | $2,300 -> $18,500 | Ongoing | NYC + London weather |
| Multi-city bot | $65,000 | Ongoing | NYC, London, Seoul |

### Data Sources

- [NOAA GFS Ensemble](https://www.ncei.noaa.gov/products/weather-climate-models/global-forecast) — 31-member ensemble forecasts
- [Open-Meteo API](https://open-meteo.com/) — free weather forecast API
- [NWS API](https://www.weather.gov/documentation/services-web-api) — National Weather Service forecasts
- Polymarket temperature bucket markets

### Implementation Approach

```
1. Fetch GFS ensemble forecast for target city/date
2. Calculate probability distribution across temperature buckets
3. Compare to Polymarket prices for each bucket
4. If |forecast_prob - market_price| > threshold (typically 5-10%):
   - Buy underpriced outcomes
   - Sell overpriced outcomes
5. Size positions using fractional Kelly criterion
6. Monitor and exit as forecasts update
```

### Risk Factors

- Forecast busts (ensemble models aren't perfect)
- Thin liquidity in weather markets — slippage on entry/exit
- Resolution disputes on edge cases (e.g., temperature exactly at boundary)
- Competition from other weather bots narrowing the edge

### Open-Source Implementations

- [polymarket-kalshi-weather-bot](https://github.com/suislanchez/polymarket-kalshi-weather-bot) — GFS ensemble + Kelly sizing, reported $1.8k highest profits
- [Polymarket-Weather-Trading-Bot](https://github.com/solship/Polymarket-Weather-Trading-Bot) — NWS forecast-based scanner

---

## Strategy 2: Crypto Latency Arbitrage (BTC/ETH 5-15 Minute Markets)

**Edge**: Polymarket's short-duration crypto contracts reprice slower than spot prices on centralized exchanges.

### How It Works

Polymarket offers 5-minute and 15-minute "Will BTC go up or down?" markets. These resolve based on Chainlink price feeds. The key insight: when a strong price move happens on Binance/Coinbase, there's a brief window (seconds) where Polymarket odds haven't caught up. The bot buys the near-certain winning side before the market adjusts.

### Claude's Role

- Builds the trading bot infrastructure (one user reported Claude Code wrote ~4,000 lines in 10 minutes)
- Designs signal detection logic for spot price momentum
- Implements risk management and position sizing
- Debugs and optimizes execution speed

### Reported Results

- One bot: $313 -> $414,000 in one month, 98% win rate on BTC/ETH/SOL 15-min markets
- Average bet size: $4,000-$5,000 per trade
- Key metric: latency advantage has shrunk from 12.3 seconds (2024) to 2.7 seconds (Q1 2026)

### Data Sources

- Binance/Coinbase WebSocket feeds (real-time spot prices)
- Polymarket CLOB API (current odds + order book depth)
- Chainlink price feed (resolution oracle)

### Implementation Approach

```
1. Subscribe to Binance BTC/USDT WebSocket (tick-by-tick)
2. Subscribe to Polymarket 5m/15m BTC market WebSocket
3. Detect momentum signal:
   - Price moves >0.1% in <10 seconds on Binance
   - Volume spike confirmation
4. Check Polymarket odds — if they haven't adjusted:
   - Buy YES (if BTC pumping) or NO (if dumping)
   - Market order for speed, limit order if spread is wide
5. Hold to resolution (5 or 15 minutes)
6. Repeat
```

### Risk Factors

- **Latency arms race** — edge is shrinking rapidly, need dedicated Polygon RPC nodes
- **Whipsaw risk** — price reverses after initial move
- **Resolution timing** — Chainlink feed may sample at unfavorable moment
- **Capital requirements** — need significant size for thin margins to be meaningful
- **Competition** — HFT firms are entering this space

---

## Strategy 3: NegRisk Multi-Outcome Arbitrage

**Edge**: In multi-outcome markets (elections, awards), the sum of all YES prices should equal $1.00 but frequently doesn't.

### How It Works

Polymarket uses "NegRisk" contracts for mutually exclusive multi-outcome markets (e.g., "Who will win the election?" with 5 candidates). If the sum of all YES prices < $1.00, buy one share of every outcome for guaranteed profit. If > $1.00, sell/short the overpriced side.

Between April 2024 and April 2025, traders extracted an estimated **$40 million** from NegRisk rebalancing arbitrage.

### Claude's Role

- Monitors all active NegRisk markets simultaneously
- Calculates sum of YES prices across all outcomes in real-time
- Identifies when sum deviates beyond fee threshold (>2.5-3%)
- Executes multi-leg trades and tracks P&L

### The Math

```
Market: "Who wins Best Picture?" (5 nominees)
  Film A: $0.35 YES
  Film B: $0.28 YES
  Film C: $0.18 YES
  Film D: $0.10 YES
  Film E: $0.06 YES
  ─────────────────
  Total:  $0.97

Action: Buy 1 YES share of each film = $0.97 cost
Guaranteed payout: $1.00 (exactly one wins)
Profit: $0.03 per set (3.1% risk-free, minus 2% fee on winner = ~1% net)
```

### Reported Results

- IMDEA Networks study: $29M extracted from NegRisk rebalancing across 17,218 market conditions
- NegRisk arbitrage generated 73% of total arb profits despite being only 8.6% of opportunities
- 29x capital efficiency advantage over binary arbitrage

### Data Sources

- Polymarket Gamma API (market discovery)
- Polymarket CLOB API (real-time prices across all outcomes)
- On-chain data (settlement verification)

### Implementation Approach

```
1. Query Gamma API for all active NegRisk (multi-outcome) markets
2. For each market, fetch YES prices for all outcomes
3. Calculate sum = Σ(YES prices)
4. If sum < 0.97 (accounting for 2% fee + gas):
   - BUY all YES shares → guaranteed profit at resolution
5. If sum > 1.03:
   - SELL/SHORT overpriced outcomes (or mint + sell strategy)
6. Monitor continuously — mispricings last seconds during events
```

### Risk Factors

- **Non-atomic execution** — must buy multiple outcomes sequentially; prices can move between legs
- **Fee drag** — 2% fee on winning outcome eats into thin margins
- **Gas costs** on Polygon (small but adds up at scale)
- **Monopolized by HFT** — brief windows during emotional retail flow (30-60 seconds during news events)

### Reference

- Academic paper: [Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets](https://arxiv.org/abs/2508.03474) (arXiv:2508.03474)
- [NegRisk Market Rebalancing: How $29M Was Extracted](https://medium.com/@navnoorbawa/negrisk-market-rebalancing-how-29m-was-extracted-from-multi-condition-prediction-markets-2f1f91644c5b)

---

## Strategy 4: AI News Sentiment & Event Probability Estimation

**Edge**: Claude can process breaking news, government filings, social media, and economic data faster than humans to estimate true event probabilities.

### How It Works

For political, geopolitical, and policy markets (e.g., "Will the Fed cut rates in June?", "Will X bill pass the Senate?"), the bot continuously ingests news and data, uses Claude to estimate the true probability, and trades when the market price diverges from the AI's estimate.

This is the most "pure AI" strategy — it relies on Claude's reasoning ability rather than a mathematical edge like latency or arbitrage.

### Claude's Role

- **Primary analyst**: Reads and synthesizes breaking news articles, press releases, government filings
- **Probability estimator**: Outputs calibrated probability estimates with confidence intervals
- **Contrarian detector**: Identifies when market sentiment has overreacted to news
- **Multi-model ensemble**: Some implementations use GPT-4o + Claude + Gemini and average their probability estimates for better calibration

### Reported Results

- One ensemble bot (profiled by Igor Mikerin): **$2.2 million profit in 2 months**
- AI probability estimation bots vs humans using similar strategies: bots $206K profit (85%+ win rate) vs humans $100K
- Key: continual model retraining on resolution outcomes improves calibration over time

### Data Sources

- News APIs (NewsAPI, Google News, Reuters, AP)
- Government data (FRED, congressional voting records, executive orders)
- Social media sentiment (Twitter/X API, Reddit)
- Expert forecasts (Metaculus, Good Judgment Open, 538)
- Polymarket's own market history (for calibration)

### Implementation Approach

```
1. Market Selection:
   - Filter Polymarket for event markets with >$50k volume
   - Exclude sports and crypto (different strategies)
   - Focus on politics, policy, geopolitics, macro

2. Research Phase (Claude):
   - Gather all relevant news articles (last 24-72 hours)
   - Pull historical base rates for similar events
   - Analyze expert forecasts and prediction aggregators
   - Generate probability estimate with reasoning

3. Trading Decision:
   - Compare Claude's probability to Polymarket price
   - If |claude_prob - market_price| > 10%:
     - Trade in direction of Claude's estimate
     - Size using fractional Kelly (typically 1-5% of bankroll)
   - If divergence < 5%: no trade (within noise)

4. Position Management:
   - Re-evaluate daily as new information arrives
   - Adjust position if Claude's estimate shifts materially
   - Exit early if edge disappears (price converges)
```

### Risk Factors

- **AI hallucination** — Claude may confidently output wrong probabilities
- **Calibration drift** — AI models aren't naturally well-calibrated on tail events
- **Stale information** — model knowledge cutoff may miss recent developments
- **Black swan events** — no model handles true surprises well
- **Overconfidence** — AI tends to cluster estimates around 40-60%, missing extreme outcomes

### Open-Source Implementation

- [Fully-Autonomous-Polymarket-AI-Trading-Bot](https://github.com/dylanpersonguy/Fully-Autonomous-Polymarket-AI-Trading-Bot) — multi-model ensemble (GPT-4o, Claude, Gemini), 15+ risk checks, fractional Kelly sizing, 9-tab monitoring dashboard
- [Polymarket/agents](https://github.com/Polymarket/agents) — official Polymarket AI agent framework

---

## Strategy 5: Cross-Platform Arbitrage (Polymarket vs Kalshi vs PredictIt)

**Edge**: The same event can trade at different probabilities on different prediction markets.

### How It Works

If "Will Bitcoin exceed $100k by June?" trades at 55% on Polymarket but 65% on Kalshi, there's a 10-point spread. Buy YES on Polymarket ($0.55) and NO on Kalshi ($0.35) for a total cost of $0.90. One of the two must pay $1.00, guaranteeing $0.10 profit regardless of outcome.

### Claude's Role

- Matches equivalent markets across platforms (event descriptions differ)
- Normalizes contract terms (resolution criteria, timing, edge cases)
- Calculates net arbitrage after fees on both platforms
- Flags when contract terms aren't truly identical (a common trap)

### Platforms to Monitor

| Platform | Fee | Settlement | Focus |
|----------|-----|------------|-------|
| Polymarket | 2% on profit | On-chain (Polygon) | Crypto, politics, events |
| Kalshi | 7% on profit | USD (regulated) | Weather, economics, events |
| PredictIt | 10% on profit + 5% withdrawal | USD (regulated) | Politics |
| Metaculus | No trading (forecasting) | N/A | Science, technology |

### Implementation Approach

```
1. Build market matcher:
   - Scrape active markets from Polymarket, Kalshi, PredictIt
   - Use Claude to semantically match equivalent events
   - Normalize resolution criteria and dates

2. Price monitor:
   - Track real-time prices on all platforms
   - Calculate cross-platform spread for matched markets
   - Account for fees: Polymarket (2%), Kalshi (7%), PredictIt (15%)

3. Execute arbitrage:
   - When spread > combined fees + buffer (typically >5%):
     - Buy YES on cheap platform
     - Buy NO on expensive platform
   - Lock in guaranteed profit

4. Settlement tracking:
   - Monitor resolution on both platforms
   - Handle edge cases where platforms resolve differently
```

### Risk Factors

- **Resolution risk** — platforms may interpret the same event differently
- **Counterparty risk** — PredictIt/Kalshi are centralized; funds could be frozen
- **Fee asymmetry** — Kalshi's 7% fee makes small spreads unprofitable
- **Capital lockup** — funds tied up until event resolution (could be months)
- **Regulatory risk** — CFTC oversight varies by platform
- **Liquidity mismatch** — may get filled on one leg but not the other

---

## Comparative Summary

| Strategy | Edge Source | Claude's Role | Capital Needs | Competition | Difficulty |
|----------|-----------|---------------|--------------|-------------|------------|
| **Weather Arbitrage** | Forecast models > crowd | Data parsing, decision making | Low ($100+) | Moderate | Medium |
| **Crypto Latency** | Exchange speed > Polymarket | Bot building, optimization | High ($5k+) | Extreme (HFT) | Hard |
| **NegRisk Arb** | Math (probability sum != 1) | Monitoring, multi-leg execution | Medium ($1k+) | Extreme | Hard |
| **News Sentiment** | AI reasoning > crowd | Primary analyst & estimator | Low ($100+) | Moderate | Medium |
| **Cross-Platform** | Price differences between markets | Market matching, normalization | High ($5k+) | Low | Medium |

## Getting Started

### Prerequisites

```bash
pip install py-clob-client   # Polymarket Python SDK
```

### API Setup

The Polymarket CLOB API has 3 authentication levels:

| Level | Capabilities | Requirements |
|-------|-------------|--------------|
| Level 0 | Read-only (prices, markets, order book) | None |
| Level 1 | Generate API keys | Polygon wallet + signature |
| Level 2 | Place/cancel orders, manage positions | API key + approval |

### Key APIs

- **Gamma API**: Market discovery (search active markets, metadata)
- **CLOB API**: Trading (order book, place/cancel orders, prices)
- **Data API**: Portfolio (positions, trade history, P&L)
- **WebSocket**: Real-time price/order updates

### Useful Resources

- [Polymarket Developer Docs](https://docs.polymarket.com/quickstart/overview)
- [py-clob-client GitHub](https://github.com/Polymarket/py-clob-client)
- [Polymarket/agents](https://github.com/Polymarket/agents) — official AI agent framework
- [NautilusTrader Polymarket Integration](https://nautilustrader.io/docs/latest/integrations/polymarket/)

## Risk Disclaimer

Prediction markets involve substantial risk of loss. AI-generated probability estimates are not financial advice. Markets can move against you, liquidity can dry up, and models can be wrong. The CFTC has warned that fraudsters exploit AI hype to promote unrealistic returns. Start small, paper trade first, and only use money you can afford to lose.

The reported profit figures in this document come from self-reported sources and may not be independently verified. Past performance does not guarantee future results.

## Module Reference

| File | Description |
|------|-------------|
| `README.md` | This research document |
| `weather_arb.py` | Weather forecast arbitrage bot (planned) |
| `crypto_latency.py` | BTC/ETH latency arbitrage scanner (planned) |
| `negrisk_arb.py` | NegRisk multi-outcome arbitrage monitor (planned) |
| `news_sentiment.py` | AI news sentiment probability estimator (planned) |
| `cross_platform.py` | Cross-platform arbitrage scanner (planned) |

## Sources

- [Claude AI Trading Bots Are Making Hundreds of Thousands on Polymarket](https://medium.com/@weare1010/claude-ai-trading-bots-are-making-hundreds-of-thousands-on-polymarket-2840efb9f2cd) — Medium
- [AI Agent Claude Gains 1,322% on Polymarket in 48 Hours](https://phemex.com/news/article/ai-trading-agent-claude-achieves-1322-return-on-polymarket-65634) — Phemex
- [Building an Automated Polymarket Trading System with Claude Code](https://medium.com/@rvarkarlsson/building-an-automated-polymarket-trading-system-with-claude-code-1982ff60cc74) — Medium
- [Found The Weather Trading Bots Quietly Making $24,000 On Polymarket](https://blog.devgenius.io/found-the-weather-trading-bots-quietly-making-24-000-on-polymarket-and-built-one-myself-for-free-120bd34d6f09) — Dev Genius
- [How AI is Helping Retail Traders Exploit Prediction Market Glitches](https://www.coindesk.com/markets/2026/02/21/how-ai-is-helping-retail-traders-exploit-prediction-market-glitches-to-make-easy-money) — CoinDesk
- [Arbitrage Bots Dominate Polymarket With Millions in Profits](https://finance.yahoo.com/news/arbitrage-bots-dominate-polymarket-millions-100000888.html) — Yahoo Finance
- [NegRisk Market Rebalancing: How $29M Was Extracted](https://medium.com/@navnoorbawa/negrisk-market-rebalancing-how-29m-was-extracted-from-multi-condition-prediction-markets-2f1f91644c5b) — Medium
- [Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets](https://arxiv.org/abs/2508.03474) — arXiv
- [Polymarket Developer Docs](https://docs.polymarket.com/quickstart/overview)
- [Polymarket HFT: How Traders Use AI](https://www.quantvps.com/blog/polymarket-hft-traders-use-ai-arbitrage-mispricing) — QuantVPS
