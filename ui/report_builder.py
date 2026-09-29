"""
=============================================================================
 REPORT BUILDER  —  gathers everything the report needs, then exports it
=============================================================================

WHAT THIS FILE DOES
    Sits between the sidebar's "Build full report" button and
    core/report_export.py.

        sidebar button
              |
        ui/report_builder.py   <- reads session state, re-runs the frontier
              |                    and the backtests, assembles DataFrames
        core/report_export.py  <- writes the .xlsx bytes

    It exists so that core/report_export.py stays free of Streamlit: all the
    session-state reading happens here.

WHAT GOES INTO THE REPORT
    * the model currently selected in the dropdown (shared by the Portfolios
      and Backtesting pages via st.session_state["selected_model"])
    * that model's weights INCLUDING any What-if edits
    * the CMA including any session edits
    * a freshly solved efficient frontier
    * a backtest of all three scenarios over the full available history

    The backtest here deliberately uses the FULL history and all scenarios,
    not whatever the Backtesting page happens to be showing - a downloaded
    report should be complete rather than a snapshot of one screen.

WHERE TO CHANGE WHAT
    * Which sheets appear      -> core/report_export.py build_workbook()
    * What the report contains -> build() below
    * The button itself        -> ui/sidebar_nav.py

CALLED BY
    ui/sidebar_nav.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import backtest as bt
from core.config import Config
from core.history_loader import load_history
from core.report_export import build_workbook
from core.report_tables import (all_columns, granular_block, group_block,
                                metrics_block, subgroup_block)
from core.taxonomy import model_directory, scenario_matrix
from ui import weight_edits

try:
    from core.frontier import build as build_frontier
    FRONTIER_AVAILABLE = True
except Exception:                                   # pragma: no cover
    FRONTIER_AVAILABLE = False


# --------------------------------------------------------------------------- #
# assembling the wide tables                                                 #
# --------------------------------------------------------------------------- #
def _house_table(cfg: Config, weights_by_rp: dict, cma, corr) -> pd.DataFrame:
    """
    The page-1 table as one wide frame: rows are the asset codes, then the
    sub-group, group and metric rows; columns are (RP, scenario).
    """
    columns = all_columns(cfg)
    blocks = []

    for builder, label in [(granular_block, None),
                           (subgroup_block, "— SUB-GROUP —"),
                           (group_block, "— GROUP —")]:
        pieces = {}
        for rp, weights in weights_by_rp.items():
            frame = builder(cfg, weights)[columns]
            pieces[cfg.rp_short(rp)] = frame
        wide = pd.concat(pieces, axis=1)
        if label:
            spacer = pd.DataFrame([[None] * wide.shape[1]],
                                  index=[label], columns=wide.columns)
            blocks.append(spacer)
        blocks.append(wide)

    metric_pieces = {}
    for rp, weights in weights_by_rp.items():
        metric_pieces[cfg.rp_short(rp)] = metrics_block(cfg, weights, cma, corr)[columns]
    metrics_wide = pd.concat(metric_pieces, axis=1)
    blocks.append(pd.DataFrame([[None] * metrics_wide.shape[1]],
                               index=["— RISK-RETURN METRICS —"],
                               columns=metrics_wide.columns))
    blocks.append(metrics_wide)

    out = pd.concat(blocks)
    out.index.name = "Asset Class"
    return out


def _metrics_all_profiles(cfg: Config, weights_by_rp: dict,
                          cma, corr) -> pd.DataFrame:
    """Risk-return metrics for every profile x scenario, as one table."""
    pieces = {cfg.rp_short(rp): metrics_block(cfg, weights, cma, corr)[all_columns(cfg)]
              for rp, weights in weights_by_rp.items()}
    out = pd.concat(pieces, axis=1)
    out.index.name = "Metric"
    return out


# --------------------------------------------------------------------------- #
# frontier + backtest                                                        #
# --------------------------------------------------------------------------- #
def _frontier_pieces(cfg: Config, cma, corr, weights_by_rp: dict):
    """(curve points, gap table) or (None, None) if SciPy is unavailable."""
    if not FRONTIER_AVAILABLE:
        return None, None

    configured_rf = str(cfg.frontier.get("risk_free", "")).strip()
    frontier = build_frontier(cma, corr, cfg.asset_codes,
                              n_points=int(cfg.frontier.get("points", 120)),
                              rf=float(configured_rf) if configured_rf else None)

    curve = frontier.points.rename(columns={"vol": "Volatility %",
                                            "ret": "Expected return %"})

    from core.analytics import compute
    rows = []
    for scenario in cfg.scenarios:
        for rp, weights in weights_by_rp.items():
            point = compute(weights[scenario], cma, corr, cfg)
            gap = frontier.gap(point.volatility, point.exp_return)
            rows.append({
                "Scenario": scenario,
                "Profile": cfg.rp_short(rp),
                "Risk %": point.volatility,
                "Return %": point.exp_return,
                "Frontier return @ risk %": point.exp_return + gap,
                "Return gap (pp)": gap,
            })
    return curve, pd.DataFrame(rows)


def _backtest_pieces(cfg: Config, currency: str, weights_by_rp: dict):
    """
    Backtest every scenario at every risk profile over the full history.
    Returns (growth, drawdown, rolling_return, rolling_vol, metrics, prices,
             notes) - all empty/None when there is no price history.
    """
    history = load_history(cfg, currency)
    if not history.ok:
        return {}, {}, {}, {}, None, None, [
            f"No price history for {currency}, so the backtest sheets are "
            f"not included."
        ]

    rebalance = cfg.backtest.get("rebalance", "M") or None
    rolling_months = int(cfg.backtest.get("rolling_months", 12))
    window = int(rolling_months / 12 * bt.TRADING_DAYS)

    growth, dropped_any = {}, []
    for scenario in cfg.scenarios:
        for rp, weights in weights_by_rp.items():
            aligned, dropped = bt.align_weights(weights[scenario], history.prices)
            dropped_any += [c for c in dropped if c not in dropped_any]
            if aligned.empty:
                continue
            series = bt.run(history.prices, aligned, rebalance=rebalance)
            if not series.empty:
                growth[f"{cfg.rp_short(rp)} {scenario}"] = series

    drawdown = {name: bt.drawdown_series(s) for name, s in growth.items()}
    rolling_return = {name: bt.rolling_return(s, window) for name, s in growth.items()}
    rolling_vol = {name: bt.rolling_volatility(s, window) for name, s in growth.items()}

    benchmark = next((n for n in growth if n.endswith(cfg.scenario_benchmark)), None)
    metrics = bt.metrics_frame(
        growth, benchmark_name=benchmark,
        risk_free=float(cfg.backtest.get("risk_free", 0.0)),
        var_confidence=float(cfg.backtest.get("var_confidence", 0.95)),
    )

    notes = [
        f"Backtest covers the full available history "
        f"({history.start:%b %Y} to {history.end:%b %Y}), rebalanced "
        f"'{cfg.backtest.get('rebalance', 'M')}'.",
    ]
    if dropped_any:
        notes.append(f"Excluded for lack of price history: {', '.join(dropped_any)}.")
    if history.missing_codes:
        notes.append(f"Asset classes with no price column: "
                     f"{', '.join(history.missing_codes)}.")

    return growth, drawdown, rolling_return, rolling_vol, metrics, history.prices, notes


# --------------------------------------------------------------------------- #
# the public entry point                                                     #
# --------------------------------------------------------------------------- #
def build(cfg: Config, data, cma_store) -> tuple[bytes, str]:
    """
    Build the full report for the currently selected model.
    Returns (xlsx bytes, suggested filename).
    """
    directory = model_directory(data.portfolios)
    if directory.empty:
        raise ValueError("There are no model portfolios to report on.")

    model_ids = directory["model_id"].tolist()
    model_id = st.session_state.get("selected_model", model_ids[0])
    if model_id not in model_ids:
        model_id = model_ids[0]

    row = directory.set_index("model_id").loc[model_id]
    currency, model_name = row["currency"], row["model_name"]

    cma = cma_store.effective(currency)
    corr = data.corr.get(currency)

    # use the user's edited weights when they exist, else the file
    edited = st.session_state.get(weight_edits.SESSION_KEY, {}).get(model_id)
    weights_by_rp = edited or {
        rp: scenario_matrix(data.portfolios, cfg, model_id, rp)
        for rp in cfg.rp_ids
    }

    notes = []
    if edited:
        notes.append("Weights include the What-if edits made in this session.")
    if cma_store.is_modified(currency):
        notes.append(f"The {currency} CMA includes this session's edits.")

    frontier_points, frontier_gaps = _frontier_pieces(cfg, cma, corr, weights_by_rp)
    (growth, drawdown, rolling_return, rolling_vol,
     backtest_metrics, prices, backtest_notes) = _backtest_pieces(
        cfg, currency, weights_by_rp)

    workbook = build_workbook(
        cfg,
        model_name=model_name,
        currency=currency,
        weights_by_rp=weights_by_rp,
        cma=cma,
        corr=corr,
        house_table=_house_table(cfg, weights_by_rp, cma, corr),
        metrics_all=_metrics_all_profiles(cfg, weights_by_rp, cma, corr),
        frontier_points=frontier_points,
        frontier_gaps=frontier_gaps,
        backtest_growth=growth,
        backtest_drawdown=drawdown,
        backtest_rolling_return=rolling_return,
        backtest_rolling_vol=rolling_vol,
        backtest_metrics=backtest_metrics,
        prices=prices,
        notes=notes + backtest_notes,
    )
    filename = f"{model_id}_full_report.xlsx"
    return workbook, filename
