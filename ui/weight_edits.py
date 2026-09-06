"""
=============================================================================
 WEIGHT EDITS  —  the session-only copy of a model's weights
=============================================================================

WHAT THIS FILE DOES
    Holds the weights the user is currently looking at, per model, in
    st.session_state. Starts as an exact copy of what was read from
    data/model_portfolios.xlsx; the What-if editor mutates that copy.

    Nothing here is ever written to disk. Close the browser tab and the edits
    are gone — the next session starts from the file again. That is deliberate
    (see HOW_TO_NAVIGATE.md, "Why nothing is saved").

    ---------------------------------------------------------------------
    THE SHAPE OF THE DATA
    ---------------------------------------------------------------------
    st.session_state["model_weights"] = {
        "eur_emea": {                       <- model_id
            1: <DataFrame>,                 <- risk profile 1
            2: <DataFrame>, ... 5: ...
        },
        "usd_apac": { ... },
    }

    Each DataFrame:  index = asset code, one column per scenario, values in %

                 ESAA   DSAA 2026   DSAA 2025
        code
        EME       2.64       4.72        1.70
        DME       9.54      10.79        7.74

    ---------------------------------------------------------------------
    *** THE ONE SUBTLE THING IN THIS APP — READ THIS ***
    ---------------------------------------------------------------------
    st.data_editor does NOT hand you the edited table before it is drawn. It
    stores the user's pending changes in st.session_state under the widget's
    key, shaped like:

        {"edited_rows": {3: {"DSAA 2026": 12.5}}, "added_rows": [], ...}
                         ^ row NUMBER (0-based), not the asset code

    The house table is drawn ABOVE the editor on the page, so by the time
    Streamlit reaches the editor it is too late to update the table. The fix
    is fold_in_pending_edits(): before drawing anything, we read that raw
    widget state ourselves and apply it to our own copy of the weights. That
    is why the table, the charts and the frontier all update the moment you
    type a number.

    Row number -> asset code works because the editor is always built from
    cfg.asset_codes in the same order. If you ever sort or filter the rows in
    the editor, this mapping breaks — sort a *copy* for display only.

WHERE TO CHANGE WHAT
    * Reset behaviour           -> reset_model()
    * Which model is selected   -> ui/page_portfolios.py
    * The editor widget itself  -> ui/sections/whatif_editor.py

USED BY
    ui/page_portfolios.py and ui/sections/whatif_editor.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.config import Config
from core.taxonomy import scenario_matrix

# key under which every model's working weights live in st.session_state
SESSION_KEY = "model_weights"


def editor_widget_key(model_id: str, rp: int) -> str:
    """
    The st.session_state key Streamlit uses for one risk profile's data editor.
    Must be identical in fold_in_pending_edits() and in the widget itself.
    """
    return f"weight_editor::{model_id}::{rp}"


# --------------------------------------------------------------------------- #
# create / read                                                              #
# --------------------------------------------------------------------------- #
def get_or_create(cfg: Config, portfolios: pd.DataFrame,
                  model_id: str) -> dict[int, pd.DataFrame]:
    """
    Return {risk_profile: weights DataFrame} for this model, seeding it from
    the loaded file the first time the model is opened in this session.
    """
    all_models = st.session_state.setdefault(SESSION_KEY, {})
    if model_id not in all_models:
        all_models[model_id] = {
            rp: scenario_matrix(portfolios, cfg, model_id, rp).astype(float)
            for rp in cfg.rp_ids
        }
    return all_models[model_id]


# --------------------------------------------------------------------------- #
# apply the user's typing                                                    #
# --------------------------------------------------------------------------- #
def fold_in_pending_edits(cfg: Config, model_id: str) -> None:
    """
    Copy any not-yet-applied data-editor changes into our weights, so that
    everything drawn afterwards (house table, charts, frontier) is current.

    Call this ONCE per page load, before drawing anything. See the long note
    at the top of this file for why it is necessary.
    """
    weights_by_rp = st.session_state[SESSION_KEY][model_id]

    for rp in cfg.rp_ids:
        widget_state = st.session_state.get(editor_widget_key(model_id, rp))
        if not (isinstance(widget_state, dict) and widget_state.get("edited_rows")):
            continue

        weights = weights_by_rp[rp]
        for row_number, changed_cells in widget_state["edited_rows"].items():
            try:
                code = cfg.asset_codes[int(row_number)]
            except (ValueError, IndexError):
                continue                      # row no longer exists — ignore
            for column, value in changed_cells.items():
                if column in cfg.scenarios and value is not None:
                    weights.loc[code, column] = float(value)
        weights_by_rp[rp] = weights


def write_back(cfg: Config, model_id: str, rp: int,
               edited: pd.DataFrame, columns: list[str]) -> None:
    """
    Store what st.data_editor returned. Only `columns` are touched, so hidden
    scenarios (e.g. DSAA 2025 when the checkbox is off) keep their values.
    """
    cleaned = (edited.set_index("code")[columns]
               .apply(pd.to_numeric, errors="coerce")
               .fillna(0.0)
               .reindex(cfg.asset_codes)
               .fillna(0.0))
    weights = st.session_state[SESSION_KEY][model_id][rp]
    for column in columns:
        weights[column] = cleaned[column]


# --------------------------------------------------------------------------- #
# reset                                                                      #
# --------------------------------------------------------------------------- #
def reset_model(cfg: Config, model_id: str) -> None:
    """
    Throw away this model's edits. Removes both our copy of the weights and
    the data editors' own pending state, so the next run reseeds from file.
    """
    st.session_state.get(SESSION_KEY, {}).pop(model_id, None)
    for rp in cfg.rp_ids:
        st.session_state.pop(editor_widget_key(model_id, rp), None)


def scenario_totals(weights: pd.DataFrame) -> pd.Series:
    """Column sums — used to warn when a scenario no longer adds up to 100."""
    return weights.sum()
