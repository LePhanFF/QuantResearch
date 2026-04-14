"""
Wheel Strategy Decision Engine
==============================

Complete lifecycle management for the wheel strategy.  Every decision
point — entry, hold, roll, accept assignment, covered-call management,
and outright buy — is codified as a deterministic rule set that can be
evaluated in real time or replayed in backtests.

Decision tree overview
======================

Phase 1 — NO POSITION
    evaluate_entry()  →  SELL_PUT / BUY_STOCK / STAND_ASIDE

Phase 2 — SHORT PUT OPEN
    manage_put()  →  HOLD / CLOSE_WINNER / ROLL_SAME_STRIKE /
                     ROLL_DOWN_AND_OUT / ACCEPT_ASSIGNMENT

Phase 3 — HOLDING SHARES (assigned)
    manage_shares()  →  SELL_COVERED_CALL (with strike guidance)

Phase 4 — SHORT CALL OPEN
    manage_call()  →  HOLD / CLOSE_WINNER / ROLL_UP_AND_OUT /
                      ROLL_DOWN / LET_CALL_AWAY


                    ┌─────────────────────────────┐
                    │  NO POSITION                │
                    │  evaluate_entry()            │
                    └──────┬───────────┬──────────┘
                   SELL_PUT│           │BUY_STOCK
                           v           v
               ┌──────────────┐   (hold shares,
               │ SHORT PUT    │    skip to Phase 3)
               │ manage_put() │
               └──┬───┬───┬──┘
      expired OTM │   │   │ assigned
      (keep $)    │   │   v
          ┌───────┘   │  ┌──────────────────────┐
          │   ROLL    │  │ HOLDING SHARES        │
          │  (same or │  │ manage_shares()       │
          │   down)   │  │  → SELL_COVERED_CALL  │
          │           │  └──────────┬────────────┘
          │           │             v
          │           │  ┌──────────────────────┐
          │           │  │ SHORT CALL            │
          │           │  │ manage_call()         │
          │           │  └──┬───────┬───────────┘
          │           │     │       │ called away
          │           │     │ROLL   v
          └───────────┘     │   back to NO POSITION
                            │     (cycle complete)
                            └──→ re-sell CC

"""

from __future__ import annotations

import io
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# Fix Windows console encoding (only when run as main script)
if sys.platform == "win32" and __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# =============================================================================
# Enums & data classes
# =============================================================================


class Action(str, Enum):
    # Phase 1 — entry
    SELL_PUT = "SELL_PUT"
    BUY_STOCK = "BUY_STOCK"
    STAND_ASIDE = "STAND_ASIDE"

    # Phase 2 — put management
    HOLD_PUT = "HOLD_PUT"
    CLOSE_PUT_WINNER = "CLOSE_PUT_WINNER"
    ROLL_SAME_STRIKE = "ROLL_SAME_STRIKE"
    ROLL_DOWN_AND_OUT = "ROLL_DOWN_AND_OUT"
    ACCEPT_ASSIGNMENT = "ACCEPT_ASSIGNMENT"

    # Phase 3 — post-assignment
    SELL_COVERED_CALL = "SELL_COVERED_CALL"

    # Phase 4 — call management
    HOLD_CALL = "HOLD_CALL"
    CLOSE_CALL_WINNER = "CLOSE_CALL_WINNER"
    ROLL_CALL_UP_AND_OUT = "ROLL_CALL_UP_AND_OUT"
    ROLL_CALL_DOWN = "ROLL_CALL_DOWN"
    LET_CALL_AWAY = "LET_CALL_AWAY"


@dataclass
class Decision:
    """What to do and why."""
    action: Action
    reason: str
    # Guidance for the next trade (not always populated)
    target_delta: Optional[float] = None
    target_dte: Optional[int] = None         # calendar days
    target_strike: Optional[float] = None    # explicit strike override
    roll_credit_min: Optional[float] = None  # minimum net credit on a roll


@dataclass
class PutPosition:
    """Snapshot of a live short put."""
    ticker: str
    strike: float
    premium_collected: float     # per-share premium received at open
    current_underlying: float    # latest spot price
    days_remaining: int          # calendar days to expiry
    iv_rank: float               # current IV rank (0-100)
    put_mark: float              # current mid-price of the put
    above_200_sma: bool
    earnings_before_expiry: bool


