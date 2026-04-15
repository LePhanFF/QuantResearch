/**
 * Interactive Guided Tour for the Wheel Strategy Terminal
 * ======================================================
 *
 * Uses Shepherd.js. To update the tour, edit the TOUR_STEPS array below.
 * Each step has:
 *   - id:       unique step identifier
 *   - title:    header text
 *   - text:     body text (HTML allowed)
 *   - attachTo: { element: CSS selector, on: position }
 *   - beforeShowPromise: (optional) async function to set up UI state
 *
 * Steps run in order. Add/remove/reorder as needed.
 */

const TOUR_STEPS = [
    {
        id: 'welcome',
        title: 'Welcome to the Wheel Terminal',
        text: `
            <p>This dashboard scans <b>80+ tickers</b> in real-time and tells you exactly what to do:</p>
            <ul>
                <li><b style="color:#22c55e">SELL PUT</b> — premium is rich, good entry</li>
                <li><b style="color:#3b82f6">BUY STOCK</b> — IV too low, just buy it</li>
                <li><b style="color:#eab308">STAND ASIDE</b> — overbought or risky</li>
            </ul>
            <p>Let's walk through each section.</p>
        `,
    },
    {
        id: 'scan-button',
        title: 'Live Scan',
        text: 'Click <b>SCAN</b> to fetch real-time data from Yahoo Finance for all tickers. The first scan runs automatically on load.',
        attachTo: { element: '#scan-btn', on: 'bottom' },
    },
    {
        id: 'summary-strip',
        title: 'Market Summary',
        text: 'Quick overview: how many tickers signal Sell Put vs Buy Stock, average IV rank, RSI, overbought/oversold counts.',
        attachTo: { element: '.summary-strip', on: 'bottom' },
    },
    {
        id: 'search-box',
        title: 'Search & Filter',
        text: 'Type any ticker, company name, or sector to instantly filter the table. Try typing <b>SLB</b> or <b>energy</b>.',
        attachTo: { element: '#ticker-search', on: 'bottom' },
    },
    {
        id: 'group-filter',
        title: 'Group Filter',
        text: 'Filter by category: <b>Index</b>, <b>Mega-Cap</b>, <b>Growth</b>, <b>Staples</b>, <b>Financials</b>, <b>Income</b>, or <b>Hedges</b>.',
        attachTo: { element: '.group-bar', on: 'bottom' },
    },
    {
        id: 'signal-tabs',
        title: 'Signal Tabs',
        text: `
            <b>Sell Puts</b> — only tickers where selling a put makes sense<br>
            <b>Accumulate</b> — buy outright (IV too low for premiums)<br>
            <b>Stand Aside</b> — overbought, falling knife, or earnings risk
        `,
        attachTo: { element: '.tabs', on: 'bottom' },
    },
    {
        id: 'ticker-table',
        title: 'Ticker Table',
        text: `
            Click any column header to sort. Key columns:<br>
            <b>RSI</b> — below 30 = oversold (green), above 70 = overbought (red)<br>
            <b>IVR</b> — above 50 = rich premium (green)<br>
            <b>ROC%</b> — annualized return on capital from selling a put<br>
            <b>R/R</b> — risk/reward: GOOD, FAIR, or POOR<br><br>
            <b>Click a ticker row</b> to see its full analysis on the right.
        `,
        attachTo: { element: '#ticker-table', on: 'right' },
    },
    {
        id: 'divider',
        title: 'Draggable Divider',
        text: 'Drag this bar left/right to resize the table and chart panels.',
        attachTo: { element: '#divider', on: 'right' },
    },
    {
        id: 'right-tabs',
        title: 'Ticker Detail Tabs',
        text: `
            When you click a ticker, four tabs appear:<br>
            <b>Signal</b> — entry decision, valuation, technicals, CSP/CC setup<br>
            <b>Chart</b> — TradingView-style with EMAs, RSI, signals, earnings<br>
            <b>Options</b> — full chain with recommended strikes<br>
            <b>Fundamentals</b> — financials, balance sheet, news
        `,
        attachTo: { element: '.right-tabs', on: 'bottom' },
    },
    {
        id: 'chart-features',
        title: 'Chart Features',
        text: `
            <b>Timeframes</b>: 1D (15-min bars) through 5Y (daily)<br>
            <b>Overlays</b>: 20 EMA (yellow), 50 EMA (blue), 200 SMA (purple)<br>
            <b>Toggles</b>: Volume Profile, Earnings markers, Buy/Sell signals<br>
            <b>Signal markers</b>:<br>
            &nbsp; Green arrow = SELL PUT &nbsp; Blue arrow = BUY<br>
            &nbsp; Yellow arrow = OVERBOUGHT &nbsp; Orange square = EARNINGS
        `,
        attachTo: { element: '.right-tabs', on: 'bottom' },
    },
    {
        id: 'options-chain',
        title: 'Option Chain',
        text: `
            Auto-selects the best expiry (30-45 DTE sweet spot).<br>
            <b>Green banner</b>: recommended put/call strikes at ~0.25 delta<br>
            <b>Green rows</b>: optimal theta zone (delta 0.20-0.30)<br>
            <b>Earnings flag</b>: warns if earnings fall before expiry<br>
            <b>Delta column</b>: Black-Scholes estimated delta for each strike
        `,
        attachTo: { element: '.right-tabs', on: 'bottom' },
    },
    {
        id: 'basket-tab',
        title: 'Portfolio Basket Builder',
        text: `
            Click the <b>Basket</b> tab to build an optimized portfolio:<br>
            <b>Size presets</b>: $25K, $50K, $100K, $300K, $1M<br>
            <b>Risk slider</b>: drag from conservative (5%) to aggressive (40% max drawdown)<br>
            <b>Pie charts</b>: ticker and sector allocation<br>
            <b>Income estimate</b>: annual dividends + option premiums<br>
            <b>5Y backtest</b>: equity curve vs SPY, drawdown chart, annual returns
        `,
        attachTo: { element: '.tabs', on: 'bottom' },
    },
    {
        id: 'heatmap-tab',
        title: 'Sector Heatmap',
        text: `
            Click <b>Heatmap</b> to see sectors at a glance:<br>
            <b style="color:#22c55e">Green border</b> = sector is oversold (opportunity)<br>
            <b style="color:#ef4444">Red border</b> = sector is overbought (be careful)<br>
            Click any ticker chip to jump to its detail view.
        `,
        attachTo: { element: '.tabs', on: 'bottom' },
    },
    {
        id: 'ai-chat',
        title: 'Gemini AI Assistant',
        text: `
            Click the <b>AI</b> button (bottom-right) to chat.<br>
            Gemini knows the full wheel playbook and can:<br>
            • Analyze the selected ticker<br>
            • Compare tickers ("is there a better put to sell?")<br>
            • Find opportunities by criteria ("best put under $10K")<br>
            • Explain strategy rules<br><br>
            <b>Ticker names in responses are clickable</b> — click to jump to that ticker.
        `,
        attachTo: { element: '#chat-toggle', on: 'left' },
    },
    {
        id: 'playbook',
        title: 'The Wheel Playbook',
        text: `
            Click <b>Playbook</b> for the complete decision rules:<br>
            <b>Phase 1</b>: When to sell put, buy stock, or stand aside<br>
            <b>Phase 2</b>: How to manage open puts (roll, close, assignment)<br>
            <b>Phase 3</b>: Covered call selection after assignment<br>
            <b>Phase 4</b>: Call management until cycle completes<br><br>
            The key rule: <b>30-45 DTE, 0.20-0.30 delta, close at 50% profit, never roll for a debit.</b>
        `,
        attachTo: { element: '.tabs', on: 'bottom' },
    },
    {
        id: 'done',
        title: 'You\'re Ready!',
        text: `
            <p>Start by clicking a ticker in the table. The terminal will show you everything you need to make a decision.</p>
            <p>You can restart this tour anytime by clicking <b>Guide</b>.</p>
            <p style="color:var(--green);font-weight:700">Happy wheeling!</p>
        `,
    },
];

