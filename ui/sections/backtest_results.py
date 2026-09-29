"""
=============================================================================
 BACKTEST SECTION 3 — RESULTS  (charts + the metrics table)
=============================================================================

WHAT THIS FILE DOES
    Draws everything below the controls on the Backtesting page, given a dict
    of already-computed portfolio index series:

        {"ESAA": <series>, "DSAA 2026": <series>, "Custom portfolio": <series>}

    1. Growth of 100          every portfolio, rebased to 100 at the start
    2. Drawdown               underwater chart + worst-drawdown caption
    3. Rolling 12m return     side by side
       Rolling 12m volatility
    4. Metrics table          the full set from core/backtest.py METRIC_ROWS

    It does no backtesting itself - ui/page_backtest.py does that and hands
    the results here.

WHERE TO CHANGE WHAT
    * Chart appearance   -> ui/charts.py (growth_chart, drawdown_chart,
                            rolling_chart)
    * Which metrics      -> core/backtest.py METRIC_ROWS + summary_metrics()
    * Rolling window     -> settings.toml [backtest].rolling_months
    * Number formatting  -> _format_metrics() below

CALLED BY
    ui/page_backtest.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import backtest as bt
from core.config import Config
from ui.charts import drawdown_chart, growth_chart, rolling_chart
from ui.theme import PLOTLY_CONFIG
from ui.widgets import card_title

# Metrics that read better with no decimals, and those that are ratios.
RATIO_ROWS = {"Sharpe", "Sortino", "Calmar"}


def _format_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Round ratios to 2dp and percentages to 2dp; keep everything numeric."""
    return frame.round(2)


def _worst_drawdown_caption(results: dict[str, pd.Series]) -> str:
    """One line naming the deepest drawdown across all the plotted portfolios."""
    worst_name, worst = None, None
    for name, series in results.items():
        detail = bt.drawdown_detail(series)
        if worst is None or (detail["depth"] is not None
                             and detail["depth"] < worst["depth"]):
            worst, worst_name = detail, name
    if not worst or worst["trough"] is None:
        return ""
    peak = worst["peak"].strftime("%b %Y") if worst["peak"] is not None else "?"
    trough = worst["trough"].strftime("%b %Y")
    return (f"Deepest fall: **{worst_name}** lost **{abs(worst['depth']):.1f}%** "
            f"from its peak in {peak} to the trough in {trough}.")


def render(cfg: Config, results: dict[str, pd.Series],
           benchmark_name: str | None, period_label: str) -> None:
    if not results:
        st.info("Nothing selected to backtest.")
        return

    settings = cfg.backtest
    rolling_months = int(settings.get("rolling_months", 12))
    rolling_window_days = int(rolling_months / 12 * bt.TRADING_DAYS)

    # ---- 1. growth of 100 --------------------------------------------- #
    with st.container(border=True):
        card_title(f"Growth of 100 — {period_label}")
        st.plotly_chart(growth_chart(results), config=PLOTLY_CONFIG,
                        use_container_width=True)

    # ---- 2. drawdown --------------------------------------------------- #
    with st.container(border=True):
        card_title("Drawdown — how far below the previous peak")
        drawdowns = {name: bt.drawdown_series(series)
                     for name, series in results.items()}
        st.plotly_chart(drawdown_chart(drawdowns), config=PLOTLY_CONFIG,
                        use_container_width=True)
        caption = _worst_drawdown_caption(results)
        if caption:
            st.caption(caption)

    # ---- 3. rolling windows -------------------------------------------- #
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            card_title(f"Rolling {rolling_months}-month return")
            rolling_returns = {
                name: bt.rolling_return(series, rolling_window_days)
                for name, series in results.items()
            }
            if all(s.empty for s in rolling_returns.values()):
                st.caption(f"Needs more than {rolling_months} months of history.")
            else:
                st.plotly_chart(
                    rolling_chart(rolling_returns, "Return", zero_line=True),
                    config=PLOTLY_CONFIG, use_container_width=True)
    with right:
        with st.container(border=True):
            card_title(f"Rolling {rolling_months}-month volatility")
            rolling_vols = {
                name: bt.rolling_volatility(series, rolling_window_days)
                for name, series in results.items()
            }
            if all(s.empty for s in rolling_vols.values()):
                st.caption(f"Needs more than {rolling_months} months of history.")
            else:
                st.plotly_chart(
                    rolling_chart(rolling_vols, "Volatility"),
                    config=PLOTLY_CONFIG, use_container_width=True)

    # ---- 4. the metrics table ------------------------------------------ #
    with st.container(border=True):
        card_title("Backtested metrics")
        frame = bt.metrics_frame(
            results,
            benchmark_name=benchmark_name,
            risk_free=float(settings.get("risk_free", 0.0)),
            var_confidence=float(settings.get("var_confidence", 0.95)),
        )
        st.dataframe(
            _format_metrics(frame), use_container_width=True,
            column_config={c: st.column_config.NumberColumn(c, format="%.2f")
                           for c in frame.columns},
        )
        notes = [
            f"Monthly rebalancing back to target weights "
            f"(settings.toml [backtest].rebalance = "
            f"\"{settings.get('rebalance', 'M')}\").",
            f"Sharpe and Sortino use a {float(settings.get('risk_free', 0)):.1f}% "
            f"risk-free rate.",
            f"VaR / CVaR are monthly, at "
            f"{float(settings.get('var_confidence', 0.95)) * 100:.0f}% confidence.",
        ]
        if benchmark_name:
            notes.append(f"Tracking error is measured against **{benchmark_name}**.")
        st.caption("  ·  ".join(notes))