@dataclass
class SharePosition:
    """Snapshot after put assignment."""
    ticker: str
    shares: int
    cost_basis: float            # strike - cumulative premium per share
    current_price: float
    iv_rank: float
    above_200_sma: bool
    earnings_before_next_expiry: bool
    dividend_ex_date_before_expiry: bool


@dataclass
class CallPosition:
    """Snapshot of a live short covered call."""
    ticker: str
    strike: float
    premium_collected: float     # per-share
    cost_basis: float            # from assignment
    current_underlying: float
    days_remaining: int
    iv_rank: float
    call_mark: float             # current mid-price of the call
    above_200_sma: bool
    earnings_before_expiry: bool


# =============================================================================
# Phase 1 — ENTRY (no position)
# =============================================================================

# Thresholds
IVR_SELL_PUT = 30       # minimum IV rank to justify selling premium
IVR_RICH = 50           # premium is genuinely rich → widen delta
IVR_CRISIS = 80         # panic level — do NOT sell premium into the hole
IVR_BUY_STOCK = 20      # below this, CSP premium isn't worth the effort
QUALITY_MIN = 7         # minimum quality score (1-10) to trade
SMA_MAX_BELOW = 10      # max % below 200 SMA before standing aside

# Valuation thresholds
PE_OVERVALUED = 40      # trailing P/E above this = overbought flag
PE_CHEAP = 15           # trailing P/E below this = value territory

# Momentum / overbought-oversold
RSI_OVERBOUGHT = 70     # RSI above this = don't chase
RSI_OVERSOLD = 30       # RSI below this = accumulation zone

# Pullback & risk
PULLBACK_SWEET_SPOT = 10  # 10-25% off 52w high = best entry zone
PULLBACK_DEEP = 25        # > 25% off = potential value trap, be careful


