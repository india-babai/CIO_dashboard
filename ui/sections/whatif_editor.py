"""
=============================================================================
 SECTION 2 — WHAT-IF EDITOR  (change weights and watch everything recalculate)
=============================================================================

WHAT THIS FILE DOES
    Draws the card below the house table:

        WHAT-IF — ADJUST INDIVIDUAL WEIGHTS
        [RP1][RP2][RP3][RP4][RP5]              <- which profile you're editing
        ┌──────────────────────┐  ┌────────────────────────────────────────┐
        │ editable weight grid │  │ DSAA 2026 vs ESAA — active weights bar │
        │ (16 rows, compact)   │  │                                        │
        ├──────────────────────┤  │                                        │
        │ Risk-Return Metrics  │  │                                        │
        │ (live, compact)      │  │                                        │
        └──────────────────────┘  └────────────────────────────────────────┘

    Typing a number here updates the house table above, the charts and the
    efficient frontier — all on the same page load. See ui/weight_edits.py
    for how that works.

WHERE TO CHANGE WHAT
    * Left/right column split      -> st.columns([2, 3]) below
    * Editor height                -> `editor_height` below
    * Which scenarios are editable -> `columns` below (driven by the checkbox
                                      on ui/page_portfolios.py)
    * The bar chart                -> ui/charts.py  active_weights_bar()
    * The metrics numbers          -> core/report_tables.py  metrics_block()

CALLED BY
    ui/page_portfolios.py
"""
from __future__ import annotations

import streamlit as st

from core.analytics import diff_series
from core.config import Config
from core.report_tables import metrics_block
from ui import weight_edits
from ui.charts import active_weights_bar
from ui.theme import PLOTLY_CONFIG
from ui.widgets import card_title

ROW_HEIGHT_PX = 35          # roughly one data-editor row
HEADER_HEIGHT_PX = 40


def render(cfg: Config, model_id: str, show_all_scenarios: bool,
           cma, corr) -> None:
    weights_by_rp = st.session_state[weight_edits.SESSION_KEY][model_id]

    # which scenario columns to expose — matches the house table's checkbox
    columns = (list(cfg.scenarios) if show_all_scenarios
               else list(cfg.scenarios[:2]))

    card_title("What-if — adjust individual weights")

    # ---- which risk profile are we editing? ----------------------------- #
    picker_column, _spacer = st.columns([2, 5])
    with picker_column:
        chosen = st.segmented_control(
            "Edit RP", cfg.rp_ids, default=cfg.rp_ids[0],
            format_func=cfg.rp_short, key="whatif_rp",
        ) or cfg.rp_ids[0]
    rp = int(chosen)

    editor_height = ROW_HEIGHT_PX * len(cfg.asset_codes) + HEADER_HEIGHT_PX

    left, right = st.columns([2, 3], gap="large")

    # ------------------------------------------------------------------ #
    # LEFT: the editable grid, then the live metrics                     #
    # ------------------------------------------------------------------ #
    with left:
        grid = weights_by_rp[rp][columns].reset_index()
        edited = st.data_editor(
            grid,
            key=weight_edits.editor_widget_key(model_id, rp),
            hide_index=True,
            height=editor_height,
            use_container_width=False,      # keep it compact, not page-wide
            disabled=["code"],              # the asset code is not editable
            column_config={
                "code": st.column_config.TextColumn("Asset Class", width="small"),
                **{s: st.column_config.NumberColumn(s, format="%.2f", step=0.25,
                                                    width="small")
                   for s in columns},
            },
        )
        weight_edits.write_back(cfg, model_id, rp, edited, columns)

        # warn if a scenario no longer adds up to 100
        totals = weight_edits.scenario_totals(weights_by_rp[rp])
        off_target = [f"{s} {totals[s]:.1f}" for s in cfg.scenarios
                      if abs(totals[s] - 100) > 0.5]
        if off_target:
            st.caption("⚠ weights no longer sum to 100 — " + " · ".join(off_target))

        # live risk / return readout, deliberately compact
        metric_columns = (columns + ["Change"]) if show_all_scenarios else columns
        metrics = metrics_block(cfg, weights_by_rp[rp], cma, corr)
        card_title(f"Risk-Return Metrics · {cfg.rp_short(rp)} — updates as you edit",
                   top_margin=".8rem")
        st.dataframe(
            metrics[metric_columns].round(3),
            use_container_width=False,
            column_config={c: st.column_config.NumberColumn(c, format="%.3f",
                                                            width="small")
                           for c in metric_columns},
        )

    # ------------------------------------------------------------------ #
    # RIGHT: how far this scenario tilts away from the benchmark          #
    # ------------------------------------------------------------------ #
    with right:
        current = cfg.scenario_change[0]          # e.g. "DSAA 2026"
        benchmark = cfg.scenario_benchmark        # e.g. "ESAA"
        weights = weights_by_rp[rp]
        tilts = (diff_series(weights[current], weights[benchmark])
                 .reindex(cfg.asset_codes).fillna(0.0))

        card_title(f"{current} vs {benchmark} — active weights · {cfg.rp_short(rp)}")
        st.plotly_chart(active_weights_bar(tilts, height=editor_height),
                        config=PLOTLY_CONFIG, use_container_width=True)
