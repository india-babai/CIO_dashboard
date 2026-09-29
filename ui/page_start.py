"""
=============================================================================
 PAGE 0 — START HERE  (the read-me landing page users see first)
=============================================================================

WHAT THIS FILE DOES
    A plain-English guide to using the app, shown by default when someone
    opens it. Nothing on this page reads data or calculates anything - it is
    static text plus a couple of counts, so it always loads instantly even if
    the data files are broken.

    NOT TO BE CONFUSED WITH:
      README.md            for whoever RUNS the app (install, commands)
      HOW_TO_NAVIGATE.md   for whoever CHANGES the code
      this file            for whoever USES the dashboard

WHERE TO CHANGE WHAT
    * The wording          -> right here, it is all literal text
    * Stop it being the
      default landing page -> ui/sidebar_nav.py  DEFAULT_PAGE
    * Remove it entirely   -> delete its entry from NAV_GROUPS in
                              ui/sidebar_nav.py and the branch in app.py

CALLED BY
    app.py
"""
from __future__ import annotations

import streamlit as st

from core.config import Config
from ui.widgets import card_title, section_heading


def render(cfg: Config, data, cma_store) -> None:
    section_heading(
        "Start here", "How to use this dashboard",
        "A two-minute guide. Everything here is also reachable from the "
        "left-hand menu at any time.",
    )

    model_count = (int(data.portfolios["model_id"].nunique())
                   if not data.portfolios.empty else 0)

    # ---- the three pages ------------------------------------------------ #
    left, middle, right = st.columns(3)

    with left:
        with st.container(border=True):
            card_title("1 · Portfolios")
            st.markdown(
                f"**What it shows.** Pick one of the **{model_count} model "
                "portfolios** from the dropdown. All five risk profiles "
                "(RP1–RP5) appear side by side in the house format:\n\n"
                "- the 16 asset classes\n"
                "- their 6 sub-group totals\n"
                "- their 4 group totals\n"
                "- expected return, volatility, Sharpe and tracking error\n\n"
                "Each block has a column per scenario "
                f"({' / '.join(cfg.scenarios)}).\n\n"
                "**Try this.** Tick *Show "
                f"{cfg.scenario_change[1]} & Change* to add the prior-year "
                "column and the year-on-year move."
            )

    with middle:
        with st.container(border=True):
            card_title("2 · Backtesting")
            st.markdown(
                "**What it shows.** The same portfolios run through 20 years "
                "of daily price history, rebalanced monthly.\n\n"
                "- growth of 100, drawdown, rolling return and volatility\n"
                "- CAGR, Sharpe, Sortino, max drawdown, monthly VaR and CVaR\n"
                "- any period from 1 year to the full history\n\n"
                "**Try this.** Tick *Include my custom portfolio*, then edit "
                "the weights to see how your own mix would have behaved."
            )

    with right:
        with st.container(border=True):
            card_title("3 · Capital Market Assumptions")
            st.markdown(
                "**What it shows.** The expected return, volatility and "
                "correlations that every number on the other two pages is "
                "built from. This is the input, not the output.\n\n"
                "**Try this.** Change an expected return and press *Apply* — "
                "then go back to Portfolios and watch the metrics move.\n\n"
                "Your edits are **private to your browser session** and are "
                "never saved."
            )

    # ---- the two things people get wrong -------------------------------- #
    st.markdown("<hr/>", unsafe_allow_html=True)
    section_heading("Good to know", "Three things worth reading once")

    first, second, third = st.columns(3)

    with first:
        with st.container(border=True):
            card_title("Nothing you change is saved")
            st.markdown(
                "Editing weights on **Portfolios**, building a custom "
                "portfolio on **Backtesting**, or changing a number on the "
                "**CMA** page only affects *your* screen, for *this* session.\n\n"
                "Nobody else sees it, and closing the tab discards it. "
                "Use **Download full report** in the left menu first if you "
                "want to keep anything."
            )

    with second:
        with st.container(border=True):
            card_title("Download full report")
            st.markdown(
                "The button in the left menu builds **one Excel file** with "
                "everything for the selected model:\n\n"
                "- the allocation table, per profile and combined\n"
                "- risk-return metrics\n"
                "- the CMA and correlation matrix\n"
                "- the efficient frontier and the gap to it\n"
                "- every backtest series and metric, with charts\n\n"
                "It reflects any edits you have made."
            )

    with third:
        with st.container(border=True):
            card_title("Where the numbers come from")
            st.markdown(
                "**Portfolios** uses the CMA — these are *forward-looking* "
                "expectations.\n\n"
                "**Backtesting** uses actual price history — these are "
                "*realised* results.\n\n"
                "They will not match, and that is correct. A realised return "
                "is always a little below the forward-looking one for the same "
                "portfolio, because volatility drags compounding down."
            )

    st.caption(
        "Each model portfolio carries its own currency, so choosing the model "
        "also chooses which capital market assumptions and which price history "
        "are used — there is no separate currency selector."
    )