def evaluate_entry(
    *,
    quality_score: int,
    iv_rank: float,
    above_200_sma: bool,
    pct_from_200_sma: float,    # positive = above, negative = below
    earnings_within_dte: bool,
    in_strong_uptrend: bool = False,
    ex_div_before_expiry: bool = False,
    # New valuation & momentum inputs (all optional for backward compat)
    rsi_14: Optional[float] = None,
    trailing_pe: Optional[float] = None,
    forward_pe: Optional[float] = None,
    pct_off_52w_high: Optional[float] = None,  # negative number, e.g. -15.0
    premium_ann_roc: Optional[float] = None,    # CSP annualized return on capital
    max_dd_6w: Optional[float] = None,          # 6-week max drawdown (negative)
) -> Decision:
    """
    Decide whether to open a new position.

    Returns SELL_PUT, BUY_STOCK, or STAND_ASIDE with reasoning and
    suggested parameters.

    When to sell put (IVR >= 30)
    ----------------------------
    Premium is at least "average" for the name.  The higher the IVR,
    the wider we can go OTM and still collect meaningful income.

      IVR 30-50  →  sell ~0.25 delta (standard)
      IVR 50-80  →  sell ~0.20 delta (can afford to go wider)
      IVR > 80   →  only if ABOVE 200 SMA (fear spike in an uptrend)

    When to buy outright (IVR < 20)
    --------------------------------
    Premium is so thin that the 30-45 day lock-up isn't worth it.
    You'd rather own the shares and collect dividends.  Also preferred
    when a strong breakout is in progress — selling a put means you
    might never get filled while the stock runs.

    When to stand aside
    --------------------
    - Earnings inside the DTE window (binary event risk)
    - Price > 10% below 200 SMA with high IV (broken chart)
    - Quality below threshold
    """
    # --- Build context tags for multi-factor reasoning ---
    warnings: list[str] = []

    # --- Hard exclusions ---
    if quality_score < QUALITY_MIN:
        return Decision(Action.STAND_ASIDE,
                        f"Quality {quality_score}/10 below {QUALITY_MIN} minimum.")

    if earnings_within_dte:
        return Decision(Action.STAND_ASIDE,
                        "Earnings fall inside the option expiry window.")

    if pct_from_200_sma < -SMA_MAX_BELOW:
        return Decision(Action.STAND_ASIDE,
                        f"Price {pct_from_200_sma:+.1f}% vs 200 SMA — "
                        "falling knife, wait for stabilisation.")

    if not above_200_sma and iv_rank > IVR_CRISIS:
        return Decision(Action.STAND_ASIDE,
                        "Below 200 SMA with crisis-level IV — "
                        "do not sell premium into a breakdown.")

    # --- RSI overbought: don't chase the top ---
    if rsi_14 is not None and rsi_14 > RSI_OVERBOUGHT:
        if trailing_pe is not None and trailing_pe > PE_OVERVALUED:
            return Decision(Action.STAND_ASIDE,
                            f"RSI {rsi_14:.0f} overbought + P/E {trailing_pe:.0f} "
                            f"stretched. Don't chase — wait for pullback.")
        warnings.append(f"RSI {rsi_14:.0f} overbought")

    # --- Overvalued on P/E alone ---
    if trailing_pe is not None and trailing_pe > PE_OVERVALUED:
        warnings.append(f"P/E {trailing_pe:.0f} > {PE_OVERVALUED}")

    # --- Risk/reward check: premium vs recent drawdown ---
    if premium_ann_roc is not None and max_dd_6w is not None:
        if premium_ann_roc < abs(max_dd_6w) * 0.5:
            warnings.append(
                f"Poor risk/reward: {premium_ann_roc:.0f}% ann ROC vs "
                f"{max_dd_6w:.0f}% 6w drawdown"
            )

    # --- Pullback / accumulation zone detection ---
    pullback_pct = abs(pct_off_52w_high) if pct_off_52w_high is not None else 0
    in_pullback_zone = PULLBACK_SWEET_SPOT <= pullback_pct <= PULLBACK_DEEP
    deep_pullback = pullback_pct > PULLBACK_DEEP

    # --- RSI oversold + value = prime accumulation ---
    if rsi_14 is not None and rsi_14 < RSI_OVERSOLD and above_200_sma:
        if trailing_pe is not None and trailing_pe < PE_CHEAP:
            return Decision(
                Action.BUY_STOCK,
                f"RSI {rsi_14:.0f} oversold + P/E {trailing_pe:.0f} cheap + "
                "above 200 SMA. Prime accumulation — buy outright.",
            )
        if iv_rank >= IVR_SELL_PUT:
            return Decision(
                Action.SELL_PUT,
                f"RSI {rsi_14:.0f} oversold + IVR {iv_rank:.0f} rich. "
                "Sell aggressive put to accumulate at discount.",
                target_delta=0.30, target_dte=35,
            )

    # --- Pullback sweet spot (10-25% off highs) ---
    if in_pullback_zone and above_200_sma:
        if iv_rank >= IVR_SELL_PUT:
            note = (f"{pullback_pct:.0f}% off 52w high — pullback zone. "
                    f"IVR {iv_rank:.0f} rich. Sell put to accumulate at discount.")
            return Decision(Action.SELL_PUT, note,
                            target_delta=0.25, target_dte=35)
        else:
            return Decision(Action.BUY_STOCK,
                            f"{pullback_pct:.0f}% off 52w high — pullback zone. "
                            "IV too low for CSP, buy the dip outright.")

    # --- Deep pullback: be careful ---
    if deep_pullback and not above_200_sma:
        return Decision(Action.STAND_ASIDE,
                        f"{pullback_pct:.0f}% off 52w high + below 200 SMA. "
                        "Potential value trap. Wait for stabilisation.")

    # --- Outright buy triggers ---
    if in_strong_uptrend and iv_rank < 25:
        return Decision(Action.BUY_STOCK,
                        "Strong breakout + low IV — own shares outright, "
                        "don't risk being left behind with an unexercised CSP.")

    if ex_div_before_expiry and iv_rank < IVR_SELL_PUT:
        return Decision(Action.BUY_STOCK,
                        "Ex-dividend before expiry and IV too low for CSP — "
                        "buy shares to capture the dividend.")

    if iv_rank < IVR_BUY_STOCK:
        return Decision(Action.BUY_STOCK,
                        f"IV rank {iv_rank:.0f} < {IVR_BUY_STOCK} — premium too "
                        "thin to bother. Accumulate shares on dips instead.")

    # --- Sell put (core logic) ---
    if iv_rank >= IVR_SELL_PUT:
        if iv_rank >= IVR_RICH:
            delta = 0.20
            note = f"IVR {iv_rank:.0f} is rich — go wider OTM (0.20 delta)."
        else:
            delta = 0.25
            note = f"IVR {iv_rank:.0f} >= {IVR_SELL_PUT} — standard 0.25 delta."

        # Append any warning flags
        if warnings:
            note += " WARNINGS: " + "; ".join(warnings) + "."

        return Decision(
            Action.SELL_PUT, note,
            target_delta=delta, target_dte=35,
        )

    # Fallback — IV between 20 and 30
    reason = (f"IV rank {iv_rank:.0f} in dead zone (20-30). "
              "Prefer buying shares or waiting for IV expansion.")
    if warnings:
        reason += " WARNINGS: " + "; ".join(warnings) + "."
    return Decision(Action.BUY_STOCK, reason)


