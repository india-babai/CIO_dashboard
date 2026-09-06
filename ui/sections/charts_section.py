"""
=============================================================================
 SECTION 3 — CHARTS  (allocation donut + capital/return/risk contribution)
=============================================================================

WHAT THIS FILE DOES
    The "Allocation & risk" card below the What-if editor. Three small
    controls choose what is shown, then two charts sit side by side:

        [RP1..RP5]  [ESAA | DSAA 2026 | DSAA 2025]  [Granular | Sub-group | Group]

        ┌─────────────────────────┐  ┌─────────────────────────────────────┐
        │  allocation donut       │  │  weight vs return vs risk, by       │
        │                         │  │  sub-group                          │
        └─────────────────────────┘  └─────────────────────────────────────┘

    Everything here reflects the user's What-if edits, because it reads the
    same session weights.

WHERE TO CHANGE WHAT
    * Add / remove a control     -> the st.columns block below
    * Default selections         -> the `default=` arguments below
    * Chart appearance           -> ui/charts.py
    * The roll-up maths          -> core/taxonomy.py rollup()
    * Contribution maths         -> core/analytics.py compute()

CALLED BY
    ui/page_portfolios.py
"""
from __future__ import annotations

import streamlit as st

from core.analytics import compute
from core.config import Config
from core.taxonomy import rollup
from ui.charts import allocation_donut, contribution_bar
from ui.theme import PLOTLY_CONFIG
from ui.widgets import card_title, horizontal_rule, section_heading

LEVELS = ["Granular", "Sub-group", "Group"]


def render(cfg: Config, model_name: str, currency: str,
           cma, corr, weights_by_rp: dict) -> None:
    horizontal_rule()
    section_heading(
        "Allocation & risk", "Charts",
        f"{model_name} — valued in {currency}. Reflects any edits made above.",
    )

    with st.container(border=True):
        # ---- controls --------------------------------------------------- #
        control_columns = st.columns([1.2, 1.5, 1.4])
        with control_columns[0]:
            rp = st.segmented_control(
                "RP", cfg.rp_ids,
                default=cfg.rp_ids[len(cfg.rp_ids) // 2],   # middle profile
                format_func=cfg.rp_short, key="charts_rp",
            ) or cfg.rp_ids[0]
        with control_columns[1]:
            default_scenario = (cfg.scenarios[1] if len(cfg.scenarios) > 1
                                else cfg.scenarios[0])
            scenario = st.segmented_control(
                "Scenario", cfg.scenarios, default=default_scenario,
                key="charts_scenario",
            ) or cfg.scenarios[0]
        with control_columns[2]:
            level = st.segmented_control(
                "Level", LEVELS, default="Sub-group", key="charts_level",
            ) or "Sub-group"

        # ---- pick the weights and the matching colours ------------------ #
        weights = weights_by_rp[int(rp)][scenario]

        if level == "Granular":
            display_weights = weights
            colour_of = cfg.asset_color
        elif level == "Sub-group":
            display_weights = rollup(weights, cfg, "subgroup")
            colour_of = lambda name: cfg.subgroup_colors.get(name, "#999999")
        else:
            display_weights = rollup(weights, cfg, "group")
            colour_of = lambda name: cfg.group_colors.get(name, "#999999")

        # ---- the two charts --------------------------------------------- #
        left, right = st.columns(2)
        with left:
            card_title(f"Allocation — {scenario} · {level}")
            st.plotly_chart(allocation_donut(display_weights, colour_of, height=300),
                            config=PLOTLY_CONFIG, use_container_width=True)
        with right:
            metrics = compute(weights, cma, corr, cfg)
            card_title("Capital vs return vs risk — by sub-group")
            st.plotly_chart(contribution_bar(metrics.per_subgroup, height=300),
                            config=PLOTLY_CONFIG, use_container_width=True)
