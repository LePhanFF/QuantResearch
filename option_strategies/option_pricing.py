"""
Option Pricing Utilities
========================

Black-Scholes pricing for estimating option premiums during backtesting.
Uses historical volatility when implied volatility is not available.
"""

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm


@dataclass
class OptionQuote:
    """Estimated option price and Greeks."""
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float


def black_scholes_put(
    S: float, K: float, T: float, r: float, sigma: float
) -> OptionQuote:
    """Price a European put option using Black-Scholes.

    Args:
        S: Current stock price.
        K: Strike price.
        T: Time to expiration in years.
        r: Risk-free rate (annualized).
        sigma: Volatility (annualized).

    Returns:
        OptionQuote with price and Greeks.
    """
    if T <= 0 or sigma <= 0:
        intrinsic = max(K - S, 0)
        delta = -1.0 if S < K else 0.0
        return OptionQuote(price=intrinsic, delta=delta, gamma=0, theta=0, vega=0, iv=sigma)

    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    put_price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    delta = norm.cdf(d1) - 1  # put delta is negative
    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
    theta = (-(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
             + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365
    vega = S * norm.pdf(d1) * math.sqrt(T) / 100

    return OptionQuote(price=put_price, delta=delta, gamma=gamma,
                       theta=theta, vega=vega, iv=sigma)


def black_scholes_call(
    S: float, K: float, T: float, r: float, sigma: float
) -> OptionQuote:
    """Price a European call option using Black-Scholes.

    Args:
        S: Current stock price.
        K: Strike price.
        T: Time to expiration in years.
        r: Risk-free rate (annualized).
        sigma: Volatility (annualized).

    Returns:
        OptionQuote with price and Greeks.
    """
    if T <= 0 or sigma <= 0:
        intrinsic = max(S - K, 0)
        delta = 1.0 if S > K else 0.0
        return OptionQuote(price=intrinsic, delta=delta, gamma=0, theta=0, vega=0, iv=sigma)

    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    call_price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    delta = norm.cdf(d1)
    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
    theta = (-(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
             - r * K * math.exp(-r * T) * norm.cdf(d2)) / 365
    vega = S * norm.pdf(d1) * math.sqrt(T) / 100

    return OptionQuote(price=call_price, delta=delta, gamma=gamma,
                       theta=theta, vega=vega, iv=sigma)


def historical_volatility(prices: np.ndarray, window: int = 30) -> float:
    """Calculate annualized historical volatility from daily prices.

    Args:
        prices: Array of daily closing prices.
        window: Lookback window in trading days.

    Returns:
        Annualized volatility.
    """
    if len(prices) < window + 1:
        window = len(prices) - 1
    if window < 2:
        return 0.3  # default fallback

    returns = np.diff(np.log(prices[-window - 1:]))
    return float(np.std(returns) * math.sqrt(252))


def round_strike(price: float, increment: float = 1.0) -> float:
    """Round to nearest option strike increment."""
    return round(price / increment) * increment


def iv_multiplier(base_iv: float, iv_rank_pct: float = 50) -> float:
    """Adjust IV based on IV rank percentile.

    Higher IV rank means options are relatively expensive.
    """
    # Scale IV between 0.7x (low rank) and 1.5x (high rank)
    scale = 0.7 + (iv_rank_pct / 100) * 0.8
    return base_iv * scale
