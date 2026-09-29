"""
=============================================================================
 BACKTEST SECTION 1 — CONTROLS  (what to compare, and over what period)
=============================================================================

WHAT THIS FILE DOES
    Draws the control card at the top of the Backtesting page and returns the
    user's choices as a plain dict. It does no maths and runs no backtest.

        What to compare   ( Scenarios )( All risk profiles )( Custom only )
        Risk profile      (RP1)(RP2)(RP3)(RP4)(RP5)        <- if "Scenarios"
        Scenario          (ESAA)(DSAA 2026)(DSAA 2025)     <- if "All profiles"
        [x] Include my custom portfolio
        Period            (1Y)(3Y)(5Y)(10Y)(20Y)(All)(Custom)

WHAT IT RETURNS
    {
      "mode":           "scenarios" | "profiles" | "custom_only",
      "rp":             3,            # used when mode == "scenarios"
      "scenario":       "DSAA 2026",  # used when mode == "profiles"
      "include_custom": True,
      "start":          Timestamp,    # first date of the backtest window
      "end":            Timestamp,
      "period_label":   "Last 10 years",
    }

WHERE TO CHANGE WHAT
    * Add a period preset   -> PERIOD_PRESETS below
    * Default period        -> settings.toml [backtest].default_years
    * Add a comparison mode -> MODES below, then handle the new key in
                               ui/page_backtest.py _build_portfolios()

CALLED BY
    ui/page_backtest.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.config import Config
from ui.widgets import card_title

MODE_SCENARIOS = "scenarios"
MODE_PROFILES = "profiles"
MODE_CUSTOM = "custom_only"

MODES = {
    "Scenarios for one profile": MODE_SCENARIOS,
    "All risk profiles": MODE_PROFILES,
    "Custom portfolio only": MODE_CUSTOM,
}

# label -> number of years back from the end of the data. None means "all".
PERIOD_PRESETS = {
    "1Y": 1, "3Y": 3, "5Y": 5, "10Y": 10, "20Y": 20, "All": None,
}
CUSTOM_PERIOD = "Custom"


def _resolve_period(label: str, first_date, last_date) -> tuple:
    """Turn a preset label into (start, end) timestamps."""
    if label == "All" or label not in PERIOD_PRESETS:
        return first_date, last_date
    years = PERIOD_PRESETS[label]
    if years is None:
        return first_date, last_date
    start = last_date - pd.DateOffset(years=years)
    return max(start, first_date), last_date


def render(cfg: Config, first_date, last_date) -> dict:
    """Draw the controls. `first_date`/`last_date` bound the available history."""
    default_years = int(cfg.backtest.get("default_years", 10))
    default_label = f"{default_years}Y" if f"{default_years}Y" in PERIOD_PRESETS else "All"

    with st.container(border=True):
        card_title("What to compare")

        top = st.columns([2.2, 2.0, 1.6])
        with top[0]:
            mode_label = st.segmented_control(
                "Comparison", list(MODES), default=list(MODES)[0],
                key="bt_mode", label_visibility="collapsed",
            ) or list(MODES)[0]
            mode = MODES[mode_label]

        risk_profile = cfg.rp_ids[len(cfg.rp_ids) // 2]
        scenario = cfg.scenarios[1] if len(cfg.scenarios) > 1 else cfg.scenarios[0]

        with top[1]:
            if mode == MODE_SCENARIOS:
                risk_profile = int(st.segmented_control(
                    "Risk profile", cfg.rp_ids, default=risk_profile,
                    format_func=cfg.rp_short, key="bt_rp",
                    label_visibility="collapsed") or risk_profile)
            elif mode == MODE_PROFILES:
                scenario = st.segmented_control(
                    "Scenario", cfg.scenarios, default=scenario,
                    key="bt_scenario", label_visibility="collapsed") or scenario

        with top[2]:
            include_custom = st.checkbox("Include my custom portfolio",
                                         value=(mode == MODE_CUSTOM),
                                         key="bt_include_custom")

        # ---- period ---------------------------------------------------- #
        card_title("Period", top_margin=".9rem")
        period_columns = st.columns([3.2, 2.4])
        with period_columns[0]:
            period_label = st.segmented_control(
                "Period", list(PERIOD_PRESETS) + [CUSTOM_PERIOD],
                default=default_label, key="bt_period",
                label_visibility="collapsed") or default_label

        if period_label == CUSTOM_PERIOD:
            with period_columns[1]:
                date_columns = st.columns(2)
                with date_columns[0]:
                    start = st.date_input("From", value=first_date,
                                          min_value=first_date, max_value=last_date,
                                          key="bt_start")
                with date_columns[1]:
                    end = st.date_input("To", value=last_date,
                                        min_value=first_date, max_value=last_date,
                                        key="bt_end")
            start, end = pd.Timestamp(start), pd.Timestamp(end)
            if start >= end:
                st.warning("The start date must be before the end date — "
                           "showing the full history instead.")
                start, end = first_date, last_date
            period_text = f"{start:%b %Y} to {end:%b %Y}"
        else:
            start, end = _resolve_period(period_label, first_date, last_date)
            period_text = ("Full history" if period_label == "All"
                           else f"Last {PERIOD_PRESETS[period_label]} years")

    return {
        "mode": mode,
        "rp": risk_profile,
        "scenario": scenario,
        "include_custom": include_custom,
        "start": start,
        "end": end,
        "period_label": period_text,
    }
