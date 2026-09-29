"""
=============================================================================
 THEME  —  colours for the Python/Plotly side of the app
=============================================================================

WHAT THIS FILE DOES
    Reads the colour variables straight out of  ui/css/01_variables.css  and
    exposes them to Python, then builds the shared Plotly template so every
    chart looks the same.

    ==> You never define a colour twice. Edit 01_variables.css and both the
        CSS and the charts change together.

WHERE TO CHANGE WHAT
    * Any brand colour            -> ui/css/01_variables.css
    * Chart series colours        -> SCENARIO_LINE / CHART_COLORWAY below
    * Chart fonts, gridlines      -> _build_template() below
    * Hide/show the Plotly toolbar-> PLOTLY_CONFIG below

USED BY
    ui/charts.py and every section that draws a figure.
"""
from __future__ import annotations

import os
import re

import plotly.graph_objects as go
import plotly.io as pio

CSS_VARIABLES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "css", "01_variables.css")


# --------------------------------------------------------------------------- #
# read the palette out of the CSS file                                       #
# --------------------------------------------------------------------------- #
def _read_css_variables(path: str) -> dict[str, str]:
    """Parse the `:root { --name: value; }` block of a CSS file into a dict."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return {}
    block = re.search(r":root\s*\{(.*?)\}", text, re.S)
    if not block:
        return {}
    return {name: value.strip()
            for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block.group(1))}


_VARS = _read_css_variables(CSS_VARIABLES_FILE)


def css_var(name: str, fallback: str) -> str:
    """Look up one CSS variable, e.g. css_var('--accent', '#7A1F2B')."""
    return _VARS.get(name, fallback)


# --------------------------------------------------------------------------- #
# named colours (same values as the CSS)                                     #
# --------------------------------------------------------------------------- #
ACCENT = css_var("--accent", "#7A1F2B")          # maroon
ACCENT_SOFT = css_var("--accent-soft", "#A33847")
BLACK = css_var("--black", "#17161A")
INK = css_var("--ink", "#1A1719")
MUTE = css_var("--mute", "#7A6E71")
LINE = css_var("--line", "#E4E4E4")
ZEBRA = css_var("--zebra", "#E9E9EA")

GRID = "#EAE4E2"                 # chart gridlines
PAPER = "rgba(0,0,0,0)"          # transparent chart background

# ---- chart-specific colours ---------------------------------------------- #
POSITIVE = ACCENT                # bars above zero (overweight vs benchmark)
NEGATIVE = "#8A8385"             # bars below zero (underweight)
WEIGHT_BAR = "#D8D2CE"           # pale grey  — "Weight" series
RISK_BAR = "#3C3739"             # near-black — "Contribution to risk" series
ASSET_DOT = BLACK                # single asset classes on the frontier chart

# One colour per scenario line on the efficient-frontier chart, in the order
# scenarios appear in settings.toml ([scenarios].columns).
SCENARIO_LINE = ["#2E7D9E",      # teal    — ESAA
                 "#B8862B",      # gold    — DSAA 2026
                 "#7E4A8E",      # plum    — DSAA 2025
                 "#4C5C68", "#9B5DA0"]   # spare colours if you add scenarios

# One colour per line on the Backtesting charts. The first is maroon because
# the first series plotted there is usually the one the user cares about, and
# a custom portfolio is always drawn in CUSTOM_LINE so it stands out.
SERIES_PALETTE = ["#7A1F2B", "#2E7D9E", "#B8862B", "#7E4A8E",
                  "#4C5C68", "#2E8B6F", "#9B5DA0", "#8A8385"]
CUSTOM_LINE = "#17161A"          # black — the user's own custom portfolio

CHART_COLORWAY = [ACCENT, INK, ACCENT_SOFT, "#6E6A6B", "#C98A94",
                  "#4A4446", "#8A8385", "#5A1620", "#B0AAAB", "#2E2A2B"]

FONT = ('Inter, "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, '
        'Helvetica, Arial, sans-serif')

# Plotly's own toolbar is hidden; pass this to every st.plotly_chart(config=...)
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}


# --------------------------------------------------------------------------- #
# the shared Plotly template                                                 #
# --------------------------------------------------------------------------- #
def _build_template() -> go.layout.Template:
    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family=FONT, size=13, color=INK),
        paper_bgcolor=PAPER,
        plot_bgcolor=PAPER,
        margin=dict(l=8, r=8, t=8, b=8),
        colorway=CHART_COLORWAY,
        hoverlabel=dict(font=dict(family=FONT, size=12),
                        bgcolor="#FFFFFF", bordercolor=GRID),
        xaxis=dict(showgrid=True, gridcolor=GRID, zeroline=False,
                   linecolor=GRID, tickcolor=GRID, tickfont=dict(color=MUTE)),
        yaxis=dict(showgrid=True, gridcolor=GRID, zeroline=False,
                   linecolor=GRID, tickcolor=GRID, tickfont=dict(color=MUTE)),
        legend=dict(font=dict(color=MUTE, size=12), bgcolor=PAPER),
    )
    return template


pio.templates["cio"] = _build_template()


def style(fig: go.Figure, height: int | None = None) -> go.Figure:
    """Apply the shared template to a figure. Call this last in every chart."""
    fig.update_layout(template="cio")
    if height:
        fig.update_layout(height=height)
    return fig
