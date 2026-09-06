"""
=============================================================================
 CIO MODEL PORTFOLIO DASHBOARD  —  START HERE
=============================================================================

    Run with:   .venv/Scripts/python.exe -m streamlit run app.py

WHAT THIS FILE DOES
    The entry point, and nothing more. It:
        1. sets the browser tab title and page width
        2. injects the stylesheet          -> ui/styling.py
        3. loads settings.toml + data/     -> core/config.py, core/data_loader.py
        4. draws the top bar and the two-page nav
        5. hands over to one of the two pages

    All the real work is in the page files:
        ui/page_portfolios.py    the model portfolio landing page
        ui/page_cma.py           the capital market assumptions page

    ==> New to this codebase? Read HOW_TO_NAVIGATE.md first.

WHERE TO CHANGE WHAT
    * Browser tab title / icon    -> st.set_page_config() below
    * The top bar wording         -> _render_top_bar() below
    * Add a THIRD page            -> add its name to PAGES, write
                                     ui/page_<name>.py, add one branch in main()
    * The footer text             -> _render_footer() below
"""
from __future__ import annotations

import os

import streamlit as st

from core.cma_store import CmaStore
from core.config import load_config
from core.data_loader import load_all
from ui import page_cma, page_portfolios
from ui.styling import inject_css

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

PORTFOLIOS_PAGE = "Portfolios"
CMA_PAGE = "Capital Market Assumptions"
PAGES = [PORTFOLIOS_PAGE, CMA_PAGE]

# set_page_config must be the first Streamlit call, so the config is read here
# rather than inside main(). Change the title in settings.toml [app].title.
_CONFIG = load_config()

st.set_page_config(
    page_title=_CONFIG.app.get("title", "CIO Model Portfolios"),
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",     # the sidebar is also hidden by CSS
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
    button in the top bar forces the same thing manually.
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


# --------------------------------------------------------------------------- #
# chrome                                                                     #
# --------------------------------------------------------------------------- #
def _render_top_bar(cfg, data) -> None:
    """The black-on-white title bar with the counts on the right."""
    model_count = (int(data.portfolios["model_id"].nunique())
                   if not data.portfolios.empty else 0)
    currency_count = (int(data.portfolios["currency"].nunique())
                      if not data.portfolios.empty else 0)
    st.markdown(
        f"""
        <div class="cio-topbar">
          <div class="cio-brand">
            <span class="mark">CIO<span class="dot">.</span>&nbsp;Model Portfolios</span>
            <span class="sub">{cfg.app.get("subtitle", "")}</span>
          </div>
          <div class="cio-meta">
            <b>{model_count}</b> model portfolios &nbsp;·&nbsp;
            <b>{len(cfg.asset_codes)}</b> asset classes &nbsp;·&nbsp;
            <b>{currency_count}</b> currencies
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_navigation() -> str:
    """
    The page pills plus the Reload button. Returns the chosen page name.

    The st.container(key="cio-nav") matters: Streamlit turns that key into the
    CSS class .st-key-cio-nav, which ui/css/04_widgets.css uses to give ONLY
    this segmented control the rounded-pill look.
    """
    with st.container(key="cio-nav"):
        left, right = st.columns([3, 1])
        with left:
            chosen = st.segmented_control("nav", PAGES, default=PORTFOLIOS_PAGE,
                                          label_visibility="collapsed")
        with right:
            if st.button("↻  Reload data", use_container_width=True):
                _load_data.clear()
                st.rerun()
    return chosen or PORTFOLIOS_PAGE


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

    _render_top_bar(cfg, data)

    # Fatal problems (missing file, missing column) stop the app here.
    if not data.ok:
        st.error("Data could not be loaded — fix the following and reload:")
        for error in data.errors:
            st.markdown(f"- {error}")
        st.stop()

    # This session's private CMA edits. Rebuilt each run; the state lives in
    # st.session_state, so it is per-user and never written to disk.
    store = CmaStore(cfg, data.cma, st.session_state)

    page = _render_navigation()
    _render_session_banner(store)
    _render_data_warnings(data)

    if page == PORTFOLIOS_PAGE:
        page_portfolios.render(cfg, data, store)
    else:
        page_cma.render(cfg, data, store)

    _render_footer()


if __name__ == "__main__":
    main()
