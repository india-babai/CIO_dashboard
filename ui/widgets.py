"""
=============================================================================
 WIDGETS  —  tiny shared UI helpers
=============================================================================

WHAT THIS FILE DOES
    Four small helpers that several pages/sections use, so the wording and
    styling stay consistent. Nothing clever lives here.

        section_heading()  the maroon kicker + serif title + grey lede
        card_title()       the small uppercase title inside a card
        number_columns()   number formatting for st.dataframe / st.data_editor
        horizontal_rule()  the thin divider between page sections

WHERE TO CHANGE WHAT
    * How headings LOOK   -> ui/css/03_layout_and_headings.css
    * How headings are BUILT (the HTML) -> here

USED BY
    ui/page_portfolios.py, ui/page_cma.py and everything in ui/sections/.
"""
from __future__ import annotations

import streamlit as st


def section_heading(kicker: str, title: str, lede: str = "") -> None:
    """
    The standard section header used across the app, e.g.

        OPTIMISATION                       <- kicker (small, maroon, uppercase)
        This model vs the efficient frontier   <- title (serif)
        Long-only, fully-invested ...          <- lede  (grey explanation)
    """
    html = f'<div class="cio-kicker">{kicker}</div><div class="cio-h">{title}</div>'
    if lede:
        html += f'<div class="cio-lede">{lede}</div>'
    st.markdown(html, unsafe_allow_html=True)


def card_title(text: str, top_margin: str | None = None) -> None:
    """Small uppercase grey title, used above a chart or table inside a card."""
    style = f' style="margin-top:{top_margin}"' if top_margin else ""
    st.markdown(f'<div class="cio-card-title"{style}>{text}</div>',
                unsafe_allow_html=True)


def number_columns(columns, decimals: int = 2, width: str | None = None) -> dict:
    """
    Build the `column_config` dict that formats a set of numeric columns.

        st.dataframe(df, column_config=number_columns(["Risk %", "Return %"]))

    width : None (auto) or "small" / "medium" / "large" to keep a table compact.
    """
    extra = {"width": width} if width else {}
    return {c: st.column_config.NumberColumn(c, format=f"%.{decimals}f", **extra)
            for c in columns}


def horizontal_rule() -> None:
    """Thin divider between the major sections of a page."""
    st.markdown("<hr/>", unsafe_allow_html=True)
