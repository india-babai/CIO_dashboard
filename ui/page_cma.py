"""
=============================================================================
 PAGE 2 — CAPITAL MARKET ASSUMPTIONS
=============================================================================

WHAT THIS FILE DOES
    Shows the numbers every risk/return figure in the app is built from, and
    lets a user try different ones.

    THREE TABS
      Assumptions        expected return + volatility per asset class, editable
      Correlation matrix the full matrix as a heatmap (read-only in this version)
      Change log         what this session has edited

    EDITS ARE SESSION-ONLY. Nothing is written to disk, nobody else sees them,
    and a new session starts from data/cma/*.csv again. The mechanism is in
    core/cma_store.py.

WHERE TO CHANGE WHAT
    * Which fields are editable   -> core/cma_store.py EDITABLE_FIELDS
    * Min / max allowed values    -> the NumberColumn definitions below
    * Make correlations editable  -> would need a new editor here plus a
                                     matrix-aware override in core/cma_store.py
    * Heatmap colours             -> ui/charts.py correlation_heatmap()

CALLED BY
    app.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.cma_store import current_user
from core.config import Config
from ui.charts import correlation_heatmap
from ui.theme import PLOTLY_CONFIG
from ui.widgets import section_heading

EDITABLE_FIELDS = ("expected_return", "volatility")


def _unchanged(a, b, tolerance: float = 1e-6) -> bool:
    """True when two cell values are effectively the same number."""
    try:
        return abs(float(a) - float(b)) < tolerance
    except (TypeError, ValueError):
        return True


# --------------------------------------------------------------------------- #
# tab 1 — the editable assumptions grid                                      #
# --------------------------------------------------------------------------- #
def _assumptions_tab(cfg: Config, data, store, currency: str) -> None:
    imported = data.cma[currency].set_index("code")
    effective = store.effective(currency).set_index("code")
    overrides = store.overrides.get(currency, {})

    grid = effective.reset_index()[["code", "expected_return", "volatility"]].copy()
    grid["name"] = grid["code"].map(cfg.asset_name).fillna("")
    grid["group"] = grid["code"].map(cfg.group_of).fillna("Unmapped")
    grid["base ER"] = grid["code"].map(imported["expected_return"])
    grid["base Vol"] = grid["code"].map(imported["volatility"])
    grid["modified"] = grid["code"].apply(lambda code: bool(overrides.get(code)))
    grid = grid[["code", "name", "group", "expected_return", "volatility",
                 "base ER", "base Vol", "modified"]]

    st.caption(
        f"Editing **{currency}** for this session only. Change *Expected "
        "return %* or *Volatility %* in the grid, then **Apply**. Set a value "
        "back to its base to clear it. Nothing is saved to disk."
    )

    edited = st.data_editor(
        grid, hide_index=True, use_container_width=True,
        key=f"cma_editor_{currency}",
        height=min(56 + 35 * len(grid), 900),
        disabled=["code", "name", "group", "base ER", "base Vol", "modified"],
        column_config={
            "code": st.column_config.TextColumn("Code", width="small"),
            "name": st.column_config.TextColumn("Asset class", width="medium"),
            "group": st.column_config.TextColumn("Group", width="small"),
            "expected_return": st.column_config.NumberColumn(
                "Expected return %", format="%.2f", step=0.05,
                min_value=-10.0, max_value=40.0),
            "volatility": st.column_config.NumberColumn(
                "Volatility %", format="%.2f", step=0.05,
                min_value=0.0, max_value=60.0),
            "base ER": st.column_config.NumberColumn("Base ER %", format="%.2f"),
            "base Vol": st.column_config.NumberColumn("Base Vol %", format="%.2f"),
            "modified": st.column_config.CheckboxColumn("Overridden"),
        },
    )

    # work out what the user has changed but not yet applied
    pending = []
    for _, row in edited.iterrows():
        code = row["code"]
        for field in EDITABLE_FIELDS:
            if not _unchanged(row[field], effective.loc[code, field]):
                pending.append((code, field, float(row[field]),
                                float(effective.loc[code, field])))

    buttons = st.columns([1.2, 1.4, 1.6, 3])
    with buttons[0]:
        apply_clicked = st.button(f"Apply ({len(pending)})", type="primary",
                                  disabled=not pending, use_container_width=True)
    with buttons[1]:
        reset_currency = st.button(f"Reset {currency} to base",
                                   disabled=not store.is_modified(currency),
                                   use_container_width=True)
    with buttons[2]:
        reset_everything = st.button("Reset ALL currencies",
                                     disabled=not store.is_modified(),
                                     use_container_width=True)

    if pending:
        st.markdown("**Pending edits**")
        st.dataframe(pd.DataFrame(pending,
                                  columns=["Code", "Field", "New", "Current"]),
                     hide_index=True, use_container_width=True)

    if apply_clicked and pending:
        user = current_user()
        applied = sum(store.set_value(currency, code, field, value, user)
                      for code, field, value, _old in pending)
        st.success(f"Applied {applied} change(s) to {currency} for this session.")
        st.rerun()
    if reset_currency:
        st.success(f"Reset {store.reset(currency)} session edit(s) for {currency}.")
        st.rerun()
    if reset_everything:
        st.success(f"Reset {store.reset(None)} session edit(s) across all currencies.")
        st.rerun()


# --------------------------------------------------------------------------- #
# tab 2 — correlation matrix                                                 #
# --------------------------------------------------------------------------- #
def _correlation_tab(cfg: Config, data, currency: str) -> None:
    matrix = data.corr.get(currency)
    if matrix is None or matrix.empty:
        st.info(f"No correlation matrix found for {currency}.")
        return

    # show the asset classes in settings.toml order, then anything unexpected
    ordered = ([c for c in cfg.asset_codes if c in matrix.index]
               + [c for c in matrix.index if c not in cfg.asset_codes])
    matrix = matrix.loc[ordered, ordered]

    st.caption(
        f"Correlation matrix for **{currency}** (as imported). Used in full for "
        "the portfolio volatility calculation √(wᵀΣw). Not editable in this version."
    )
    st.plotly_chart(correlation_heatmap(matrix), config=PLOTLY_CONFIG,
                    use_container_width=True)


# --------------------------------------------------------------------------- #
# tab 3 — change log                                                         #
# --------------------------------------------------------------------------- #
def _change_log_tab(store) -> None:
    audit = store.audit_df()
    if audit.empty:
        st.info("No CMA edits recorded yet. Edits made on the Assumptions tab "
                "appear here.")
        return

    newest_first = audit.iloc[::-1].reset_index(drop=True)
    newest_first["timestamp"] = newest_first["timestamp"].str.replace("T", "  ",
                                                                     regex=False)
    st.dataframe(
        newest_first, hide_index=True, use_container_width=True,
        column_config={
            "timestamp": st.column_config.TextColumn("When", width="medium"),
            "user": st.column_config.TextColumn("User", width="small"),
            "currency": st.column_config.TextColumn("Ccy", width="small"),
            "old_value": st.column_config.NumberColumn("Old", format="%.4g"),
            "new_value": st.column_config.NumberColumn("New", format="%.4g"),
        },
    )
    st.download_button("Download this session's change log (CSV)",
                       audit.to_csv(index=False).encode("utf-8"),
                       file_name="cma_change_log.csv", mime="text/csv")


# --------------------------------------------------------------------------- #
# the page                                                                   #
# --------------------------------------------------------------------------- #
def render(cfg: Config, data, store) -> None:
    section_heading(
        "Inputs", "Capital market assumptions",
        "Expected return, volatility and the full correlation matrix behind "
        "every risk/return figure on the Portfolios page. Expected return and "
        "volatility are editable for your own exploration — edits apply to this "
        "browser session only, are never saved, and don't affect anyone else. "
        "A new session always starts from the imported CMA.",
    )

    currencies = [c for c in cfg.currencies if c in data.cma] or cfg.currencies
    top = st.columns([1.4, 2.6])
    with top[0]:
        currency = st.segmented_control("Currency", currencies,
                                        default=currencies[0]) or currencies[0]
    with top[1]:
        edit_count = store.change_count(currency)
        message = (f"{edit_count} session edit(s) active for {currency}."
                   if edit_count else f"{currency} matches the imported CMA.")
        st.markdown(
            f'<div style="color:#7A6E71;font-size:.85rem;padding-top:.55rem;">'
            f"{message}</div>", unsafe_allow_html=True)

    assumptions, correlations, change_log = st.tabs(
        ["Assumptions", "Correlation matrix", "Change log"])

    with assumptions:
        _assumptions_tab(cfg, data, store, currency)
    with correlations:
        _correlation_tab(cfg, data, currency)
    with change_log:
        _change_log_tab(store)
