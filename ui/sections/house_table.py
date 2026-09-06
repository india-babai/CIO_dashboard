"""
=============================================================================
 SECTION 1 — THE HOUSE TABLE  (the big RP1-RP5 table on the landing page)
=============================================================================

WHAT THIS FILE DOES
    Builds the main table as raw HTML and puts it on the page.

    WHY HAND-WRITTEN HTML AND NOT st.dataframe?
    Streamlit draws dataframes onto an HTML <canvas>. You cannot give a canvas
    alternating row colours, black section rules, merged "RP1"/"RP2" header
    bars or a white gutter column. A plain <table> can do all of that, and it
    still copy-pastes cleanly into Excel. The cost is that this file writes
    HTML by hand; the styling for it is in ui/css/05_house_table.css.

    WHAT THE TABLE LOOKS LIKE
        ┌────────────┬──────── RP1 ────────┬ ┬──────── RP2 ────────┬ ...
        │ Asset Class│ ESAA │ DSAA 2026 │…│ │ ESAA │ DSAA 2026 │…│
        ├────────────┼──────┼───────────┼─┼─┼──────┼───────────┼─┼
        │ EME        │ 2.64 │      4.72 │ │ │ 6.42 │      8.16 │ │  16 rows
        │ …                                                          (granular)
        ├──────────── black rule ─────────────────────────────────────
        │ Equity     │12.18 │     15.51 │ │ │28.34 │     31.53 │ │   6 rows
        │ …                                                        (sub-group)
        ├──────────── black rule ─────────────────────────────────────
        │ Equity     │ …                                             4 rows
        │ …                                                            (group)
        ├──────────── black rule ─────────────────────────────────────
        │ RISK-RETURN METRICS                                        label row
        │ Exp Ret    │ 4.36 │      4.62 │ │ │ 4.76 │      5.02 │ │   4 rows
        │ …                                                          (metrics)

    The "┬ ┬" columns are deliberate empty white gutter cells that separate
    the RP groups all the way down the table.

WHERE TO CHANGE WHAT
    * The NUMBERS in any block   -> core/report_tables.py
    * Row order / which rows      -> settings.toml ([[asset_classes]], etc.)
    * Colours, spacing, fonts     -> ui/css/05_house_table.css
    * Which columns are visible   -> ui/page_portfolios.py (the checkbox)
    * The HTML structure itself   -> build_html() below

CALLED BY
    ui/page_portfolios.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from core.config import Config
from core.report_tables import (METRIC_ROWS, granular_block, group_block,
                                metrics_block, subgroup_block)

LABEL_COLUMN_HEADER = "Asset Class"
METRICS_LABEL_ROW = "Risk-Return Metrics"


# --------------------------------------------------------------------------- #
# public entry point                                                         #
# --------------------------------------------------------------------------- #
def render(cfg: Config, weights_by_rp: dict[int, pd.DataFrame],
           cma: pd.DataFrame, corr: pd.DataFrame,
           visible_columns: list[str]) -> None:
    """Draw the table. `visible_columns` is e.g. ['ESAA', 'DSAA 2026']."""
    st.markdown(build_html(cfg, weights_by_rp, cma, corr, visible_columns),
                unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# small helpers                                                              #
# --------------------------------------------------------------------------- #
def _format_number(value) -> str:
    """2 decimal places, or an empty cell for missing values."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return f"{value:,.2f}"


class _Zebra:
    """Hands out r-even / r-odd in turn so body rows alternate shading."""

    def __init__(self) -> None:
        self._count = 0

    def next_class(self) -> str:
        css_class = "r-odd" if self._count % 2 else "r-even"
        self._count += 1
        return css_class


def _prepare_blocks(cfg: Config, weights_by_rp: dict[int, pd.DataFrame],
                    cma: pd.DataFrame, corr: pd.DataFrame) -> dict:
    """
    Pre-compute the four numeric blocks for every risk profile:

        {1: {"granular": df, "subgroup": df, "group": df, "metrics": df}, 2: ...}

    Each df is indexed by its row label and has every scenario + "Change",
    so a cell is simply  blocks[rp][block_name].loc[row_label, column].
    """
    return {
        rp: {
            "granular": granular_block(cfg, weights),
            "subgroup": subgroup_block(cfg, weights),
            "group": group_block(cfg, weights),
            "metrics": metrics_block(cfg, weights, cma, corr),
        }
        for rp, weights in weights_by_rp.items()
    }