/**
 * Start the interactive tour.
 * Call this from the Guide button: onclick="startTour()"
 */
function startTour() {
    // Make sure we're on the main view
    const main = document.querySelector('.terminal-layout');
    if (main) main.style.display = 'flex';
    document.getElementById('playbook-view').style.display = 'none';
    document.getElementById('basket-view').style.display = 'none';
    document.getElementById('heatmap-view').style.display = 'none';

    const tour = new Shepherd.Tour({
        useModalOverlay: true,
        defaultStepOptions: {
            scrollTo: true,
            cancelIcon: { enabled: true },
            classes: 'shepherd-theme-custom',
        },
    });

    TOUR_STEPS.forEach((step, i) => {
        const buttons = [];
        if (i > 0) buttons.push({ text: 'Back', action: tour.back, classes: 'shepherd-btn-back' });
        if (i < TOUR_STEPS.length - 1) {
            buttons.push({ text: 'Next', action: tour.next, classes: 'shepherd-btn-next' });
        } else {
            buttons.push({ text: 'Done', action: tour.complete, classes: 'shepherd-btn-next' });
        }
        buttons.push({ text: 'Skip', action: tour.complete, classes: 'shepherd-btn-skip' });

        tour.addStep({
            id: step.id,
            title: step.title,
            text: step.text,
            attachTo: step.attachTo,
            beforeShowPromise: step.beforeShowPromise,
            buttons,
        });
    });

    tour.start();
}
