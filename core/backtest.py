"""
=============================================================================
 BACKTEST  —  runs a weight vector through history and scores the result
=============================================================================

WHAT THIS FILE DOES
    Everything behind the Backtesting page. Pure pandas/numpy, so
    scripts/smoke_test.py checks the numbers without launching the app.

    THE FOUR THINGS YOU WILL CALL
      align_weights()   drop assets with no price history, renormalise the rest
      run()             grow a portfolio through the price history -> index
      metrics_frame()   the results table: CAGR, drawdown, VaR, Sharpe, ...
      drawdown_series() / rolling_return() / rolling_volatility()  for charts

REBALANCING  (set in settings.toml [backtest].rebalance)
    "M" - the portfolio is reset to its target weights at the START OF EVERY
    MONTH. Within the month, weights drift with the market. This is what
    run() implements; see the loop in _rebalanced_daily_returns().

    To change to quarterly, set [backtest].rebalance = "Q". The code groups by
    that pandas period alias, so "W", "M", "Q" and "Y" all work. Blank means
    buy and hold: weights are set once at the start and never reset.

UNITS
    Prices in, percentages out. Every metric ending in "%" is already
    multiplied by 100, so 6.2 means 6.2%. Sharpe/Sortino/Calmar are ratios.

WHERE TO CHANGE WHAT
    * Rebalancing frequency   -> settings.toml [backtest].rebalance
    * VaR confidence level    -> settings.toml [backtest].var_confidence
    * Risk-free rate          -> settings.toml [backtest].risk_free
    * Add a metric            -> add it to METRIC_ROWS and to summary_metrics()
    * Trading days per year   -> TRADING_DAYS below

NO STREAMLIT IN THIS FILE.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252
MONTHS_PER_YEAR = 12
BASE_LEVEL = 100.0

# Rows of the results table, in display order. All numeric so the table can be
# formatted in one go; the max-drawdown DATE is returned separately by
# drawdown_detail() and shown under the drawdown chart.
METRIC_ROWS = [
    "Total return %",
    "CAGR %",
    "Ann. volatility %",
    "Sharpe",
    "Sortino",
    "Max drawdown %",
    "Calmar",
    "Monthly VaR 95 %",
    "Monthly CVaR 95 %",
    "Best month %",
    "Worst month %",
    "% positive months",
    "Tracking error %",
]


# --------------------------------------------------------------------------- #
# 1. getting the weights ready                                               #
# --------------------------------------------------------------------------- #
def align_weights(weights: pd.Series,
                  prices: pd.DataFrame) -> tuple[pd.Series, list[str]]:
    """
    Keep only the assets that actually have prices, and renormalise so the
    remainder sums to 1.

    Returns (usable weights summing to 1, codes dropped for lack of prices).
    A code carrying a zero weight is not reported as dropped - it would not
    have affected the result anyway.
    """
    held = weights[weights.abs() > 1e-9]
    usable = [code for code in held.index if code in prices.columns]
    dropped = [code for code in held.index if code not in prices.columns]

    aligned = held.reindex(usable).astype(float)
    total = aligned.sum()
    if total <= 0:
        return pd.Series(dtype=float), dropped
    return aligned / total, dropped


def slice_period(prices: pd.DataFrame, start=None, end=None) -> pd.DataFrame:
    """Cut the price history down to the window the user asked for."""
    out = prices
    if start is not None:
        out = out[out.index >= pd.Timestamp(start)]
    if end is not None:
        out = out[out.index <= pd.Timestamp(end)]
    return out


# --------------------------------------------------------------------------- #
# 2. running the portfolio through history                                   #
# --------------------------------------------------------------------------- #
def _rebalanced_daily_returns(returns: pd.DataFrame, weights: pd.Series,
                              rebalance: str | None) -> pd.Series:
    """
    Daily portfolio returns, resetting to `weights` at the start of each
    rebalance period. `weights` must already sum to 1.

    Inside one period the maths is:
        growth_i = running product of (1 + daily return of asset i)
        value    = sum over i of  weight_i * growth_i      (starts at 1.0)
        return_t = value_t / value_(t-1) - 1
    which is exactly "buy the target weights, then let them drift".

    PERFORMANCE NOTE
    This used to loop over each month in Python. That is the obvious way to
    write it, but with ~230 months and ~15 portfolios in a report it cost
    about 19 seconds. The version below does the same arithmetic with a single
    grouped cumprod, which is ~30x faster. scripts/smoke_test.py asserts the
    two give identical answers - if you change this, keep that check passing.
    """
    growth_factors = 1.0 + returns

    if not rebalance:                                   # buy and hold
        growth = growth_factors.cumprod()
        value = growth.mul(weights, axis=1).sum(axis=1)
        previous = value.shift(1).fillna(1.0)
        return value / previous - 1.0

    periods = returns.index.to_period(rebalance)

    # cumulative growth of each asset SINCE the start of its rebalance period
    growth = growth_factors.groupby(periods).cumprod()
    value = growth.mul(weights, axis=1).sum(axis=1)

    # the previous day's value, except on the first day of a period where the
    # portfolio has just been reset to the target weights, so the base is 1.0
    previous = value.shift(1)
    period_starts = np.asarray(periods) != np.roll(np.asarray(periods), 1)
    period_starts[0] = True
    previous[period_starts] = 1.0

    return value / previous - 1.0


def run(prices: pd.DataFrame, weights: pd.Series,
        rebalance: str | None = "M") -> pd.Series:
    """
    Grow a portfolio through the given prices and return its index level,
    starting at 100.

    `weights` should come from align_weights() so it sums to 1 and only names
    assets that exist in `prices`.
    """
    if prices.empty or weights.empty:
        return pd.Series(dtype=float)

    columns = [c for c in weights.index if c in prices.columns]
    prices = prices[columns]
    weights = weights.reindex(columns)

    returns = prices.pct_change().fillna(0.0)
    daily = _rebalanced_daily_returns(returns, weights, rebalance)
    return BASE_LEVEL * (1.0 + daily).cumprod()


# --------------------------------------------------------------------------- #
# 3. chart series                                                            #
# --------------------------------------------------------------------------- #
def drawdown_series(index: pd.Series) -> pd.Series:
    """How far below its own running peak the portfolio is, in percent (<= 0)."""
    if index.empty:
        return index
    return (index / index.cummax() - 1.0) * 100.0


def drawdown_detail(index: pd.Series) -> dict:
    """Worst drawdown, when it bottomed, and the peak it fell from."""
    if index.empty:
        return {"depth": np.nan, "trough": None, "peak": None}
    drawdown = index / index.cummax() - 1.0
    trough = drawdown.idxmin()
    peak = index.loc[:trough].idxmax() if trough is not None else None
    return {"depth": float(drawdown.min() * 100.0), "trough": trough, "peak": peak}


def rolling_return(index: pd.Series, window_days: int = TRADING_DAYS) -> pd.Series:
    """Rolling total return over `window_days`, in percent."""
    if len(index) <= window_days:
        return pd.Series(dtype=float)
    return index.pct_change(window_days).dropna() * 100.0


def rolling_volatility(index: pd.Series,
                       window_days: int = TRADING_DAYS) -> pd.Series:
    """Rolling annualised volatility over `window_days`, in percent."""
    daily = index.pct_change()
    if len(daily.dropna()) <= window_days:
        return pd.Series(dtype=float)
    return (daily.rolling(window_days).std() * np.sqrt(TRADING_DAYS) * 100.0).dropna()


def monthly_returns(index: pd.Series) -> pd.Series:
    """Month-end to month-end returns, as fractions."""
    if index.empty:
        return pd.Series(dtype=float)
    return index.resample("ME").last().pct_change().dropna()


# --------------------------------------------------------------------------- #
# 4. the metrics                                                             #
# --------------------------------------------------------------------------- #
def summary_metrics(index: pd.Series, benchmark: pd.Series | None = None,
                    risk_free: float = 0.0,
                    var_confidence: float = 0.95) -> dict[str, float]:
    """
    Score one portfolio. `risk_free` is an annual rate in percent (e.g. 3.3).
    Returns a dict keyed by METRIC_ROWS.
    """
    blank = {row: np.nan for row in METRIC_ROWS}
    if index.empty or len(index) < 3:
        return blank

    daily = index.pct_change().dropna()
    years = (index.index[-1] - index.index[0]).days / 365.25
    if years <= 0 or daily.empty:
        return blank

    growth = index.iloc[-1] / index.iloc[0]
    total_return = (growth - 1.0) * 100.0
    cagr = (growth ** (1.0 / years) - 1.0) * 100.0
    volatility = daily.std() * np.sqrt(TRADING_DAYS) * 100.0

    excess = cagr - risk_free
    sharpe = excess / volatility if volatility > 0 else np.nan

    downside = daily[daily < 0]
    downside_vol = (downside.std() * np.sqrt(TRADING_DAYS) * 100.0
                    if len(downside) > 1 else np.nan)
    sortino = (excess / downside_vol
               if downside_vol and downside_vol > 0 else np.nan)

    max_drawdown = drawdown_detail(index)["depth"]
    calmar = (cagr / abs(max_drawdown)
              if max_drawdown and abs(max_drawdown) > 1e-9 else np.nan)

    monthly = monthly_returns(index)
    if len(monthly) >= 2:
        var_level = monthly.quantile(1.0 - var_confidence)
        tail = monthly[monthly <= var_level]
        monthly_var = var_level * 100.0
        monthly_cvar = tail.mean() * 100.0 if len(tail) else np.nan
        best_month = monthly.max() * 100.0
        worst_month = monthly.min() * 100.0
        positive_months = (monthly > 0).mean() * 100.0
    else:
        monthly_var = monthly_cvar = best_month = worst_month = np.nan
        positive_months = np.nan

    tracking_error = np.nan
    if benchmark is not None and not benchmark.empty:
        benchmark_monthly = monthly_returns(benchmark)
        pair = pd.concat([monthly, benchmark_monthly], axis=1).dropna()
        if len(pair) >= 2:
            active = pair.iloc[:, 0] - pair.iloc[:, 1]
            tracking_error = active.std() * np.sqrt(MONTHS_PER_YEAR) * 100.0

    return {
        "Total return %": total_return,
        "CAGR %": cagr,
        "Ann. volatility %": volatility,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Max drawdown %": max_drawdown,
        "Calmar": calmar,
        "Monthly VaR 95 %": monthly_var,
        "Monthly CVaR 95 %": monthly_cvar,
        "Best month %": best_month,
        "Worst month %": worst_month,
        "% positive months": positive_months,
        "Tracking error %": tracking_error,
    }


def metrics_frame(results: dict[str, pd.Series],
                  benchmark_name: str | None = None,
                  risk_free: float = 0.0,
                  var_confidence: float = 0.95) -> pd.DataFrame:
    """
    The results table: one row per metric, one column per portfolio.

    results : {"ESAA": <index series>, "DSAA 2026": <index series>, ...}
    benchmark_name : which of those to measure tracking error against.
    """
    benchmark = results.get(benchmark_name) if benchmark_name else None
    columns = {
        name: summary_metrics(series, benchmark=benchmark,
                              risk_free=risk_free, var_confidence=var_confidence)
        for name, series in results.items()
    }
    frame = pd.DataFrame(columns).reindex(METRIC_ROWS)
    frame.index.name = "Metric"
    return frame
