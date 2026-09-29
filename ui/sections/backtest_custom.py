"""
=============================================================================
 BACKTEST SECTION 2 — CUSTOM PORTFOLIO BUILDER
=============================================================================

WHAT THIS FILE DOES
    Lets the user build their own weight vector and backtest it alongside the
    model portfolios. Seeded from whichever model/profile/scenario is showing,
    so you start from something sensible and tweak rather than typing 16
    numbers from scratch.

        BUILD YOUR OWN PORTFOLIO
        [Reset to <model> RP3 DSAA 2026]     total: 100.0  ✓
        ┌──────────────┬────────┐
        │ Asset Class  │ Weight │   <- editable, 16 rows
        │ EME          │   9.96 │
        │ ...          │        │
        └──────────────┴────────┘

    The weights live in st.session_state, exactly like the What-if editor on
    the Portfolios page, and are lost when the session ends.

WHY IT DOES NOT FORCE THE TOTAL TO 100
    Telling you the total and letting you fix it is friendlier than silently
    renormalising. The backtest itself always renormalises (see
    core/backtest.py align_weights), so a total of 90 or 110 still produces a
    valid result - it is just scaled. The caption says so.

WHERE TO CHANGE WHAT
    * Seeding behaviour    -> seed_from() below
    * The editor layout    -> render() below
    * How totals are fixed -> core/backtest.py align_weights()

CALLED BY
    ui/page_backtest.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.config import Config
from ui.widgets import card_title

SESSION_KEY = "backtest_custom_weights"
SEED_LABEL_KEY = "backtest_custom_seed_label"
EDITOR_KEY = "backtest_custom_editor"

CUSTOM_NAME = "Custom portfolio"


def seed_from(cfg: Config, weights: pd.Series, label: str,
              force: bool = False) -> None:
    """
    Put `weights` into session state as the starting point for the custom
    portfolio. Only does anything the first time, unless `force` is True
    (which is what the Reset button uses).
    """
    if force or SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = (weights.reindex(cfg.asset_codes)
                                         .fillna(0.0).astype(float))
        st.session_state[SEED_LABEL_KEY] = label
        st.session_state.pop(EDITOR_KEY, None)      # clear pending edits


def current_weights(cfg: Config) -> pd.Series:
    """The custom weights as they stand right now, including pending edits."""
    weights = st.session_state.get(SESSION_KEY)
    if weights is None:
        return pd.Series(0.0, index=cfg.asset_codes)

    # fold in anything typed into the editor but not yet written back, so the
    # charts below update on the same run (same trick as ui/weight_edits.py)
    state = st.session_state.get(EDITOR_KEY)
    if isinstance(state, dict) and state.get("edited_rows"):
        weights = weights.copy()
        for row_number, changes in state["edited_rows"].items():
            try:
                code = cfg.asset_codes[int(row_number)]
            except (ValueError, IndexError):
                continue
            if "Weight %" in changes and changes["Weight %"] is not None:
                weights.loc[code] = float(changes["Weight %"])
        st.session_state[SESSION_KEY] = weights
    return weights


def render(cfg: Config, seed_weights: pd.Series, seed_label: str) -> pd.Series:
    """Draw the builder card and return the current custom weights (percent)."""
    seed_from(cfg, seed_weights, seed_label)
    weights = current_weights(cfg)

    with st.container(border=True):
        card_title("Build your own portfolio")

        header = st.columns([2.4, 1.6])
        with header[0]:
            if st.button(f"↺  Reset to {seed_label}", key="bt_custom_reset",
                         use_container_width=True):
                seed_from(cfg, seed_weights, seed_label, force=True)
                st.rerun()
        with header[1]:
            total = float(weights.sum())
            if abs(total - 100.0) < 0.05:
                st.markdown(
                    f'<div style="padding-top:.45rem;font-size:.82rem;color:#7A1F2B;'
                    f'font-weight:600;">Total {total:.1f}  ✓</div>',
                    unsafe_allow_html=True)
            else:
                st.markdown(
                    f'<div style="padding-top:.45rem;font-size:.82rem;color:#7A6E71;">'
                    f'Total <b>{total:.1f}</b> — will be scaled to 100</div>',
                    unsafe_allow_html=True)

        grid = pd.DataFrame({
            "code": cfg.asset_codes,
            "Weight %": weights.reindex(cfg.asset_codes).fillna(0.0).to_numpy(),
        })
        edited = st.data_editor(
            grid, key=EDITOR_KEY, hide_index=True,
            height=35 * len(cfg.asset_codes) + 40,
            use_container_width=False, disabled=["code"],
            column_config={
                "code": st.column_config.TextColumn("Asset Class", width="small"),
                "Weight %": st.column_config.NumberColumn(
                    "Weight %", format="%.2f", step=0.25,
                    min_value=0.0, max_value=100.0, width="small"),
            },
        )
        updated = (pd.Series(edited["Weight %"].to_numpy(),
                             index=edited["code"].to_numpy(), dtype=float)
                   .reindex(cfg.asset_codes).fillna(0.0))
        st.session_state[SESSION_KEY] = updated

        st.caption("Long-only. Weights are scaled to 100 before the backtest "
                   "runs, so relative sizes are what matter.")

    return updated
