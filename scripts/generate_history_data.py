"""
=============================================================================
 HISTORY GENERATOR  —  makes fake but realistic daily price files
=============================================================================

    .venv/Scripts/python.exe scripts/generate_history_data.py

WHAT THIS FILE DOES
    Writes 20 years of daily total-return index levels for every asset class,
    one file per currency, so the Backtesting page has something to run on.

    IT OVERWRITES:  data/history/prices_<CCY>.csv

    ==> Once your real price history is in data/history/, do not run this
        again - it will overwrite it.

HOW THE FAKE PRICES ARE BUILT
    The paths are simulated FROM THE CMA, so the backtest roughly agrees with
    the forward-looking numbers on the Portfolios page:

        drift  = expected_return from data/cma/cma_<CCY>.csv
        vol    = volatility     from the same file
        shape  = correlated draws using data/cma/corr_<CCY>.csv (Cholesky)

    Two stress episodes are injected so drawdown and VaR metrics look
    realistic - a 2008-style bear market and a 2020-style crash. Risk assets
    fall hard, government bonds rally.

THE SCHEMA YOUR REAL DATA MUST MATCH
    data/history/prices_<CCY>.csv

        date,EME,DME,Gov,Infl,...        <- one column per asset code
        2006-01-02,100.0,100.0,...       <- daily total-return INDEX LEVELS
        2006-01-03,100.62,100.21,...        (not returns, not prices ex-income)

    * `date` ascending, any pandas-readable format
    * column names must match [[asset_classes]].code in settings.toml
    * an asset class with no column is reported on the Backtesting page and
      dropped from the portfolio - see core/history_loader.py

NO STREAMLIT IN THIS FILE.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CMA_DIR = os.path.join(DATA, "cma")
HISTORY_DIR = os.path.join(DATA, "history")

YEARS = 20
TRADING_DAYS = 252
START_LEVEL = 100.0

# Stress episodes: (start fraction through the sample, length in days, severity)
# `severity` is an extra annualised drift applied to risk assets during the
# window. Calibrated so a full-beta asset falls roughly:
#     window 1  ~ -48% peak to trough   (a 2008-style bear market)
#     window 2  ~ -30% peak to trough   (a 2020-style crash)
# The drag is added back over the rest of the sample (see the recentring step
# in simulate_currency), so long-run returns still match the CMA.
# Each episode is (start_fraction, crash_days, severity, recovery_days).
# `severity` is an extra annualised drift applied while the crash runs;
# `recovery_days` is how long the bounce afterwards takes. Without the bounce
# the market never recovers and every trough ends up at the far right of the
# chart. RECOVERY_SHARE sets how much of the fall is clawed back in that
# window - the remainder is absorbed by the recentring step further down.
# Fractions are chosen so that, with a sample starting ~mid-2007, the crashes
# land in late 2008 and early 2020 - where a reader expects to see them.
STRESS_WINDOWS = [
    (0.02, 350, -0.38, 520),   # a 2008-style bear market, ~2 year recovery
    (0.66, 45, -1.70, 170),    # a 2020-style crash, ~8 month recovery
]
RECOVERY_SHARE = 0.88
# How hard each group is hit during a stress window (1.0 = full severity).
STRESS_BETA = {
    "Equity": 1.00,
    "Alternatives": 0.60,
    "Fixed Income": 0.15,
    "Cash": 0.00,
}
# Government bonds rally when risk assets fall.
SAFE_HAVEN_CODES = {"Gov", "Infl"}


def _asset_groups() -> dict[str, str]:
    """code -> group, read straight out of settings.toml so the two agree."""
    import tomllib
    with open(os.path.join(ROOT, "settings.toml"), "rb") as fh:
        cfg = tomllib.load(fh)
    return {a["code"]: a["group"] for a in cfg["asset_classes"]}


def _currencies() -> list[str]:
    import tomllib
    with open(os.path.join(ROOT, "settings.toml"), "rb") as fh:
        return list(tomllib.load(fh)["currencies"])


def simulate_currency(currency: str, groups: dict[str, str],
                      rng: np.random.Generator) -> pd.DataFrame:
    """Simulate one currency's daily index levels from its CMA."""
    cma = pd.read_csv(os.path.join(CMA_DIR, f"cma_{currency}.csv")).set_index("code")
    corr = pd.read_csv(os.path.join(CMA_DIR, f"corr_{currency}.csv")).set_index("code")

    codes = [c for c in cma.index if c in corr.index]
    mu = cma.loc[codes, "expected_return"].to_numpy(float) / 100.0
    sigma = cma.loc[codes, "volatility"].to_numpy(float) / 100.0
    correlation = corr.loc[codes, codes].to_numpy(float)

    # Cholesky needs a strictly positive-definite matrix; nudge if necessary
    try:
        chol = np.linalg.cholesky(correlation)
    except np.linalg.LinAlgError:
        values, vectors = np.linalg.eigh(correlation)
        correlation = vectors @ np.diag(np.clip(values, 1e-6, None)) @ vectors.T
        d = np.sqrt(np.diag(correlation))
        correlation = correlation / np.outer(d, d)
        chol = np.linalg.cholesky(correlation)

    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(),
                           periods=YEARS * TRADING_DAYS)
    n_days, n_assets = len(dates), len(codes)

    # correlated standard normal shocks
    shocks = rng.standard_normal((n_days, n_assets)) @ chol.T

    # baseline geometric Brownian motion, in daily terms
    dt = 1.0 / TRADING_DAYS
    drift = (mu - 0.5 * sigma ** 2) * dt
    diffusion = sigma * np.sqrt(dt) * shocks
    daily_log_returns = drift + diffusion

    # overlay the stress episodes, each followed by a recovery
    for start_fraction, length, severity, recovery_days in STRESS_WINDOWS:
        first = int(start_fraction * n_days)
        last = min(first + length, n_days)
        recovery_end = min(last + recovery_days, n_days)
        for j, code in enumerate(codes):
            beta = STRESS_BETA.get(groups.get(code, "Equity"), 0.5)
            if code in SAFE_HAVEN_CODES:
                beta = -0.25                      # flight to quality
            per_day = severity * beta * dt
            daily_log_returns[first:last, j] += per_day
            # bounce back over the recovery window
            if recovery_end > last:
                total_fall = per_day * (last - first)
                daily_log_returns[last:recovery_end, j] += (
                    -total_fall * RECOVERY_SHARE / (recovery_end - last))

    # ---- recentre so the FULL-PERIOD return still matches the CMA ---------
    # Without this the stress episodes are a permanent drag and 20-year equity
    # returns come out negative. Here the crashes stay (so drawdown and VaR
    # look real) but each asset is nudged by a constant daily amount so its
    # geometric return over the whole sample lands on  mu - 0.5*sigma^2.
    target_total_log = (mu - 0.5 * sigma ** 2) * YEARS
    realised_total_log = daily_log_returns.sum(axis=0)
    daily_log_returns += (target_total_log - realised_total_log) / n_days

    levels = START_LEVEL * np.exp(np.cumsum(daily_log_returns, axis=0))
    frame = pd.DataFrame(levels, index=dates, columns=codes).round(4)
    frame.index.name = "date"
    return frame


def main() -> None:
    os.makedirs(HISTORY_DIR, exist_ok=True)
    groups = _asset_groups()
    rng = np.random.default_rng(20)

    for currency in _currencies():
        cma_path = os.path.join(CMA_DIR, f"cma_{currency}.csv")
        if not os.path.exists(cma_path):
            print(f"  skip {currency}: no CMA file, run generate_sample_data.py first")
            continue
        frame = simulate_currency(currency, groups, rng)
        out = os.path.join(HISTORY_DIR, f"prices_{currency}.csv")
        frame.to_csv(out)
        size_kb = os.path.getsize(out) / 1024
        print(f"  wrote history/prices_{currency}.csv  "
              f"({len(frame):,} days x {len(frame.columns)} assets, {size_kb:,.0f} KB, "
              f"{frame.index[0].date()} -> {frame.index[-1].date()})")


if __name__ == "__main__":
    print("generating daily price history...")
    main()
