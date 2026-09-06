"""
=============================================================================
 THE FOUR TABLE BLOCKS  (granular / sub-group / group / risk-return metrics)
=============================================================================

WHAT THIS FILE DOES
    Turns one risk profile's weight matrix into the four numeric blocks that
    make up the "house format" table. Three different places display these
    same numbers, so they are built once, here:

        ui/sections/house_table.py     -> the big RP1-RP5 table on screen
        ui/sections/whatif_editor.py   -> the live metrics under the editor
        core/excel_export.py           -> the .xlsx download

    "Weights matrix" everywhere below means a pandas DataFrame shaped like:

                 ESAA   DSAA 2026   DSAA 2025      <- one column per scenario
        code
        EME       2.64       4.72        1.70      <- percent, not fractions
        DME       9.54      10.79        7.74
        ...

WHERE TO CHANGE WHAT
    * Add / rename / reorder a metric row   -> METRIC_ROWS + metrics_block()
    * Change how "Change" is calculated     -> settings.toml [scenarios].change
    * Change the Tracking Error benchmark   -> settings.toml [scenarios].benchmark
    * Change the Excel sheet layout         -> stacked_block()

NO STREAMLIT IN THIS FILE — it is pure pandas so scripts/smoke_test.py can
check the numbers without launching the app.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.analytics import portfolio_metrics
from core.config import Config
from core.taxonomy import rollup_matrix

# The four rows of the metrics block, in display order.
# Add a row here AND add the matching line in metrics_block() below.
METRIC_ROWS = ["Exp Ret", "Exp Vol", "Exp Sharpe", "Tracking Error"]

CHANGE_COL = "Change"


# --------------------------------------------------------------------------- #
# shared helper                                                              #
# --------------------------------------------------------------------------- #
def add_change_column(cfg: Config, df: pd.DataFrame) -> pd.DataFrame:
    """
    Append the "Change" column = <first scenario in [scenarios].change>
                               - <second scenario in [scenarios].change>
    e.g. with the default settings.toml this is  DSAA 2026 - DSAA 2025.
    """
    newer, older = cfg.scenario_change
    out = df.copy()
    out[CHANGE_COL] = out[newer] - out[older]
    return out


def all_columns(cfg: Config) -> list[str]:
    """Every column a block can have: the scenarios, then Change."""
    return list(cfg.scenarios) + [CHANGE_COL]


# --------------------------------------------------------------------------- #
# the four blocks                                                            #
# --------------------------------------------------------------------------- #
def granular_block(cfg: Config, weights: pd.DataFrame) -> pd.DataFrame:
    """Rows = the 16 asset-class codes, in settings.toml order."""
    out = add_change_column(cfg, weights.reindex(cfg.asset_codes).fillna(0.0))
    out.index.name = "Asset Class"
    return out


def subgroup_block(cfg: Config, weights: pd.DataFrame) -> pd.DataFrame:
    """Rows = Equity / Risky FI / Defensive FI / liquid alts / illiq alts / Cash."""
    out = add_change_column(cfg, rollup_matrix(weights, cfg, "subgroup"))
    out.index.name = "Asset Class"
    return out


def group_block(cfg: Config, weights: pd.DataFrame) -> pd.DataFrame:
    """Rows = Equity / Fixed Income / Alternatives / Cash."""
    out = add_change_column(cfg, rollup_matrix(weights, cfg, "group"))
    out.index.name = "Asset Class"
    return out


def metrics_block(cfg: Config, weights: pd.DataFrame,
                  cma: pd.DataFrame, corr: pd.DataFrame) -> pd.DataFrame:
    """
    Rows = Exp Ret / Exp Vol / Exp Sharpe / Tracking Error, one column per
    scenario plus Change.

    Tracking Error is measured against the scenario named in
    settings.toml [scenarios].benchmark (ESAA by default), so that scenario's
    own tracking error is always exactly 0.
    """
    benchmark_name = cfg.scenario_benchmark
    benchmark_weights = (weights[benchmark_name]
                         if benchmark_name in weights.columns else None)
    risk_free = cfg.metrics_risk_free

    data: dict[str, dict[str, float]] = {row: {} for row in METRIC_ROWS}
    for scenario in cfg.scenarios:
        m = portfolio_metrics(weights[scenario], cma, corr, cfg,
                              benchmark=benchmark_weights, rf=risk_free)
        data["Exp Ret"][scenario] = m.exp_return
        data["Exp Vol"][scenario] = m.exp_vol
        data["Exp Sharpe"][scenario] = m.sharpe
        data["Tracking Error"][scenario] = (0.0 if scenario == benchmark_name
                                            else m.tracking_error)

    out = add_change_column(cfg, pd.DataFrame(data).T[list(cfg.scenarios)])
    out.index.name = "Asset Class"
    return out


# --------------------------------------------------------------------------- #
# all four stacked (used by the Excel export)                                #
# --------------------------------------------------------------------------- #
def stacked_block(cfg: Config, weights: pd.DataFrame,
                  cma: pd.DataFrame, corr: pd.DataFrame) -> pd.DataFrame:
    """
    One risk profile in the full house layout, top to bottom:

        16 granular rows
        (blank)
        6 sub-group rows
        (blank)
        4 group rows
        Risk-Return Metrics          <- label row
        4 metric rows

    This is exactly what one sheet of the Excel download looks like.
    """
    cols = all_columns(cfg)

    def blank(label: str = "") -> pd.DataFrame:
        return pd.DataFrame([[np.nan] * len(cols)], index=[label], columns=cols)

    out = pd.concat([
        granular_block(cfg, weights)[cols],
        blank(),
        subgroup_block(cfg, weights)[cols],
        blank(),
        group_block(cfg, weights)[cols],
        blank("Risk-Return Metrics"),
        metrics_block(cfg, weights, cma, corr)[cols],
    ])
    out.index.name = "Asset Class"
    return out.round(3)