# --------------------------------------------------------------------------- #
# HTML pieces                                                                #
# --------------------------------------------------------------------------- #
def _header_html(cfg: Config, visible_columns: list[str]) -> str:
    """
    Two header rows:
      row 1 — "Asset Class" (spanning both rows), then a maroon RP bar per
              risk profile, with a gutter cell between them
      row 2 — the scenario names under each RP bar
    """
    parts = ["<thead><tr>",
             f'<th class="lbl" rowspan="2">{LABEL_COLUMN_HEADER}</th>']
    for index, rp in enumerate(cfg.rp_ids):
        if index:                                   # gutter before every RP but the first
            parts.append('<th class="gut" rowspan="2"></th>')
        parts.append(f'<th class="rpgrp" colspan="{len(visible_columns)}">'
                     f'{cfg.rp_short(rp)}</th>')
    parts.append("</tr><tr>")
    for _rp in cfg.rp_ids:
        for column in visible_columns:
            parts.append(f"<th>{column}</th>")
    parts.append("</tr></thead>")
    return "".join(parts)


def _row_html(cfg: Config, blocks: dict, block_name: str, row_label: str,
              css_class: str, indent: bool, zebra: _Zebra,
              visible_columns: list[str]) -> str:
    """One body row: the label cell, then each RP's cells separated by gutters."""
    label_classes = "lbl ind" if indent else "lbl"
    cells = [f'<td class="{label_classes}">{row_label}</td>']

    for index, rp in enumerate(cfg.rp_ids):
        if index:
            cells.append('<td class="gut"></td>')
        block = blocks[rp][block_name]
        for column in visible_columns:
            value = block.loc[row_label, column]
            # colour the Change column: maroon when >= 0, grey when < 0
            cell_class = ""
            if column == "Change" and not (isinstance(value, float) and np.isnan(value)):
                cell_class = "chg-pos" if value >= 0 else "chg-neg"
            cells.append(f'<td class="{cell_class}">{_format_number(value)}</td>')

    return f'<tr class="{css_class} {zebra.next_class()}">' + "".join(cells) + "</tr>"


def _separator_html(total_columns: int) -> str:
    """The blank row + black rule that divides one section from the next."""
    return f'<tr class="sep"><td colspan="{total_columns}"></td></tr>'


def _metrics_label_html(total_columns: int) -> str:
    """The 'RISK-RETURN METRICS' caption row."""
    return (f'<tr class="mhead"><td colspan="{total_columns}">'
            f"{METRICS_LABEL_ROW}</td></tr>")


# --------------------------------------------------------------------------- #
# assemble                                                                   #
# --------------------------------------------------------------------------- #
def build_html(cfg: Config, weights_by_rp: dict[int, pd.DataFrame],
               cma: pd.DataFrame, corr: pd.DataFrame,
               visible_columns: list[str]) -> str:
    """Return the complete <table> markup. Pure string building — no Streamlit."""
    blocks = _prepare_blocks(cfg, weights_by_rp, cma, corr)
    risk_profiles = cfg.rp_ids

    # 1 label column + (visible columns x RPs) + one gutter between RP groups
    total_columns = (1
                     + len(risk_profiles) * len(visible_columns)
                     + max(len(risk_profiles) - 1, 0))

    # "spaced" = the default 2-column view (bigger type, wider gaps);
    # "dense"  = when DSAA 2025 + Change are also shown.
    size_class = "spaced" if len(visible_columns) <= 2 else "dense"

    html = [f'<div class="house-wrap"><table class="house {size_class}">',
            _header_html(cfg, visible_columns),
            "<tbody>"]

    zebra = _Zebra()

    def add_rows(block_name: str, row_labels, css_class: str, indent: bool) -> None:
        for label in row_labels:
            html.append(_row_html(cfg, blocks, block_name, label,
                                  css_class, indent, zebra, visible_columns))

    # --- the four sections, separated by black rules ---------------------
    add_rows("granular", cfg.asset_codes, "data", indent=False)
    html.append(_separator_html(total_columns))

    add_rows("subgroup", cfg.subgroups, "sub", indent=True)
    html.append(_separator_html(total_columns))

    add_rows("group", cfg.groups, "grp", indent=True)
    html.append(_separator_html(total_columns))

    html.append(_metrics_label_html(total_columns))
    add_rows("metrics", METRIC_ROWS, "met", indent=True)

    html.append("</tbody></table></div>")
    return "".join(html)