# =============================================================================
# Phase 2 — MANAGE OPEN SHORT PUT
# =============================================================================

# Thresholds
PROFIT_CLOSE_PCT = 50           # close when 50% of premium captured
DAYS_MANAGE_THRESHOLD = 21      # start active management at 21 DTE
ITM_SHALLOW_PCT = 3.0           # < 3% ITM → roll same strike
ITM_MODERATE_PCT = 8.0          # 3-8% ITM → roll down and out
ROLL_MIN_CREDIT = 0.10          # never roll for a debit


def manage_put(pos: PutPosition) -> Decision:
    """
    Given a live short put, decide what to do RIGHT NOW.

    Decision flow
    -------------
    1. **Profit target hit (50%)?**
       → Close the put, re-sell a fresh 30-45 DTE.  Do not get greedy
         chasing the last 50% of premium; that is where gamma risk
         accelerates and theta decays slower (per day).

    2. **Earnings popped up inside the window?**
       → Close immediately regardless of P&L.  Binary event risk.

    3. **Still OTM with > 21 DTE?**
       → Hold.  Theta is working, nothing to do.

    4. **OTM with <= 21 DTE?**
       → Close and re-open at 30-45 DTE (mechanical roll forward).
         You've harvested the steepest part of the theta curve.

    5. **Put is ITM (spot < strike):**

       a. *Shallow ITM (< 3%)*  → **ROLL SAME STRIKE + 30 days**.
          The put is barely ITM, time-value is still significant.
          Rolling adds DTE and collects a net credit (time premium of
          the new put minus intrinsic + residual TV of old put).

       b. *Moderate ITM (3-8%)* → **ROLL DOWN AND OUT**.
          Lower the strike 1-2 strikes *and* add 30-45 DTE.  This
          must be done for a net credit or at worst scratch.  If you
          can't get a credit, move to (c).

       c. *Deep ITM (> 8%)*    → **ACCEPT ASSIGNMENT**.
          The put is so far ITM that rolling just chases the stock
          lower and ties up capital longer.  Take the shares, adjust
          your cost basis (strike - cumulative premium), and pivot
          to selling covered calls.

    Why 50% profit and not 80%?
    ---------------------------
    Closing at 50% and re-deploying into a new 30-45 DTE cycle has
    been shown (TastyTrade research) to produce higher cumulative
    returns than holding to expiry, because:
      - You re-set theta to its steepest part of the curve.
      - You reduce gamma risk as expiry approaches.
      - Win rate increases (smaller target = more winners).

    Why never roll for a debit?
    ---------------------------
    Rolling for a debit means you're *paying* to extend a losing trade.
    That capital is better used opening a new position at a better strike.
    """
    profit_pct = _profit_pct(pos)

    # 1. Profit target
    if profit_pct >= PROFIT_CLOSE_PCT:
        return Decision(
            Action.CLOSE_PUT_WINNER,
            f"Captured {profit_pct:.0f}% of max premium. "
            "Close and re-sell fresh 30-45 DTE.",
            target_delta=0.25, target_dte=35,
        )

    # 2. Earnings surprise
    if pos.earnings_before_expiry:
        return Decision(
            Action.CLOSE_PUT_WINNER if profit_pct > 0 else Action.ROLL_SAME_STRIKE,
            "Earnings appeared inside the window — close or roll out past earnings.",
            target_dte=45,
        )

    itm_pct = _itm_pct_put(pos)
    is_itm = pos.current_underlying < pos.strike

    # 3. OTM with plenty of time
    if not is_itm and pos.days_remaining > DAYS_MANAGE_THRESHOLD:
        return Decision(Action.HOLD_PUT,
                        f"OTM with {pos.days_remaining} DTE — theta is working.")

    # 4. OTM but time is running out → mechanical roll forward
    if not is_itm and pos.days_remaining <= DAYS_MANAGE_THRESHOLD:
        if profit_pct >= 30:
            return Decision(
                Action.CLOSE_PUT_WINNER,
                f"{profit_pct:.0f}% profit with {pos.days_remaining} DTE remaining. "
                "Close and re-deploy fresh capital.",
                target_delta=0.25, target_dte=35,
            )
        return Decision(
            Action.ROLL_SAME_STRIKE,
            f"OTM but only {pos.days_remaining} DTE left. "
            "Roll same strike +30 days to stay in the theta sweet spot.",
            target_strike=pos.strike, target_dte=30,
            roll_credit_min=ROLL_MIN_CREDIT,
        )

    # 5. ITM scenarios
    if is_itm:
        if itm_pct < ITM_SHALLOW_PCT:
            return Decision(
                Action.ROLL_SAME_STRIKE,
                f"Shallow ITM ({itm_pct:.1f}%). Roll same strike +30 days "
                "for a net credit — time value still meaningful.",
                target_strike=pos.strike, target_dte=30,
                roll_credit_min=ROLL_MIN_CREDIT,
            )
        elif itm_pct < ITM_MODERATE_PCT:
            return Decision(
                Action.ROLL_DOWN_AND_OUT,
                f"Moderate ITM ({itm_pct:.1f}%). Roll down 1-2 strikes and "
                "out +30-45 days. MUST get a net credit.",
                target_dte=45,
                roll_credit_min=ROLL_MIN_CREDIT,
            )
        else:
            return Decision(
                Action.ACCEPT_ASSIGNMENT,
                f"Deep ITM ({itm_pct:.1f}%). Rolling is too expensive / "
                "chasing the stock lower. Accept shares, adjust cost basis "
                f"to ~${pos.strike - pos.premium_collected:.2f}, and sell "
                "covered calls.",
            )

    # Default hold
    return Decision(Action.HOLD_PUT,
                    f"{pos.days_remaining} DTE, {profit_pct:.0f}% profit — hold.")


