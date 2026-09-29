"""
=============================================================================
 CIO MODEL PORTFOLIO DASHBOARD  —  START HERE
=============================================================================

    Run with:   .venv/Scripts/python.exe -m streamlit run app.py

WHAT THIS FILE DOES
    The entry point, and nothing more. It:
        1. sets the browser tab title and page width
        2. injects the stylesheet            -> ui/styling.py
        3. loads settings.toml + data/       -> core/config.py, core/data_loader.py
        4. draws the left-hand navigation    -> ui/sidebar_nav.py
        5. hands over to one of the three pages

    All the real work is in the page files:
        ui/page_portfolios.py    the model portfolio landing page
        ui/page_backtest.py      historical backtesting
        ui/page_cma.py           capital market assumptions (the inputs)

    ==> New to this codebase? Read HOW_TO_NAVIGATE.md first.

WHERE TO CHANGE WHAT
    * Browser tab title / icon -> settings.toml [app].title
    * The navigation itself    -> ui/sidebar_nav.py  NAV_GROUPS
    * Add a FOURTH page        -> add it to NAV_GROUPS in ui/sidebar_nav.py,
                                  write ui/page_<name>.py, then add one branch
                                  to the if/elif in main() below
    * The footer text          -> _render_footer() below
"""
from __future__ import annotations

import os

import streamlit as st

from core.cma_store import CmaStore
from core.config import load_config
from core.data_loader import load_all
from ui import page_backtest, page_cma, page_portfolios, sidebar_nav
from ui.styling import inject_css

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# set_page_config must be the first Streamlit call, so the config is read here
# rather than inside main(). Change the title in settings.toml [app].title.
_CONFIG = load_config()

st.set_page_config(
    page_title=_CONFIG.app.get("title", "CIO Model Portfolios"),
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",     # the sidebar IS the navigation
)


# --------------------------------------------------------------------------- #
# loading data (cached)                                                      #
# --------------------------------------------------------------------------- #
def _data_fingerprint(cfg) -> str:
    """
    A short string that changes whenever a file in data/ is modified.

    It is passed into _load_data() purely as a cache key: when you edit
    model_portfolios.xlsx or a CMA csv, the fingerprint changes, so Streamlit
    throws away the cached data and re-reads the files. The "Reload data"
    button in the sidebar forces the same thing manually.

    The price-history files are NOT included here - they are large and only
    the Backtesting page needs them, so they have their own cache in
    ui/page_backtest.py.
    """
    paths = [cfg.path("model_portfolios")]
    cma_dir = cfg.path("cma_dir")
    if os.path.isdir(cma_dir):
        paths += [os.path.join(cma_dir, name) for name in sorted(os.listdir(cma_dir))]

    stamps = []
    for path in paths:
        try:
            stamps.append(f"{os.path.basename(path)}:{os.path.getmtime(path):.0f}")
        except OSError:
            stamps.append(f"{os.path.basename(path)}:missing")
    return "|".join(stamps)


@st.cache_data(show_spinner="Loading model portfolios…")
def _load_data(_fingerprint: str):
    """Read and validate everything in data/. Cached until the files change."""
    return load_all(load_config())


def _clear_caches() -> None:
    """Called by the sidebar's Reload button."""
    _load_data.clear()
    st.cache_data.clear()          # also drops the cached price history


# --------------------------------------------------------------------------- #
# chrome                                                                     #
# --------------------------------------------------------------------------- #
def _render_session_banner(store) -> None:
    """Amber strip shown while this session has unsaved CMA edits."""
    message = store.banner_text()
    if message:
        st.markdown(
            f'<div class="cio-banner"><span class="badge">edited</span>{message}</div>',
            unsafe_allow_html=True,
        )


def _render_data_warnings(data) -> None:
    """Collapsed list of non-fatal problems found while reading data/."""
    if data.warnings:
        with st.expander(f"Data checks — {len(data.warnings)} note(s)"):
            for warning in data.warnings:
                st.markdown(f"- {warning}")


def _render_footer() -> None:
    st.markdown(
        '<div class="cio-foot">CIO Model Portfolio Dashboard&nbsp;·&nbsp;'
        'illustrative figures&nbsp;·&nbsp;CMA edits are per-session only and '
        'never saved</div>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# main                                                                       #
# --------------------------------------------------------------------------- #
def main() -> None:
    inject_css()

    cfg = _CONFIG                       # already loaded above for the page title
    data = _load_data(_data_fingerprint(cfg))

    # Fatal problems (missing file, missing column) stop the app here.
    if not data.ok:
        st.error("Data could not be loaded — fix the following and reload:")
        for error in data.errors:
            st.markdown(f"- {error}")
        st.stop()

    # This session's private CMA edits. Rebuilt each run; the state lives in
    # st.session_state, so it is per-user and never written to disk.
    store = CmaStore(cfg, data.cma, st.session_state)

    page = sidebar_nav.render(cfg, data, on_reload=_clear_caches)

    _render_session_banner(store)
    _render_data_warnings(data)

    if page == sidebar_nav.PORTFOLIOS:
        page_portfolios.render(cfg, data, store)
    elif page == sidebar_nav.BACKTEST:
        page_backtest.render(cfg, data, store)
    else:
        page_cma.render(cfg, data, store)

    _render_footer()


if __name__ == "__main__":
    main()
