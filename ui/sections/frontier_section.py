"""
=============================================================================
 SECTION 4 — EFFICIENT FRONTIER  (how far the model sits below optimal)
=============================================================================

WHAT THIS FILE DOES
    Solves a long-only mean-variance efficient frontier from the CMA of the
    selected model's currency, then plots the model's RP1-RP5 on it — one
    dotted line per scenario. Below the chart, a table gives the "return gap":
    how much extra expected return the frontier offers at each portfolio's own
    level of risk.

    There is deliberately NO model picker here. The model is whichever one is
    chosen at the top of the page.

WHY MODEL PORTFOLIOS SIT BELOW THE CURVE
    The frontier assumes every asset class is directly investable at exactly
    its CMA, long-only and fully invested, with no other constraints. Real
    model portfolios carry diversification rules, liquidity limits, home bias
    and governance constraints. The gap is the price of those constraints —
    it is expected, not a bug.

PERFORMANCE NOTE
    Solving the frontier is ~120 small optimisations (about 1.3 s). It is
    wrapped in @st.cache_data keyed on the CMA numbers, so it is solved once
    and reused until the CMA changes. Never remove that cache decorator
    without checking how sluggish the page becomes.

WHERE TO CHANGE WHAT
    * Number of points solved   -> settings.toml [frontier].points
    * Risk-free rate            -> settings.toml [frontier].risk_free
    * The maths                 -> core/frontier.py
    * Chart appearance          -> ui/charts.py frontier_scatter()
    * Scenario line colours     -> ui/theme.py SCENARIO_LINE

CALLED BY
    ui/page_portfolios.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.analytics import compute
from core.config import Config
from ui.charts import frontier_scatter
from ui.theme import PLOTLY_CONFIG
from ui.widgets import card_title, horizontal_rule, number_columns, section_heading

# SciPy is only needed for the frontier. If it is missing the rest of the app
# still works and this section shows a friendly message instead of crashing.
try:
    from core.frontier import build as build_frontier
    SCIPY_AVAILABLE = True
except Exception:                                   # pragma: no cover
    SCIPY_AVAILABLE = False

GAP_TABLE_COLUMNS = ["Risk %", "Return %", "Frontier return @ risk %",
                     "Return gap (pp)"]


# --------------------------------------------------------------------------- #
# cached solve                                                               #
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def _solve_frontier(currency: str, cma: pd.DataFrame, corr: pd.DataFrame,
                    asset_codes: tuple, n_points: int, risk_free):
    """
    Cached wrapper around core.frontier.build().

    The cache key includes `cma`, so a user who has edited the CMA in their
    session gets their own cached frontier and never sees anyone else's.
    """
    return build_frontier(cma, corr, list(asset_codes),
                          n_points=n_points, rf=risk_free)


def _risk_return_points(cfg: Config, weights_by_rp: dict, scenario: str,
                        cma, corr) -> pd.DataFrame:
    """One row per risk profile: its label, volatility and expected return."""
    rows = []
    for rp in cfg.rp_ids:
        metrics = compute(weights_by_rp[rp][scenario], cma, corr, cfg)
        rows.append((cfg.rp_short(rp), metrics.volatility, metrics.exp_return))
    return pd.DataFrame(rows, columns=["rp", "vol", "ret"])


# --------------------------------------------------------------------------- #
# the section                                                                #
# --------------------------------------------------------------------------- #
def render(cfg: Config, model_name: str, currency: str,
           cma, corr, weights_by_rp: dict) -> None:
    horizontal_rule()
    section_heading(
        "Optimisation", "This model vs the efficient frontier",
        f"Long-only, fully-invested mean-variance frontier from the {currency} "
        f"CMA. {model_name}'s RP1-RP5 for all three scenarios "
        f"({' / '.join(cfg.scenarios)}) are plotted on it — click a legend "
        "entry to hide it. The vertical gap to the curve is the expected "
        "return given up for that level of risk.",
    )

    with st.container(border=True):
        if not SCIPY_AVAILABLE:
            st.info("The efficient frontier needs SciPy — run "
                    "`pip install scipy` and restart the app.")
            return

        configured_rf = str(cfg.frontier.get("risk_free", "")).strip()

        with st.spinner("Solving the efficient frontier…"):
            frontier = _solve_frontier(
                currency, cma, corr, tuple(cfg.asset_codes),
                int(cfg.frontier.get("points", 120)),
                float(configured_rf) if configured_rf else None,
            )

            points_by_scenario: dict[str, pd.DataFrame] = {}
            gap_rows: list[dict] = []
            for scenario in cfg.scenarios:
                points = _risk_return_points(cfg, weights_by_rp, scenario, cma, corr)
                points_by_scenario[scenario] = points
                for _, row in points.iterrows():
                    gap = frontier.gap(row["vol"], row["ret"])
                    gap_rows.append({
                        "Scenario": scenario,
                        "Profile": row["rp"],
                        "Risk %": row["vol"],
                        "Return %": row["ret"],
                        "Frontier return @ risk %": row["ret"] + gap,
                        "Return gap (pp)": gap,
                    })

        st.plotly_chart(frontier_scatter(frontier, points_by_scenario),
                        config=PLOTLY_CONFIG, use_container_width=True)

        gaps = pd.DataFrame(gap_rows)
        st.dataframe(gaps, hide_index=True, use_container_width=True,
                     column_config=number_columns(GAP_TABLE_COLUMNS, 2))

        widest = gaps.loc[gaps["Return gap (pp)"].idxmax()]
        st.caption(
            "Frontier assumes each asset class is directly investable at its "
            "CMA, long-only and fully invested. Largest gap: "
            f"**{widest['Scenario']} {widest['Profile']}** — "
            f"{widest['Return gap (pp)']:.2f} pp at {widest['Risk %']:.1f}% risk."
        )