# =============================================================================
# Phase 3 — POST-ASSIGNMENT (holding shares, need to sell a call)
# =============================================================================


def manage_shares(pos: SharePosition) -> Decision:
    """
    Determine the right covered call to sell after assignment.

    Key principle: NEVER sell a call below your adjusted cost basis
    unless you are intentionally harvesting a tax loss.

    Strike selection
    ----------------
    The covered call strike depends on where the stock is relative
    to your cost basis:

      stock >> cost basis  →  Sell closer to money (0.30-0.40 delta).
                              You WANT to get called away at a profit.

      stock ~= cost basis  →  Sell ~0.25 delta.  Standard income play.

      stock << cost basis  →  Sell further OTM (0.15-0.20 delta).
                              Protect yourself from locking in a loss.
                              Patience — collect small premiums and wait
                              for the stock to recover.

    DTE:  30-45 days (same theta logic as CSPs).

    Dividends:  If ex-div is before your CC expiry, you will collect
                the dividend.  Factor this into your total-return calc.
    """
    pct_from_basis = (pos.current_price / pos.cost_basis - 1) * 100

    if pos.earnings_before_next_expiry:
        return Decision(
            Action.SELL_COVERED_CALL,
            "Earnings within window — sell a call AFTER earnings, "
            "or sell now with strike well above cost basis to limit risk.",
            target_delta=0.15, target_dte=45,
        )

    if pct_from_basis > 5:
        # Stock well above cost basis — get called away happily
        return Decision(
            Action.SELL_COVERED_CALL,
            f"Stock {pct_from_basis:+.1f}% above cost basis — sell "
            "aggressive call (0.30-0.40 delta) to get called away at profit.",
            target_delta=0.35, target_dte=30,
            target_strike=round(pos.cost_basis * 1.02, 2),
        )

    if pct_from_basis > -2:
        # Stock near cost basis — standard income
        return Decision(
            Action.SELL_COVERED_CALL,
            f"Stock near cost basis ({pct_from_basis:+.1f}%). "
            "Standard 0.25 delta, 30-45 DTE.",
            target_delta=0.25, target_dte=35,
        )

    if pct_from_basis > -10:
        # Stock moderately below cost basis — be patient
        return Decision(
            Action.SELL_COVERED_CALL,
            f"Stock {pct_from_basis:+.1f}% below cost basis — sell "
            "conservative call (0.15-0.20 delta) to avoid locking in loss. "
            "DO NOT sell below cost basis. Patience.",
            target_delta=0.15, target_dte=45,
        )

    # Stock way below cost basis — very conservative
    return Decision(
        Action.SELL_COVERED_CALL,
        f"Stock {pct_from_basis:+.1f}% below cost basis — deep underwater. "
        "Sell far OTM call (0.10-0.15 delta) for small income while waiting "
        "for recovery. Consider adding shares to average down if fundamentals "
        "are intact.",
        target_delta=0.12, target_dte=45,
    )


