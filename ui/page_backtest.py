"""
=============================================================================
 PAGE 3 — BACKTESTING
=============================================================================

WHAT THIS FILE DOES
    Wires the Backtesting page together. Like ui/page_portfolios.py it holds
    almost no logic - read it as a table of contents.

    PAGE LAYOUT, TOP TO BOTTOM                       LIVES IN
    ──────────────────────────────────────────────── ──────────────────────
    1. heading + model dropdown                      here
    2. data-quality warnings (missing price history) here
    3. controls: what to compare, over what period   sections/backtest_controls.py
    4. custom portfolio builder                      sections/backtest_custom.py
    5. growth / drawdown / rolling charts + metrics  sections/backtest_results.py

    The backtests themselves are run in _run_portfolios() below, which is the
    only place that calls core/backtest.py.

WHAT GETS BACKTESTED
    Driven by the "What to compare" control:
      "Scenarios for one profile"  ESAA vs DSAA 2026 vs DSAA 2025 for one RP
      "All risk profiles"          RP1..RP5 for one scenario
      "Custom portfolio only"      just the user's own weights
    plus the custom portfolio whenever "Include my custom portfolio" is ticked.

PERFORMANCE
    Loading a 5,000-row price file and running a backtest is fast, but doing
    it on every keystroke would not be. The price history is cached with
    @st.cache_data keyed on the currency, and the backtests re-run only when a
    control or a weight actually changes (Streamlit reruns the script anyway).

WHERE TO CHANGE WHAT
    * Which model is backtested -> the dropdown in render() below
    * Add a comparison mode     -> sections/backtest_controls.py MODES, then
                                   a branch in _build_weight_sets() below
    * Rebalancing / risk-free   -> settings.toml [backtest]
    * The price file schema     -> scripts/generate_history_data.py docstring

CALLED BY
    app.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import backtest as bt
from core.config import Config
from core.history_loader import load_history
from core.taxonomy import model_directory, scenario_matrix
from ui.sections import backtest_controls, backtest_custom, backtest_results
from ui.widgets import section_heading

CUSTOM_NAME = backtest_custom.CUSTOM_NAME


# --------------------------------------------------------------------------- #
# cached price history                                                       #
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Loading price history…")
def _load_prices(_cfg: Config, currency: str, _fingerprint: str):
    """
    Read one currency's daily prices. Cached on the currency; `_fingerprint`
    changes when the file on disk changes, which busts the cache.

    The leading underscore on _cfg tells Streamlit not to try to hash it.
    """
    return load_history(_cfg, currency)


def _history_fingerprint(cfg: Config, currency: str) -> str:
    import os
    from core.history_loader import history_path
    path = history_path(cfg, currency)
    try:
        return f"{os.path.getmtime(path):.0f}"
    except OSError:
        return "missing"


# --------------------------------------------------------------------------- #
# deciding which weight vectors to backtest                                  #
# --------------------------------------------------------------------------- #
def _build_weight_sets(cfg: Config, portfolios: pd.DataFrame, model_id: str,
                       choices: dict) -> dict[str, pd.Series]:
    """
    Turn the user's control choices into {display name: weights in percent}.
    """
    sets: dict[str, pd.Series] = {}
    mode = choices["mode"]

    if mode == backtest_controls.MODE_SCENARIOS:
        matrix = scenario_matrix(portfolios, cfg, model_id, choices["rp"])
        for scenario in cfg.scenarios:
            sets[scenario] = matrix[scenario]

    elif mode == backtest_controls.MODE_PROFILES:
        scenario = choices["scenario"]
        for rp in cfg.rp_ids:
            matrix = scenario_matrix(portfolios, cfg, model_id, rp)
            sets[cfg.rp_short(rp)] = matrix[scenario]

    return sets


def _run_portfolios(cfg: Config, prices: pd.DataFrame,
                    weight_sets: dict[str, pd.Series]) -> tuple[dict, list[str]]:
    """
    Backtest every weight vector over the same price window.
    Returns ({name: index series}, [asset codes dropped for lack of prices]).
    """
    rebalance = cfg.backtest.get("rebalance", "M") or None
    results, dropped_codes = {}, []

    for name, weights in weight_sets.items():
        aligned, dropped = bt.align_weights(weights, prices)
        for code in dropped:
            if code not in dropped_codes:
                dropped_codes.append(code)
        if aligned.empty:
            continue
        series = bt.run(prices, aligned, rebalance=rebalance)
        if not series.empty:
            results[name] = series

    return results, dropped_codes


# --------------------------------------------------------------------------- #
# the page                                                                   #
# --------------------------------------------------------------------------- #
def render(cfg: Config, data, cma_store) -> None:
    portfolios = data.portfolios
    directory = model_directory(portfolios)
    if directory.empty:
        st.error("No model portfolios found in the data file.")
        return

    # --- 1. heading + model dropdown ----------------------------------- #
    section_heading(
        "Backtesting", "Historical performance",
        "Run a model portfolio through real price history. Pick what to "
        "compare and over what period, or build your own portfolio below and "
        "test it alongside.",
    )

    names = dict(zip(directory["model_id"], directory["model_name"]))
    model_ids = directory["model_id"].tolist()
    previous = st.session_state.get("selected_model", model_ids[0])
    model_id = st.selectbox(
        "Model portfolio", model_ids,
        index=model_ids.index(previous) if previous in model_ids else 0,
        format_func=lambda mid: names.get(mid, mid),
        label_visibility="collapsed",
    )
    # share the selection with the Portfolios page
    st.session_state["selected_model"] = model_id

    model_row = directory.set_index("model_id").loc[model_id]
    currency, model_name = model_row["currency"], model_row["model_name"]

    # --- 2. load history and report any problems ------------------------ #
    history = _load_prices(cfg, currency, _history_fingerprint(cfg, currency))

    if not history.ok:
        for message in history.errors:
            st.error(message)
        st.info("The Backtesting page needs daily price history. Generate "
                "sample data with:\n\n"
                "`.venv/Scripts/python.exe scripts/generate_history_data.py`")
        return

    st.markdown(
        f'<div class="mp-meta"><b>{model_name}</b> &nbsp;·&nbsp; priced in '
        f'{currency} &nbsp;·&nbsp; history {history.start:%b %Y} – '
        f'{history.end:%b %Y} ({history.years:.1f} years) &nbsp;·&nbsp; '
        f'rebalanced monthly</div>',
        unsafe_allow_html=True,
    )

    if history.missing_codes:
        st.warning(
            f"No price history for {len(history.missing_codes)} asset "
            f"class(es): **{', '.join(history.missing_codes)}**. They are "
            f"excluded from every backtest below and the remaining weights are "
            f"scaled up to 100%. Add these columns to "
            f"`data/history/prices_{currency}.csv` to include them."
        )
    if history.extra_codes:
        st.caption(f"Ignoring {len(history.extra_codes)} column(s) in the price "
                   f"file that are not asset classes in settings.toml: "
                   f"{', '.join(history.extra_codes[:6])}"
                   f"{' …' if len(history.extra_codes) > 6 else ''}")

    # --- 3. controls ---------------------------------------------------- #
    choices = backtest_controls.render(cfg, history.start, history.end)

    # --- 4. custom portfolio builder ------------------------------------ #
    custom_weights = None
    if choices["include_custom"]:
        seed_rp = choices["rp"]
        seed_scenario = (choices["scenario"]
                         if choices["mode"] == backtest_controls.MODE_PROFILES
                         else cfg.scenario_change[0])
        seed_matrix = scenario_matrix(portfolios, cfg, model_id, seed_rp)
        seed_label = f"{cfg.rp_short(seed_rp)} {seed_scenario}"
        custom_weights = backtest_custom.render(
            cfg, seed_matrix[seed_scenario], seed_label)

    # --- run the backtests ---------------------------------------------- #
    prices = bt.slice_period(history.prices, choices["start"], choices["end"])
    if len(prices) < 30:
        st.warning("That period contains too little price history to backtest. "
                   "Choose a longer window.")
        return

    weight_sets = _build_weight_sets(cfg, portfolios, model_id, choices)
    if custom_weights is not None and custom_weights.abs().sum() > 0:
        weight_sets[CUSTOM_NAME] = custom_weights

    if not weight_sets:
        st.info("Nothing selected. Tick **Include my custom portfolio**, or "
                "choose a different comparison.")
        return

    results, dropped = _run_portfolios(cfg, prices, weight_sets)

    if dropped:
        st.caption(f"Excluded for lack of price history: {', '.join(dropped)}")

    # tracking error is measured against the benchmark scenario when it is
    # one of the things being plotted
    benchmark_name = (cfg.scenario_benchmark
                      if cfg.scenario_benchmark in results else None)

    # --- 5. charts + metrics -------------------------------------------- #
    backtest_results.render(cfg, results, benchmark_name,
                            choices["period_label"])
