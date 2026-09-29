"""
=============================================================================
 SIDEBAR NAVIGATION  —  the dark left-hand nav
=============================================================================

WHAT THIS FILE DOES
    Draws the left navigation and returns which page the user is on.

        ┌──────────────────────┐
        │ CIO.                 │   brand
        │ MODEL PORTFOLIOS     │
        ├──────────────────────┤
        │ ANALYSIS             │   group label
        │   Portfolios         │   <- nav items are Streamlit buttons
        │   Backtesting        │
        │                      │
        │ INPUTS               │   group label
        │   Capital Market     │
        │   Assumptions        │
        ├──────────────────────┤
        │ 10 model portfolios  │   meta
        │ 16 asset classes     │
        │ ↻ Reload data        │
        └──────────────────────┘

    ANALYSIS pages are things people look at; INPUTS pages are the control
    panel - the numbers the analysis is built from. Capital Market Assumptions
    sits under INPUTS for that reason.

HOW THE ACTIVE ITEM IS DRAWN
    Each nav item is an st.button. The active one is rendered with
    type="primary", which Streamlit turns into kind="primary" on the DOM
    node, and ui/css/06_sidebar.css paints that maroon. That is the whole
    trick - there is no custom HTML link anywhere.

    Clicking calls st.rerun() so the highlight moves immediately rather than
    lagging one click behind.

WHERE TO CHANGE WHAT
    * ADD A PAGE       -> add an entry to NAV_GROUPS below, then handle its
                          key in app.py main(). Nothing else needs touching.
    * Reorder / rename -> edit NAV_GROUPS
    * Colours, width   -> ui/css/06_sidebar.css
    * The meta counts  -> _render_meta() below

CALLED BY
    app.py
"""
from __future__ import annotations

import streamlit as st

# The page keys used here are what app.py switches on.
START = "start"
PORTFOLIOS = "portfolios"
BACKTEST = "backtest"
CMA = "cma"

DEFAULT_PAGE = START          # the read-me page is what users land on
SESSION_KEY = "nav_page"
REPORT_KEY = "report_file"    # holds the built .xlsx until it is downloaded

# (group label, [(button label, page key), ...])
NAV_GROUPS = [
    ("Guide", [
        ("Start here", START),
    ]),
    ("Analysis", [
        ("Portfolios", PORTFOLIOS),
        ("Backtesting", BACKTEST),
    ]),
    ("Inputs", [
        ("Capital Market Assumptions", CMA),
    ]),
]


def _render_brand(cfg) -> None:
    """
    The wordmark block. Three lines: "CIO.", the app name, then the subtitle
    from settings.toml [app].subtitle.
    """
    st.markdown(
        f'<div class="nav-brand">'
        f'<span class="mark">CIO<span class="dot">.</span></span>'
        f'<span class="name">Model Portfolios</span>'
        f'<span class="sub">{cfg.app.get("subtitle", "")}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_meta(cfg, data) -> None:
    models = (int(data.portfolios["model_id"].nunique())
              if not data.portfolios.empty else 0)
    currencies = (int(data.portfolios["currency"].nunique())
                  if not data.portfolios.empty else 0)
    st.markdown(
        f'<div class="nav-meta">'
        f"<b>{models}</b> model portfolios<br>"
        f"<b>{len(cfg.asset_codes)}</b> asset classes<br>"
        f"<b>{currencies}</b> currencies"
        f'<span class="hint">CMA edits are per-session only</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_report_button(cfg, data, cma_store) -> None:
    """
    Two-step download: building the workbook re-solves the frontier and runs
    the backtests (a few seconds), so it only happens when the user asks.
    Streamlit's download_button needs its bytes up front, hence the two steps.
    """
    from ui import report_builder          # imported late to keep start-up light

    st.markdown('<div class="nav-group">Report</div>', unsafe_allow_html=True)

    if st.button("⬇  Build full report", key="nav_build_report",
                 use_container_width=True):
        with st.spinner("Building report…"):
            try:
                payload, filename = report_builder.build(cfg, data, cma_store)
                st.session_state[REPORT_KEY] = {"bytes": payload, "name": filename}
            except Exception as exc:                      # noqa: BLE001
                st.session_state[REPORT_KEY] = {"error": str(exc)}
        st.rerun()

    report = st.session_state.get(REPORT_KEY)
    if not report:
        return
    if "error" in report:
        st.caption(f"Report failed: {report['error']}")
        return

    size_kb = len(report["bytes"]) / 1024
    st.download_button(
        f"⬇  Download .xlsx  ({size_kb:,.0f} KB)",
        data=report["bytes"], file_name=report["name"],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="nav_download_report", use_container_width=True,
    )


def render(cfg, data, cma_store, on_reload) -> str:
    """
    Draw the sidebar. Returns the active page key (START / PORTFOLIOS /
    BACKTEST / CMA). `on_reload` is called when the user presses Reload data.
    """
    current = st.session_state.setdefault(SESSION_KEY, DEFAULT_PAGE)

    with st.sidebar:
        _render_brand(cfg)

        for group_label, items in NAV_GROUPS:
            st.markdown(f'<div class="nav-group">{group_label}</div>',
                        unsafe_allow_html=True)
            for button_label, page_key in items:
                is_active = page_key == current
                if st.button(button_label, key=f"nav_{page_key}",
                             use_container_width=True,
                             type="primary" if is_active else "secondary"):
                    st.session_state[SESSION_KEY] = page_key
                    st.rerun()

        _render_report_button(cfg, data, cma_store)
        _render_meta(cfg, data)

        if st.button("↻  Reload data", key="nav_reload",
                     use_container_width=True):
            st.session_state.pop(REPORT_KEY, None)     # stale once data changes
            on_reload()
            st.rerun()

    return st.session_state[SESSION_KEY]