# =============================================================================
# Phase 4 — MANAGE OPEN SHORT CALL
# =============================================================================


def manage_call(pos: CallPosition) -> Decision:
    """
    Given a live short covered call, decide what to do RIGHT NOW.

    Decision flow
    -------------
    1. **50% profit?**  → Close and re-sell at fresh 30-45 DTE.

    2. **Earnings appeared?**  → Close immediately.

    3. **OTM with > 21 DTE?**  → Hold.

    4. **OTM with <= 21 DTE?**
       - If profit > 30%: close, re-sell.
       - Else: roll same strike +30d.

    5. **ITM (stock above strike)?**
       a. Near expiry (< 7 DTE) → **LET IT GET CALLED AWAY**.
          This is the GOAL — you sell at the strike + collected premium.
          Cycle complete, go back to selling puts.

       b. Far from expiry (> 7 DTE) and want to keep shares
          → **ROLL UP AND OUT**.  Higher strike + more DTE, for a credit.
          Only do this if the stock is in a strong uptrend and you believe
          it still has room.  Otherwise let it go.

    6. **Stock dropped hard while holding the call?**
       → Consider ROLLING DOWN the call strike (closer to money) to
         collect more premium and lower your cost basis faster.
         Never roll below your cost basis.

    When to let shares get called away
    -----------------------------------
    - The stock hits your strike near expiry.  Take the profit.
    - You've been wheeling the name for multiple cycles and want to
      re-deploy capital elsewhere.
    - The fundamental story has weakened and you no longer want to own it.
    """
    profit_pct = _profit_pct_call(pos)

    # 1. Profit target
    if profit_pct >= PROFIT_CLOSE_PCT:
        return Decision(
            Action.CLOSE_CALL_WINNER,
            f"Captured {profit_pct:.0f}% of CC premium. "
            "Close and re-sell fresh 30-45 DTE.",
            target_delta=0.25, target_dte=35,
        )

    # 2. Earnings surprise
    if pos.earnings_before_expiry:
        action = Action.CLOSE_CALL_WINNER if profit_pct > 0 else Action.HOLD_CALL
        return Decision(action,
                        "Earnings inside CC window — close if profitable, "
                        "else hold (assignment risk is limited on a CC).")

    is_itm = pos.current_underlying > pos.strike

    # 3. OTM with plenty of time
    if not is_itm and pos.days_remaining > DAYS_MANAGE_THRESHOLD:
        # Stock dropping? Maybe roll down for more premium
        pct_below_strike = (pos.strike / pos.current_underlying - 1) * 100
        if pct_below_strike > 8 and pos.days_remaining > 30:
            return Decision(
                Action.ROLL_CALL_DOWN,
                f"Stock {pct_below_strike:.0f}% below call strike — "
                "roll call down closer to money to collect more premium. "
                "Never below cost basis.",
                target_delta=0.25, target_dte=35,
                target_strike=max(pos.cost_basis, pos.current_underlying * 1.02),
            )
        return Decision(Action.HOLD_CALL,
                        f"OTM with {pos.days_remaining} DTE — theta working.")

    # 4. OTM near expiry
    if not is_itm and pos.days_remaining <= DAYS_MANAGE_THRESHOLD:
        if profit_pct >= 30:
            return Decision(
                Action.CLOSE_CALL_WINNER,
                f"{profit_pct:.0f}% profit, {pos.days_remaining} DTE. "
                "Close and re-sell.",
                target_delta=0.25, target_dte=35,
            )
        return Decision(
            Action.HOLD_CALL,
            f"OTM, {pos.days_remaining} DTE, {profit_pct:.0f}% profit — "
            "let theta finish the job or roll at 7 DTE.",
        )

    # 5. ITM — stock above call strike
    if is_itm:
        if pos.days_remaining <= 7:
            above_cost = pos.strike >= pos.cost_basis
            if above_cost:
                return Decision(
                    Action.LET_CALL_AWAY,
                    f"ITM with {pos.days_remaining} DTE — let shares get called "
                    f"away at ${pos.strike:.2f}. Profit = "
                    f"(strike - cost basis + premium). Cycle complete.",
                )
            else:
                return Decision(
                    Action.ROLL_CALL_UP_AND_OUT,
                    f"ITM but strike ${pos.strike:.2f} < cost basis "
                    f"${pos.cost_basis:.2f} — roll up and out to avoid "
                    "locking in a loss.",
                    target_dte=30,
                    roll_credit_min=ROLL_MIN_CREDIT,
                )
        else:
            return Decision(
                Action.ROLL_CALL_UP_AND_OUT,
                f"ITM with {pos.days_remaining} DTE still remaining. "
                "Roll up to higher strike +30 days for a credit if you "
                "want to keep shares. Otherwise just hold and let it expire.",
                target_dte=30,
                roll_credit_min=ROLL_MIN_CREDIT,
            )

    return Decision(Action.HOLD_CALL,
                    f"{pos.days_remaining} DTE, {profit_pct:.0f}% profit — hold.")


