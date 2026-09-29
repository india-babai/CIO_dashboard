"""
=============================================================================
 CHARTS  —  every Plotly figure in the app is built here
=============================================================================

WHAT THIS FILE DOES
    One function per chart. Each returns a plotly Figure; the section files
    just call it and hand the result to st.plotly_chart(). Keeping them
    together means you can restyle every chart from one screen.

    FUNCTION                 WHERE IT APPEARS
    ------------------------ -------------------------------------------------
    allocation_donut()       Charts section — the ring of weights
    contribution_bar()       Charts section — weight vs return vs risk
    active_weights_bar()     What-if section — DSAA 2026 vs ESAA tilts
    frontier_scatter()       Efficient frontier section
    correlation_heatmap()    CMA page — "Correlation matrix" tab

WHERE TO CHANGE WHAT
    * Colours              -> ui/theme.py  (which reads ui/css/01_variables.css)
    * Fonts / gridlines    -> ui/theme.py  _build_template()
    * A specific chart     -> its function below
    * Chart height         -> the `height=` argument where it is called

EVERY FUNCTION ENDS WITH `return style(fig, height)` — that applies the shared
template. Don't skip it or the chart will look foreign.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ui.theme import (ACCENT, ASSET_DOT, CUSTOM_LINE, MUTE, NEGATIVE, POSITIVE,
                      RISK_BAR, SCENARIO_LINE, SERIES_PALETTE, WEIGHT_BAR, style)


def series_colour(name: str, position: int) -> str:
    """
    Pick a line colour for a backtest series. Anything whose name starts with
    "Custom" is always black so the user's own portfolio stands out from the
    model portfolios.
    """
    if name.lower().startswith("custom"):
        return CUSTOM_LINE
    return SERIES_PALETTE[position % len(SERIES_PALETTE)]


# --------------------------------------------------------------------------- #
# 1. allocation donut                                                        #
# --------------------------------------------------------------------------- #
def allocation_donut(weights: pd.Series, color_of, height: int = 300) -> go.Figure:
    """
    Ring chart of one weight vector.

    weights  : Series indexed by asset code / sub-group / group name, percent.
    color_of : function name -> hex colour, e.g. cfg.asset_color.
    """
    shown = weights[weights.abs() > 1e-9]
    fig = go.Figure(go.Pie(
        labels=list(shown.index), values=list(shown.values),
        hole=0.62, sort=False, textinfo="none",
        marker=dict(colors=[color_of(x) for x in shown.index],
                    line=dict(color="#fff", width=1.5)),
        hovertemplate="%{label}<br><b>%{value:.1f}%</b><extra></extra>",
    ))
    fig.update_layout(
        showlegend=True, margin=dict(l=0, r=0, t=6, b=6),
        legend=dict(orientation="h", x=0.5, y=-0.05, xanchor="center",
                    font=dict(size=11)),
    )
    return style(fig, height=height)


# --------------------------------------------------------------------------- #
# 2. weight vs return-contribution vs risk-contribution                      #
# --------------------------------------------------------------------------- #
def contribution_bar(per_subgroup: pd.DataFrame, height: int = 300) -> go.Figure:
    """
    Three grouped bars per sub-group: share of capital, of expected return and
    of portfolio risk. A sub-group whose risk bar dwarfs its weight bar is a
    concentration of risk.

    per_subgroup : the .per_subgroup frame from core.analytics.compute().
    """
    rows = per_subgroup.iloc[::-1]          # reversed so the first is on top
    fig = go.Figure()
    fig.add_bar(y=rows["name"], x=rows["weight"], name="Weight",
                orientation="h", marker_color=WEIGHT_BAR)
    fig.add_bar(y=rows["name"], x=rows["ret_contrib_pct"], name="Contribution to return",
                orientation="h", marker_color=ACCENT)
    fig.add_bar(y=rows["name"], x=rows["risk_contrib_pct"], name="Contribution to risk",
                orientation="h", marker_color=RISK_BAR)
    fig.update_layout(
        barmode="group", bargap=0.3,
        xaxis=dict(ticksuffix="%"), yaxis=dict(showgrid=False),
        legend=dict(orientation="h", y=-0.18),
        margin=dict(l=4, r=12, t=6, b=4),
    )
    return style(fig, height=height)


# --------------------------------------------------------------------------- #
# 3. active weights (one scenario minus the benchmark scenario)              #
# --------------------------------------------------------------------------- #
def active_weights_bar(delta: pd.Series, height: int = 300) -> go.Figure:
    """
    Diverging horizontal bars of weight differences, in percentage points.
    Maroon = overweight, grey = underweight. Zero rows are dropped.
    """
    rows = delta[delta.abs() > 1e-6].iloc[::-1]
    if rows.empty:
        fig = go.Figure()
        fig.add_annotation(text="No differences", showarrow=False,
                           font=dict(color=MUTE))
        return style(fig, height=height)

    fig = go.Figure(go.Bar(
        y=list(rows.index), x=list(rows.values), orientation="h",
        marker_color=[POSITIVE if v >= 0 else NEGATIVE for v in rows.values],
        text=[f"{v:+.1f}" for v in rows.values],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br><b>%{x:+.2f} pp</b><extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(ticksuffix=" pp", zeroline=True, zerolinecolor="#B4ACAA"),
        yaxis=dict(showgrid=False),
        margin=dict(l=4, r=26, t=6, b=4),
    )
    return style(fig, height=height)


# --------------------------------------------------------------------------- #
# 4. efficient frontier                                                      #
# --------------------------------------------------------------------------- #
def frontier_scatter(frontier, points_by_scenario: dict[str, pd.DataFrame],
                     height: int = 480) -> go.Figure:
    """
    The frontier curve plus one dotted RP1-RP5 polyline per scenario.

    frontier           : the Frontier object from core.frontier.build().
    points_by_scenario : {"ESAA": df, "DSAA 2026": df, ...} where each df has
                         columns rp / vol / ret (from _risk_return_points()).

    Every series is a separate legend entry, so a user can click one off.
    """
    fig = go.Figure()

    # individual asset classes — black dots for context
    fig.add_scatter(
        x=frontier.assets["vol"], y=frontier.assets["ret"], mode="markers",
        name="Asset classes", marker=dict(size=6, color=ASSET_DOT),
        text=frontier.assets["code"],
        hovertemplate="%{text}<br>vol %{x:.1f}%  ·  ret %{y:.1f}%<extra></extra>",
    )
    # the frontier curve
    fig.add_scatter(
        x=frontier.points["vol"], y=frontier.points["ret"], mode="lines",
        name="Efficient frontier", line=dict(color=ACCENT, width=2.6),
    )
    # global minimum-variance portfolio
    fig.add_scatter(
        x=[frontier.gmv[0]], y=[frontier.gmv[1]], mode="markers",
        name="Min-variance",
        marker=dict(symbol="diamond", size=11, color=ACCENT,
                    line=dict(color="#fff", width=1)),
    )
    # max-Sharpe (tangency) portfolio
    if frontier.tangency:
        fig.add_scatter(
            x=[frontier.tangency[0]], y=[frontier.tangency[1]], mode="markers",
            name="Max Sharpe",
            marker=dict(symbol="star", size=15, color=RISK_BAR,
                        line=dict(color="#fff", width=1)),
        )
    # one dotted line per scenario, RP1 -> RP5
    for i, (label, points) in enumerate(points_by_scenario.items()):
        colour = SCENARIO_LINE[i % len(SCENARIO_LINE)]
        fig.add_scatter(
            x=points["vol"], y=points["ret"], mode="lines+markers+text", name=label,
            line=dict(color=colour, width=1.6, dash="dot"),
            marker=dict(size=9, color=colour, line=dict(color="#fff", width=1)),
            text=points["rp"], textposition="top center",
            textfont=dict(size=10, color=colour),
            hovertemplate=(f"{label}<br>%{{text}}<br>"
                           "vol %{x:.2f}%  ·  ret %{y:.2f}%<extra></extra>"),
        )

    fig.update_layout(
        xaxis=dict(title="Volatility  (% p.a.)", ticksuffix="%"),
        yaxis=dict(title="Expected return  (% p.a.)", ticksuffix="%",
                   showgrid=False),          # no horizontal gridlines
        legend=dict(orientation="h", y=-0.22, font=dict(size=11),
                    itemclick="toggle", itemdoubleclick="toggleothers"),
        margin=dict(l=6, r=10, t=6, b=4),
    )
    return style(fig, height=height)


# --------------------------------------------------------------------------- #
# 5. correlation heatmap (CMA page)                                          #
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# 6. backtest: growth of 100                                                 #
# --------------------------------------------------------------------------- #
def growth_chart(results: dict[str, pd.Series], height: int = 420) -> go.Figure:
    """
    Indexed growth of each backtested portfolio, all starting at 100.

    results : {"ESAA": <index series>, "Custom portfolio": <index series>, ...}
    """
    fig = go.Figure()
    for position, (name, series) in enumerate(results.items()):
        if series.empty:
            continue
        fig.add_scatter(
            x=series.index, y=series.values, mode="lines", name=name,
            line=dict(color=series_colour(name, position), width=1.9),
            hovertemplate=f"{name}<br>%{{x|%d %b %Y}}<br><b>%{{y:,.1f}}</b><extra></extra>",
        )
    fig.update_layout(
        xaxis=dict(title=None, showgrid=False),
        yaxis=dict(title="Growth of 100", showgrid=True),
        legend=dict(orientation="h", y=-0.18, font=dict(size=11),
                    itemclick="toggle", itemdoubleclick="toggleothers"),
        margin=dict(l=6, r=10, t=6, b=4), hovermode="x unified",
    )
    return style(fig, height=height)


# --------------------------------------------------------------------------- #
# 7. backtest: drawdown (underwater)                                         #
# --------------------------------------------------------------------------- #
def drawdown_chart(drawdowns: dict[str, pd.Series], height: int = 260) -> go.Figure:
    """
    How far below its own running peak each portfolio is, through time.
    Values are negative percentages; the first series is shaded.
    """
    fig = go.Figure()
    for position, (name, series) in enumerate(drawdowns.items()):
        if series.empty:
            continue
        colour = series_colour(name, position)
        fig.add_scatter(
            x=series.index, y=series.values, mode="lines", name=name,
            line=dict(color=colour, width=1.5),
            fill="tozeroy" if position == 0 else None,
            fillcolor="rgba(122,31,43,0.12)" if position == 0 else None,
            hovertemplate=f"{name}<br>%{{x|%d %b %Y}}<br><b>%{{y:.1f}}%</b><extra></extra>",
        )
    fig.update_layout(
        xaxis=dict(title=None, showgrid=False),
        yaxis=dict(title="Drawdown", ticksuffix="%", showgrid=True),
        legend=dict(orientation="h", y=-0.24, font=dict(size=11)),
        margin=dict(l=6, r=10, t=6, b=4), hovermode="x unified",
    )
    return style(fig, height=height)


# --------------------------------------------------------------------------- #
# 8. backtest: rolling return / rolling volatility                           #
# --------------------------------------------------------------------------- #
def rolling_chart(series_by_name: dict[str, pd.Series], y_title: str,
                  height: int = 240, zero_line: bool = False) -> go.Figure:
    """
    Generic rolling-window line chart. Used twice on the Backtesting page:
    once for rolling return and once for rolling volatility.
    """
    fig = go.Figure()
    for position, (name, series) in enumerate(series_by_name.items()):
        if series.empty:
            continue
        fig.add_scatter(
            x=series.index, y=series.values, mode="lines", name=name,
            line=dict(color=series_colour(name, position), width=1.5),
            hovertemplate=f"{name}<br>%{{x|%d %b %Y}}<br><b>%{{y:.1f}}%</b><extra></extra>",
        )
    fig.update_layout(
        xaxis=dict(title=None, showgrid=False),
        yaxis=dict(title=y_title, ticksuffix="%", showgrid=True,
                   zeroline=zero_line, zerolinecolor="#B4ACAA"),
        legend=dict(orientation="h", y=-0.26, font=dict(size=11)),
        margin=dict(l=6, r=10, t=6, b=4), hovermode="x unified",
    )
    return style(fig, height=height)


# --------------------------------------------------------------------------- #
# 9. correlation heatmap (CMA page)                                          #
# --------------------------------------------------------------------------- #
def correlation_heatmap(matrix: pd.DataFrame, height: int = 620) -> go.Figure:
    """Diverging heatmap: black = -1, cream = 0, maroon = +1."""
    fig = go.Figure(go.Heatmap(
        z=matrix.values, x=list(matrix.columns), y=list(matrix.index),
        zmin=-1, zmax=1,
        colorscale=[[0.0, "#1A1719"], [0.5, "#F1ECE8"], [1.0, ACCENT]],
        colorbar=dict(title="ρ", thickness=12, len=0.7),
        hovertemplate="%{y}<br>%{x}<br><b>%{z:.2f}</b><extra></extra>",
    ))
    fig.update_layout(
        margin=dict(l=4, r=4, t=4, b=4),
        xaxis=dict(showgrid=False, tickangle=45),
        yaxis=dict(showgrid=False, autorange="reversed"),
    )
    return style(fig, height=height)
