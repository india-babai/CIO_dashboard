"""
=============================================================================
 PAGE 1 — PORTFOLIOS  (the landing page)
=============================================================================

WHAT THIS FILE DOES
    Wires the Portfolios page together. It deliberately contains almost no
    logic — read it as a table of contents and jump to the section file you
    care about.

    PAGE LAYOUT, TOP TO BOTTOM                          LIVES IN
    ─────────────────────────────────────────────────── ──────────────────────
    1. heading                                          ui/widgets.py
    2. the ONE model dropdown                           here
    3. summary line + "show more columns" + reset       here
    4. the RP1-RP5 house table                          ui/sections/house_table.py
    5. Excel download button                            core/excel_export.py
    6. What-if editor + live metrics + tilt chart       ui/sections/whatif_editor.py
    7. Charts (donut + contribution)                    ui/sections/charts_section.py
    8. Efficient frontier                               ui/sections/frontier_section.py

WHERE TO CHANGE WHAT
    * Add a whole new section  -> write ui/sections/<name>.py, then add one
                                  `<name>.render(...)` line at the bottom here
    * Reorder sections         -> move those lines around
    * The model dropdown       -> _choose_model() below
    * Which columns show       -> the checkbox in _model_summary_bar() below

CALLED BY
    app.py
"""
from __future__ import annotations

import streamlit as st

from core.config import Config
from core.excel_export import workbook_bytes
from core.report_tables import CHANGE_COL
from core.taxonomy import model_directory
from ui import weight_edits
from ui.sections import charts_section, frontier_section, house_table, whatif_editor
from ui.widgets import section_heading

EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# --------------------------------------------------------------------------- #
# step 2 — the one and only model picker                                     #
# --------------------------------------------------------------------------- #
def _choose_model(directory) -> str:
    """
    Render the model dropdown and return the chosen model_id.
    The previous choice is remembered in st.session_state so the page does not
    jump back to the first model on every rerun.
    """
    names = dict(zip(directory["model_id"], directory["model_name"]))
    model_ids = directory["model_id"].tolist()

    previous = st.session_state.get("selected_model", model_ids[0])
    start_index = model_ids.index(previous) if previous in model_ids else 0

    model_id = st.selectbox(
        "Model portfolio", model_ids, index=start_index,
        format_func=lambda mid: names.get(mid, mid),
        label_visibility="collapsed",
    )
    st.session_state["selected_model"] = model_id
    return model_id


# --------------------------------------------------------------------------- #
# step 3 — summary line, column toggle, reset button                         #
# --------------------------------------------------------------------------- #
def _model_summary_bar(cfg: Config, model_name: str, currency: str,
                       model_id: str) -> bool:
    """
    Draw the grey summary line, the "Show DSAA 2025 & Change" checkbox and the
    "Reset edits" button. Returns True when the extra columns should show.
    """
    newer, older = cfg.scenario_change
    left, middle, right = st.columns([2.6, 1.5, 1])

    with left:
        st.markdown(
            f'<div class="mp-meta"><b>{model_name}</b> &nbsp;·&nbsp; valued in '
            f'{currency} &nbsp;·&nbsp; scenarios: {" / ".join(cfg.scenarios)} '
            f'&nbsp;·&nbsp; {CHANGE_COL} = {newer} − {older} &nbsp;·&nbsp; '
            f'Tracking Error vs {cfg.scenario_benchmark}</div>',
            unsafe_allow_html=True,
        )
    with middle:
        show_all = st.checkbox(f"Show {older} & {CHANGE_COL}", value=False,
                               key="show_all_scenario_columns")
    with right:
        if st.button("↺  Reset edits", use_container_width=True):
            weight_edits.reset_model(cfg, model_id)
            st.rerun()

    return show_all


# --------------------------------------------------------------------------- #
# the page                                                                   #
# --------------------------------------------------------------------------- #
def render(cfg: Config, data, cma_store) -> None:
    """
    cfg       : core.config.Config          — settings.toml
    data      : core.data_loader.LoadResult — everything read from data/
    cma_store : core.cma_store.CmaStore     — this session's CMA edits
    """
    portfolios = data.portfolios
    directory = model_directory(portfolios)
    if directory.empty:
        st.error("No model portfolios found in the data file.")
        return

    # --- 1. heading --------------------------------------------------- #
    section_heading(
        "Model portfolio", "Strategic & dynamic asset allocation",
        "Select a model portfolio. RP1-RP5 are shown together in the house "
        "format; use “What-if” below to edit individual weights and watch the "
        "sub-group, group and risk-return rows recalculate.",
    )

    # --- 2. model dropdown --------------------------------------------- #
    model_id = _choose_model(directory)
    model_row = directory.set_index("model_id").loc[model_id]
    currency, model_name = model_row["currency"], model_row["model_name"]

    if currency not in data.cma:
        st.error(f"No CMA available for currency '{currency}' "
                 f"(model {model_name}). Add data/cma/cma_{currency}.csv.")
        return

    # the CMA this model is valued on, including any edits made this session
    cma = cma_store.effective(currency)
    corr = data.corr.get(currency)

    # --- 3. summary bar ------------------------------------------------ #
    show_all = _model_summary_bar(cfg, model_name, currency, model_id)

    # --- prepare the working weights ----------------------------------- #
    # Seed from file (first visit), then fold in anything the user has just
    # typed into the What-if editor further down the page. Both must happen
    # BEFORE the table is drawn — see ui/weight_edits.py for why.
    weight_edits.get_or_create(cfg, portfolios, model_id)
    weight_edits.fold_in_pending_edits(cfg, model_id)
    weights_by_rp = st.session_state[weight_edits.SESSION_KEY][model_id]

    # --- 4. the house table -------------------------------------------- #
    visible_columns = (list(cfg.scenarios) + [CHANGE_COL] if show_all
                       else list(cfg.scenarios[:2]))
    house_table.render(cfg, weights_by_rp, cma, corr, visible_columns)

    # --- 5. Excel download --------------------------------------------- #
    download_column, _ = st.columns([2, 3])
    with download_column:
        st.download_button(
            "⬇  Download (Excel — one sheet per RP)",
            data=workbook_bytes(cfg, weights_by_rp, cma, corr),
            file_name=f"{model_id}.xlsx",
            mime=EXCEL_MIME,
            use_container_width=True,
        )

    # --- 6. what-if editor --------------------------------------------- #
    with st.container(border=True):
        whatif_editor.render(cfg, model_id, show_all, cma, corr)

    # --- 7. charts ------------------------------------------------------ #
    charts_section.render(cfg, model_name, currency, cma, corr, weights_by_rp)

    # --- 8. efficient frontier ------------------------------------------ #
    frontier_section.render(cfg, model_name, currency, cma, corr, weights_by_rp)