# =============================================================================
# Helpers
# =============================================================================


def _profit_pct(pos: PutPosition) -> float:
    """% of max put premium captured so far."""
    if pos.premium_collected <= 0:
        return 0.0
    # Profit = premium collected - current cost to buy back
    profit_per_share = pos.premium_collected - pos.put_mark
    return profit_per_share / pos.premium_collected * 100


def _profit_pct_call(pos: CallPosition) -> float:
    """% of max call premium captured so far."""
    if pos.premium_collected <= 0:
        return 0.0
    profit_per_share = pos.premium_collected - pos.call_mark
    return profit_per_share / pos.premium_collected * 100


def _itm_pct_put(pos: PutPosition) -> float:
    """How far ITM is the put, as % of strike. 0 if OTM."""
    if pos.current_underlying >= pos.strike:
        return 0.0
    return (pos.strike - pos.current_underlying) / pos.strike * 100


# =============================================================================
# Quick reference printout
# =============================================================================


def print_playbook() -> None:
    """Print the complete decision playbook to stdout."""
    playbook = """
================================================================================
  WHEEL STRATEGY DECISION PLAYBOOK
================================================================================

PHASE 1 — ENTRY (No Position)
──────────────────────────────────────────────────────────────────
  IVR >= 50     SELL PUT at 0.20 delta, 30-45 DTE (premium is rich)
  IVR 30-50     SELL PUT at 0.25 delta, 30-45 DTE (standard)
  IVR 20-30     BUY STOCK (premium dead zone — just own shares)
  IVR < 20      BUY STOCK (CSP not worth the capital lock-up)

  EXCEPTIONS:
    - Below 200 SMA by > 10%           → STAND ASIDE (falling knife)
    - Below 200 SMA + IVR > 80         → STAND ASIDE (crisis)
    - Earnings within DTE              → STAND ASIDE
    - Strong breakout + low IV         → BUY STOCK (don't miss the move)
    - Ex-div before expiry + low IV    → BUY STOCK (capture dividend)

PHASE 2 — MANAGE SHORT PUT
──────────────────────────────────────────────────────────────────
  50% profit reached            → CLOSE, re-sell new 30-45 DTE
  OTM, > 21 DTE                → HOLD (theta working)
  OTM, <= 21 DTE, > 30% profit → CLOSE, re-sell
  OTM, <= 21 DTE, < 30% profit → ROLL same strike +30 days (for credit)

  ITM < 3%     → ROLL SAME STRIKE +30 days (for a credit)
  ITM 3-8%     → ROLL DOWN 1-2 strikes + 30-45 days (MUST be for credit)
  ITM > 8%     → ACCEPT ASSIGNMENT (rolling is too expensive)

  GOLDEN RULE: Never roll for a debit. If you can't get a credit, take
               the assignment and move to covered calls.

PHASE 3 — POST-ASSIGNMENT (Sell Covered Call)
──────────────────────────────────────────────────────────────────
  Stock > 5% above cost basis  → Sell 0.30-0.40 delta CC (get called away)
  Stock near cost basis (±2%)  → Sell 0.25 delta CC (standard income)
  Stock 2-10% below basis      → Sell 0.15-0.20 delta CC (patient recovery)
  Stock > 10% below basis      → Sell 0.10-0.15 delta CC (minimal income,
                                  wait for recovery; consider averaging down)

  STRIKE RULE: Never sell a call below your adjusted cost basis.
               Adjusted cost basis = assignment strike - total premium collected.

PHASE 4 — MANAGE SHORT CALL
──────────────────────────────────────────────────────────────────
  50% profit reached             → CLOSE, re-sell new 30-45 DTE
  OTM, > 21 DTE                 → HOLD
  OTM, stock fell > 8% below    → ROLL CALL DOWN closer to money
     call strike                   (more premium; never below cost basis)
  OTM, <= 21 DTE, > 30% profit  → CLOSE, re-sell
  OTM, <= 21 DTE, < 30% profit  → HOLD, let theta finish

  ITM, <= 7 DTE, above basis    → LET IT GET CALLED AWAY (cycle complete!)
  ITM, <= 7 DTE, below basis    → ROLL UP AND OUT (avoid selling at a loss)
  ITM, > 7 DTE                  → ROLL UP AND OUT for credit, or hold

  CALLED AWAY = CYCLE COMPLETE → back to Phase 1, sell another CSP.

WHEN TO BUY STOCK OUTRIGHT (Summary)
──────────────────────────────────────────────────────────────────
  1. IV Rank < 20          Premium too thin for CSP to be worthwhile
  2. Strong breakout       Don't risk missing the move with a CSP
  3. Dividend capture      Ex-div before CSP expiry, low IV
  4. Core holding          Stock you NEVER want called away
  5. Major support bounce  Price at 200 SMA in uptrend, low IV

CONCENTRATION LIMITS
──────────────────────────────────────────────────────────────────
  Max 20% of account in any single underlying
  Max 35% in any single sector
  Keep 25% cash buffer for assignments and margin
================================================================================
"""
    print(playbook)


