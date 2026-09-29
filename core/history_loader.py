"""
=============================================================================
 HISTORY LOADER  —  reads and validates the daily price files
=============================================================================

WHAT THIS FILE DOES
    Reads one currency's price history from data/history/prices_<CCY>.csv and
    reports anything wrong with it. Kept separate from core/data_loader.py
    because these files are large (~750 KB each) and only the Backtesting page
    needs them - they are loaded on demand, not at start-up.

WHAT COMES BACK  (PriceHistory)
    .prices         DataFrame, index = date, columns = asset code, daily
                    total-return index levels
    .missing_codes  in settings.toml but NOT in the price file -> these are
                    dropped from any backtest and the page warns about it
    .extra_codes    in the price file but not in settings.toml -> ignored
    .errors         fatal (file missing, unreadable, too few rows)
    .ok             True when there are no errors

HOW GAPS ARE HANDLED
    Different markets have different holidays, so a date that exists for one
    asset may be blank for another. Blanks are forward-filled (the asset simply
    did not trade that day). Any leading rows before an asset's first real
    price are dropped from the whole frame, so every backtest starts on a date
    where every included asset has a price.

WHERE TO CHANGE WHAT
    * File location / naming   -> settings.toml [data].history_dir
    * The schema               -> scripts/generate_history_data.py docstring
    * Gap handling             -> _clean() below
    * Minimum usable history   -> MIN_ROWS below

NO STREAMLIT IN THIS FILE.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import pandas as pd

from core.config import Config

DATE_COLUMN = "date"
MIN_ROWS = 60          # fewer than ~3 months of prices is not worth backtesting


@dataclass
class PriceHistory:
    prices: pd.DataFrame
    missing_codes: list[str] = field(default_factory=list)
    extra_codes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and not self.prices.empty

    @property
    def start(self):
        return self.prices.index[0] if not self.prices.empty else None

    @property
    def end(self):
        return self.prices.index[-1] if not self.prices.empty else None

    @property
    def years(self) -> float:
        if self.prices.empty:
            return 0.0
        return (self.end - self.start).days / 365.25


def history_path(cfg: Config, currency: str) -> str:
    folder = cfg.path("history_dir")
    return os.path.join(folder, f"prices_{currency}.csv")


def _clean(frame: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill holiday gaps, then drop any leading rows that are still blank."""
    frame = frame.sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    frame = frame.ffill()
    return frame.dropna(how="any")


def load_history(cfg: Config, currency: str) -> PriceHistory:
    """Read one currency's daily price history."""
    path = history_path(cfg, currency)
    if not os.path.exists(path):
        return PriceHistory(
            pd.DataFrame(),
            errors=[f"No price history for {currency}. Expected a file at {path}. "
                    f"Run scripts/generate_history_data.py, or add your own."],
        )

    try:
        frame = pd.read_csv(path)
    except Exception as exc:                       # noqa: BLE001 - surface anything
        return PriceHistory(pd.DataFrame(),
                            errors=[f"Could not read {path}: {exc}"])

    frame.columns = [str(c).strip() for c in frame.columns]
    if DATE_COLUMN not in frame.columns:
        return PriceHistory(
            pd.DataFrame(),
            errors=[f"{os.path.basename(path)} has no '{DATE_COLUMN}' column. "
                    f"Found: {list(frame.columns)[:8]}"],
        )

    frame[DATE_COLUMN] = pd.to_datetime(frame[DATE_COLUMN], errors="coerce")
    frame = frame.dropna(subset=[DATE_COLUMN]).set_index(DATE_COLUMN)

    # keep only the asset codes settings.toml knows about, in its order
    known = [c for c in cfg.asset_codes if c in frame.columns]
    missing = [c for c in cfg.asset_codes if c not in frame.columns]
    extra = [c for c in frame.columns if c not in cfg.asset_codes]

    if not known:
        return PriceHistory(
            pd.DataFrame(), missing_codes=missing, extra_codes=extra,
            errors=[f"{os.path.basename(path)} has no columns matching any asset "
                    f"code in settings.toml. Column names must be codes like "
                    f"'EME', 'DME'. Found: {extra[:8]}"],
        )

    prices = frame[known].apply(pd.to_numeric, errors="coerce")
    prices = _clean(prices)

    errors = []
    if len(prices) < MIN_ROWS:
        errors.append(f"Only {len(prices)} usable rows of price history for "
                      f"{currency} (need at least {MIN_ROWS}).")

    return PriceHistory(prices, missing_codes=missing, extra_codes=extra,
                        errors=errors)
