"""
=============================================================================
 TAXONOMY  —  the model list, and rolling 16 asset classes up to 6 or 4
=============================================================================

WHAT THIS FILE DOES
    Three small jobs, all driven by settings.toml:

    model_directory()   one row per model — this is what fills the dropdown
    scenario_matrix()   pull ONE model + ONE risk profile out of the big table
                        and return it as   index = asset code,
                                           columns = scenarios,  values = %
    rollup()            add the 16 asset classes up to their 6 sub-groups or
                        their 4 groups
    rollup_matrix()     the same, applied to every scenario column at once

    THE TWO LEVELS OF GROUPING
        16 asset codes      EME, DME, Gov, Infl, EMD_L, ... , Cash
              |  cfg.subgroup_of
        6 sub-groups        Equity, Risky FI, Defensive FI,
                            liquid alts, illiq alts, Cash
              |  (independent mapping — NOT a roll-up of the sub-groups)
        4 groups            Equity, Fixed Income, Alternatives, Cash

    Both mappings come from the same [[asset_classes]] entries in
    settings.toml, where each code names its own `subgroup` and its own
    `group`. So you can move a code between sub-groups without disturbing its
    group, and vice versa.

WHERE TO CHANGE WHAT
    * Which sub-group / group a code belongs to -> settings.toml
                                                   [[asset_classes]]
    * Row order in every table                  -> the order of the
                                                   [[asset_classes]] entries
    * Add a THIRD level of grouping             -> add the field in
      settings.toml + an accessor in core/config.py, then extend rollup()

NO STREAMLIT IN THIS FILE.
"""
from __future__ import annotations

import pandas as pd

from core.config import Config


def model_directory(portfolios: pd.DataFrame) -> pd.DataFrame:
    """One row per model: model_id, model_name, currency."""
    d = (portfolios.groupby(["model_id", "model_name", "currency"], as_index=False)
         .size().drop(columns="size")
         .sort_values("model_name")
         .reset_index(drop=True))
    return d


def scenario_matrix(portfolios: pd.DataFrame, cfg: Config, model_id: str, rp: int) -> pd.DataFrame:
    """
    DataFrame indexed by asset code (config order), one column per scenario,
    values = weights (percent). Missing codes filled with 0.
    """
    scen = cfg.scenarios
    sub = portfolios[(portfolios.model_id == model_id) & (portfolios.risk_profile == rp)]
    sub = sub.set_index("code")[scen]
    out = sub.reindex(cfg.asset_codes).fillna(0.0)
    out.index.name = "code"
    return out[scen]


def rollup(weights: pd.Series, cfg: Config, level: str) -> pd.Series:
    """
    Roll a code-indexed weight series up to 'subgroup' or 'group' level.
    Returns a series indexed by the level's names in config order.
    """
    if level == "subgroup":
        mapping, order = cfg.subgroup_of, cfg.subgroups
    elif level == "group":
        mapping, order = cfg.group_of, cfg.groups
    else:
        raise ValueError("level must be 'subgroup' or 'group'")
    s = weights.copy()
    s.index = [mapping.get(c, "Unmapped") for c in s.index]
    agg = s.groupby(level=0).sum()
    return agg.reindex(order).fillna(0.0)


def rollup_matrix(matrix: pd.DataFrame, cfg: Config, level: str) -> pd.DataFrame:
    """Apply `rollup` to every column of a scenario matrix."""
    return pd.DataFrame({c: rollup(matrix[c], cfg, level) for c in matrix.columns})