# =============================================================================
# Example / demo
# =============================================================================

if __name__ == "__main__":
    print_playbook()

    print("\n--- Example: Entry evaluation ---")
    d = evaluate_entry(
        quality_score=9,
        iv_rank=55,
        above_200_sma=True,
        pct_from_200_sma=3.5,
        earnings_within_dte=False,
    )
    print(f"  Action:  {d.action.value}")
    print(f"  Reason:  {d.reason}")
    print(f"  Delta:   {d.target_delta}")
    print(f"  DTE:     {d.target_dte}")

    print("\n--- Example: Manage a losing put (5% ITM) ---")
    d = manage_put(PutPosition(
        ticker="AAPL",
        strike=260.00,
        premium_collected=4.50,
        current_underlying=248.00,
        days_remaining=12,
        iv_rank=45,
        put_mark=12.80,
        above_200_sma=True,
        earnings_before_expiry=False,
    ))
    print(f"  Action:  {d.action.value}")
    print(f"  Reason:  {d.reason}")

    print("\n--- Example: Post-assignment, stock below cost basis ---")
    d = manage_shares(SharePosition(
        ticker="AAPL",
        shares=100,
        cost_basis=255.50,  # 260 strike - 4.50 premium
        current_price=248.00,
        iv_rank=45,
        above_200_sma=True,
        earnings_before_next_expiry=False,
        dividend_ex_date_before_expiry=False,
    ))
    print(f"  Action:  {d.action.value}")
    print(f"  Reason:  {d.reason}")
    print(f"  Delta:   {d.target_delta}")

    print("\n--- Example: CC ITM near expiry, above cost basis ---")
    d = manage_call(CallPosition(
        ticker="AAPL",
        strike=260.00,
        premium_collected=3.00,
        cost_basis=255.50,
        current_underlying=263.00,
        days_remaining=5,
        iv_rank=30,
        call_mark=4.50,
        above_200_sma=True,
        earnings_before_expiry=False,
    ))
    print(f"  Action:  {d.action.value}")
    print(f"  Reason:  {d.reason}")
