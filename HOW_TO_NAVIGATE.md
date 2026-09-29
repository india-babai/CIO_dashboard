# HOW TO NAVIGATE THIS CODEBASE

**Read this file first. It is written to be the only reference you need.**

You are maintaining this alone. Everything below assumes no prior knowledge of
the code, and tells you *exactly which file to open* for any change you might
want to make.

---

## CONTENTS

1. [What this app is — 60 seconds](#1-what-this-app-is--60-seconds)
2. [Running it](#2-running-it)
3. [The map of the repository](#3-the-map-of-the-repository)
4. [Two rules that explain the whole layout](#4-two-rules-that-explain-the-whole-layout)
5. [What you see on screen → what draws it](#5-what-you-see-on-screen--what-draws-it)
6. [**The change cookbook** — "I want to change X"](#6-the-change-cookbook)
7. [Reference: `settings.toml`](#7-reference-settingstoml)
8. [Reference: the data files](#8-reference-the-data-files)
9. [How data flows through the app](#9-how-data-flows-through-the-app)
10. [Eight things that will surprise you](#10-eight-things-that-will-surprise-you)
11. [Troubleshooting](#11-troubleshooting)
12. [Glossary](#12-glossary)

---

## 1. What this app is — 60 seconds

A four-page Streamlit dashboard for browsing CIO model portfolios. The pages
are reached from the dark **left-hand sidebar**, which groups them into
*Guide* (how to use it), *Analysis* (things you look at) and *Inputs* (the
control panel behind them). The sidebar also carries the **Download full
report** button.

**Page 0 — Start here.** The page users land on: a plain-English guide to the
other three, written for the reader rather than the maintainer. It is pure
static text — it calculates nothing, so it loads even if the data is broken.

**Page 1 — Portfolios.** You pick one model portfolio from a dropdown. It shows
that model's five risk profiles (RP1…RP5) **side by side** in the house table
format: 16 asset classes, then their 6 sub-group totals, then their 4 group
totals, then four risk/return metrics. Below that you can edit any weight and
watch everything recalculate, see charts, and see how far the model sits below
the efficient frontier.

**Page 2 — Backtesting.** Runs the same model portfolios through 20 years of
daily price history, monthly rebalanced. Compare the three scenarios for one
risk profile, or all five risk profiles for one scenario, or build your own
portfolio and test it alongside. Growth, drawdown and rolling charts plus a
full metrics table (CAGR, max drawdown, monthly VaR/CVaR, Sharpe, Sortino…).

**Page 3 — Capital Market Assumptions.** The expected return, volatility and
correlation numbers that every figure on page 1 is calculated from. You can
edit them to try things — but only for your own browser session. This is an
*Inputs* page — a control panel, not analysis.

Three facts that explain most of the design:

| Fact | Consequence |
|---|---|
| Each model carries its own currency | There is no currency picker — picking the model picks the CMA |
| Each model/profile has **three** weight sets (ESAA, DSAA 2026, DSAA 2025) | Every table has one column per scenario, plus a "Change" column |
| CMA edits are a personal scratchpad | Nothing is ever written to disk; a new session starts clean |
| Nothing a user changes survives the tab closing | The sidebar's **Download full report** is the only way to keep anything |

---

## 2. Running it

Python **3.11 or newer** is required (the config is read with the standard
library's `tomllib`). This machine has 3.13.

### First time on a new machine

```bash
cd CIO_dashboard
python -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

On macOS/Linux, use `.venv/bin/python` everywhere instead of
`.venv/Scripts/python.exe`.

### Every day

```bash
.venv/Scripts/python.exe -m streamlit run app.py
```

Then open the URL it prints (usually <http://localhost:8501>).

### The two other commands worth knowing

```bash
.venv/Scripts/python.exe scripts/smoke_test.py
```
Checks all the data and maths without launching the app. ~40 seconds, 67
checks. **Run this after every change.** If it passes, your problem is in the
`ui/` folder; if it fails, it's in `core/` or your data.

```bash
.venv/Scripts/python.exe scripts/generate_sample_data.py
```
Regenerates the demo data. **This overwrites `data/` — do not run it once your
real data is in there.**

### The dependencies, and why each one is there

| Package | Why |
|---|---|
| `streamlit` | the web framework — everything you see |
| `pandas` | all tables |
| `numpy` | the matrix maths in `core/analytics.py` |
| `plotly` | all charts |
| `scipy` | **only** the efficient frontier optimiser. If missing, the app still runs and that one section shows a message |
| `openpyxl` | reading `.xlsx` data, and writing both Excel downloads (the table export and the full report) |

---

## 3. The map of the repository

```
CIO_dashboard/
│
├── HOW_TO_NAVIGATE.md      ← you are here
├── README.md               short quick-start; points back here
├── settings.toml           ★ ALL configuration. Asset classes, groups,
│                             scenarios, risk profiles, tolerances.
├── requirements.txt
├── app.py                  ★ START HERE when reading code. Entry point:
│                             page setup, top bar, nav, then hands off.
│
├── core/                   ═══ PURE PYTHON. NO STREAMLIT. ═══
│   ├── config.py             reads settings.toml → the `cfg` object
│   ├── data_loader.py        reads + validates everything in data/
│   ├── taxonomy.py           model list; 16 codes → 6 sub-groups / 4 groups
│   ├── analytics.py        ★ ALL the maths: return, vol, Sharpe, tracking
│   │                         error, contributions
│   ├── frontier.py           the efficient frontier optimiser (SciPy)
│   ├── report_tables.py    ★ the four table blocks every display shares
│   ├── excel_export.py       the small .xlsx download under the house table
│   ├── report_export.py      the BIG .xlsx — 17 sheets, with native charts
│   ├── history_loader.py     reads data/history/prices_<CCY>.csv
│   ├── backtest.py         ★ ALL the backtest maths: growth, drawdown,
│   │                         VaR/CVaR, Sharpe, rolling windows
│   └── cma_store.py          the imported CMA + this session's private edits
│
├── ui/                     ═══ ALL STREAMLIT. NO MATHS. ═══
│   ├── theme.py              colours for Python; reads them from the CSS
│   ├── styling.py            loads ui/css/*.css into the page
│   ├── widgets.py            section_heading(), card_title(), …
│   ├── charts.py           ★ every Plotly figure in the app
│   ├── weight_edits.py     ★ the session copy of the weights you edit
│   ├── report_builder.py     gathers session state for the full report
│   ├── sidebar_nav.py      ★ the dark left navigation; ADD A PAGE HERE
│   ├── page_start.py         page 0 — the read-me users land on
│   ├── page_portfolios.py  ★ page 1 — reads like a table of contents
│   ├── page_backtest.py      page 2
│   ├── page_cma.py           page 3
│   │
│   ├── sections/             one file per section of a page
│   │   ├── house_table.py        the big RP1–RP5 table
│   │   ├── whatif_editor.py      editable weights + live metrics + tilt chart
│   │   ├── charts_section.py     donut + contribution chart
│   │   ├── frontier_section.py   efficient frontier
│   │   ├── backtest_controls.py  what to compare, over what period
│   │   ├── backtest_custom.py    build your own portfolio
│   │   └── backtest_results.py   growth / drawdown / rolling + metrics table
│   │
│   └── css/                  the stylesheet, split by concern
│       ├── 01_variables.css  ★ THE ONLY PLACE COLOURS ARE DEFINED
│       ├── 02_streamlit_reset.css   hides Streamlit's own chrome
│       ├── 03_layout_and_headings.css
│       ├── 04_widgets.css
│       ├── 05_house_table.css       the big table
│       └── 06_sidebar.css           the dark left navigation
│
├── data/                   ═══ YOUR DATA ═══
│   ├── model_portfolios.xlsx
│   ├── cma/
│   │   ├── cma_USD.csv     expected return + volatility
│   │   └── corr_USD.csv    correlation matrix   (…and one pair per currency)
│   └── history/
│       └── prices_USD.csv  20 years of daily index levels (one per currency)
│
├── scripts/
│   ├── smoke_test.py         run after every change
│   ├── generate_sample_data.py     (also calls the one below)
│   └── generate_history_data.py
│
└── docs/
    ├── page-1-portfolios.svg  ★ annotated diagram: screen region → file
    └── page-2-cma.svg
```

**Every `.py` and `.css` file starts with a header block** telling you what it
does and where to change what. If you open a file and are unsure, read its
first 30 lines.

---

## 4. Two rules that explain the whole layout

### Rule 1 — `core/` never imports Streamlit; `ui/` never does maths

```
core/   numbers in → numbers out.   Testable without a browser.
ui/     numbers in → pixels out.    No formula ever lives here.
```

This is why `scripts/smoke_test.py` can check everything important in 30
seconds without launching a web server. It also gives you an instant
diagnosis:

- **Wrong number on screen?** → the bug is in `core/`. Run the smoke test.
- **Right number, wrong appearance?** → the bug is in `ui/`.

If you ever find yourself writing `import streamlit` inside `core/`, or a
formula inside `ui/`, stop — it belongs on the other side.

### Rule 2 — data shapes, not code, define the domain

Adding an asset class, a group, a scenario or a risk profile is a
**`settings.toml` edit**, not a code edit. The code loops over whatever is in
the config. There is no hard-coded list of 16 asset codes anywhere in Python.

The two exceptions, both deliberate:

- `core/report_tables.py` → `METRIC_ROWS` — the four metric names, because
  each one needs its own formula.
- `ui/theme.py` → `SCENARIO_LINE` — chart colours, one per scenario.

---

## 5. What you see on screen → what draws it

Open **`docs/page-1-portfolios.svg`** and **`docs/page-2-cma.svg`** in any web
browser. They are annotated diagrams of both pages: every region of the screen
is labelled with the file that draws it. That is the fastest way to find code.

The same information as text, top to bottom:

### The sidebar (on every page)

```
┌──────────────────────┐
│ CIO.                 │  ui/sidebar_nav.py  _render_brand()
│ Model Portfolios     │
│ STRATEGIC & TACTICAL │
├──────────────────────┤
│ GUIDE                │  ui/sidebar_nav.py  NAV_GROUPS  ← ADD A PAGE HERE
│   Start here         │  active item = st.button(type="primary"),
│                      │  painted maroon by ui/css/06_sidebar.css
│ ANALYSIS             │
│   Portfolios         │
│   Backtesting        │
│                      │
│ INPUTS               │
│   Capital Market     │
│   Assumptions        │
├──────────────────────┤
│ REPORT               │  ui/sidebar_nav.py  _render_report_button()
│ ⬇ Build full report  │  builds it → ui/report_builder.py
│ ⬇ Download .xlsx     │  appears only after the build finishes
├──────────────────────┤
│ 10 model portfolios  │  ui/sidebar_nav.py  _render_meta()
│ ↻ Reload data        │  clears the data caches in app.py
└──────────────────────┘
```

The report button is **two clicks on purpose**: Streamlit's
`st.download_button` needs the file's bytes *before* it can be drawn, and
building the report takes several seconds. Building on every page load would
make the whole app feel slow, so the first button builds and stores the bytes
in session state, and the second one hands them over. See §10.7.

### Page 0 — Start here

```
┌──────────────────────────────────────────────────────────────────────┐
│ START HERE / How to use this dashboard                               │  ui/page_start.py
├──────────────────────────────────────────────────────────────────────┤     render()
│ ┌────────────┐ ┌────────────┐ ┌────────────┐                         │
│ │1·Portfolios│ │2·Backtest. │ │3·CMA       │   what each page is for  │
│ └────────────┘ └────────────┘ └────────────┘                         │
│ GOOD TO KNOW                                                         │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐                         │
│ │Nothing is  │ │Download    │ │Where the   │                         │
│ │saved       │ │full report │ │numbers are │                         │
│ └────────────┘ └────────────┘ └────────────┘                         │
└──────────────────────────────────────────────────────────────────────┘
```

It is **all literal text** — no data reads, no maths. Edit the wording
directly in `ui/page_start.py`; there is nothing else to keep in sync.

### Page 1 — Portfolios

```
┌──────────────────────────────────────────────────────────────────────┐
│ MODEL PORTFOLIO                                                      │  ui/widgets.py
│ Strategic & dynamic asset allocation                                 │     section_heading()
├──────────────────────────────────────────────────────────────────────┤
│ [ EUR EMEA                                                    ▾ ]    │  ui/page_portfolios.py
│                                          ↑ THE ONLY MODEL PICKER     │     _choose_model()
├──────────────────────────────────────────────────────────────────────┤
│ EUR EMEA · valued in EUR · …   □ Show DSAA 2025 & Change  [↺ Reset]  │  ui/page_portfolios.py
├──────────────────────────────────────────────────────────────────────┤     _model_summary_bar()
│ ASSET CLASS │    RP1    │ │    RP2    │ │    RP3    │ …              │  ui/sections/
│             │ESAA│D2026 │ │ESAA│D2026 │ │ESAA│D2026 │                │    house_table.py
│ EME         │2.64│ 4.72 │ │6.42│ 8.16 │ │9.96│11.88 │   16 rows      │  numbers from
│ ══════════════ black rule ═══════════════════════════                │    core/report_tables.py
│ Equity      │…                                          6 sub-groups │  styling from
│ ══════════════ black rule ═══════════════════════════                │    ui/css/05_house_table.css
│ Equity      │…                                          4 groups     │
│ ══════════════ black rule ═══════════════════════════                │
│ RISK-RETURN METRICS                                                  │
│ Exp Ret     │…                                          4 metrics    │
├──────────────────────────────────────────────────────────────────────┤
│ [⬇ Download (Excel — one sheet per RP)]                              │  core/excel_export.py
├──────────────────────────────────────────────────────────────────────┤
│ WHAT-IF — ADJUST INDIVIDUAL WEIGHTS                                  │  ui/sections/
│ (RP1) RP2 RP3 RP4 RP5                                                │    whatif_editor.py
│ ┌─────────────────┐  ┌──────────────────────────────────┐            │  state handling in
│ │ editable grid   │  │ DSAA 2026 vs ESAA — active       │            │    ui/weight_edits.py
│ ├─────────────────┤  │ weights bar chart                │            │  chart in
│ │ live metrics    │  │                                  │            │    ui/charts.py
│ └─────────────────┘  └──────────────────────────────────┘            │
├──────────────────────────────────────────────────────────────────────┤
│ ALLOCATION & RISK — Charts                                           │  ui/sections/
│ [RP] [Scenario] [Level]                                              │    charts_section.py
│ ( donut )              ( weight vs return vs risk bars )             │  charts in ui/charts.py
├──────────────────────────────────────────────────────────────────────┤
│ OPTIMISATION — This model vs the efficient frontier                   │  ui/sections/
│ ( frontier curve + 3 scenario lines + gap table )                    │    frontier_section.py
├──────────────────────────────────────────────────────────────────────┤  maths in core/frontier.py
│ CIO Model Portfolio Dashboard · CMA edits are per-session only        │  app.py _render_footer()
└──────────────────────────────────────────────────────────────────────┘
```

### Page 2 — Backtesting

```
┌──────────────────────────────────────────────────────────────────────┐
│ BACKTESTING / Historical performance                                 │  ui/page_backtest.py
│ [ EUR EMEA                                                    ▾ ]    │     render()
│ EUR EMEA · priced in EUR · history Jun 2007–Sep 2026 · monthly       │
├──────────────────────────────────────────────────────────────────────┤
│ ⚠ No price history for X, Y — excluded and weights scaled up         │  ui/page_backtest.py
├──────────────────────────────────────────────────────────────────────┤     (missing-data warning)
│ WHAT TO COMPARE                                                      │  ui/sections/
│ (Scenarios for one profile)(All risk profiles)(Custom only)          │    backtest_controls.py
│ (RP1)(RP2)(RP3)(RP4)(RP5)        [x] Include my custom portfolio     │
│ PERIOD  (1Y)(3Y)(5Y)(10Y)(20Y)(All)(Custom)                          │
├──────────────────────────────────────────────────────────────────────┤
│ BUILD YOUR OWN PORTFOLIO                                             │  ui/sections/
│ [↺ Reset to RP3 DSAA 2026]            Total 100.0 ✓                  │    backtest_custom.py
│ ┌──────────────┬────────┐                                            │
│ │ Asset Class  │ Weight │  editable, 16 rows                         │
├──────────────────────────────────────────────────────────────────────┤
│ GROWTH OF 100 — LAST 10 YEARS                                        │  ui/sections/
│ ( line per portfolio, all rebased to 100 )                           │    backtest_results.py
├──────────────────────────────────────────────────────────────────────┤
│ DRAWDOWN — HOW FAR BELOW THE PREVIOUS PEAK                           │  charts in
│ ( underwater chart )   "Deepest fall: … lost 24.8% …"                │    ui/charts.py
├──────────────────────────────────────────────────────────────────────┤
│ ROLLING 12-MONTH RETURN    │   ROLLING 12-MONTH VOLATILITY           │
├──────────────────────────────────────────────────────────────────────┤
│ BACKTESTED METRICS                                                   │  maths in
│ CAGR · vol · Sharpe · Sortino · max DD · Calmar · VaR · CVaR · …     │    core/backtest.py
└──────────────────────────────────────────────────────────────────────┘
```

### Page 3 — Capital Market Assumptions

```
[EDITED] CMA edited for this session only — …           app.py _render_session_banner()
INPUTS / Capital market assumptions                     ui/page_cma.py  render()
(USD) SGD EUR GBP                                       settings.toml  currencies
  Tab "Assumptions"        editable ER + volatility     ui/page_cma.py  _assumptions_tab()
  Tab "Correlation matrix" heatmap, read-only           ui/page_cma.py  _correlation_tab()
  Tab "Change log"         this session's edits         ui/page_cma.py  _change_log_tab()
```

---

## 6. The change cookbook

Find your task in the left column. The right column is the **only** file you
need to touch unless stated otherwise.

### 6.1 Appearance

| I want to… | Open this | What to do |
|---|---|---|
| **Change the maroon to another colour** | `ui/css/01_variables.css` | Change `--accent`, `--accent-soft`, `--accent-wash`. Charts follow automatically — `ui/theme.py` reads this file. |
| Change the black header bars | `ui/css/01_variables.css` | `--black` |
| Change the row-shading grey | `ui/css/01_variables.css` | `--zebra` |
| Change the page background | `ui/css/01_variables.css` | `--bg` |
| Change fonts | `ui/css/01_variables.css` | `--sans`, `--serif`, and the `@import` line at the top |
| Make the page wider/narrower | `ui/css/03_layout_and_headings.css` | `.block-container { max-width }` |
| Make the big table's font bigger | `ui/css/05_house_table.css` | `table.house.spaced { font-size }` — that's the default 2-column view. `table.house { font-size }` is the 4-column view. |
| Widen the gap between RP groups | `ui/css/05_house_table.css` | `td.gut, th.gut { min-width, width }` |
| Change the gap between table sections | `ui/css/05_house_table.css` | `tr.sep td { height }` and the `.spaced` version below it |
| Change the black rule thickness | `ui/css/05_house_table.css` | `tr.sep td { border-bottom }` |
| Change a group's colour in charts | `settings.toml` | `[[subgroups]]` / `[[groups]]` → `color` |
| Change chart line colours on the frontier | `ui/theme.py` | `SCENARIO_LINE` |
| **Change the sidebar colour / width** | `ui/css/06_sidebar.css` | `[data-testid="stSidebar"] { width }`; the colour is `--black` in `01_variables.css` |
| Change the active nav item's colour | `ui/css/01_variables.css` | `--accent` (the active item is `button[kind="primary"]`) |
| **Sidebar text overlapping itself** | `ui/css/06_sidebar.css` | Two known causes, both commented in that file: a `line-height` below 1.3 on the Fraunces wordmark, and using `:first-of-type` on `.nav-group`. See §10.8. |
| Change the sidebar group headings (GUIDE / ANALYSIS / INPUTS) | `ui/sidebar_nav.py` | `NAV_GROUPS` — the dict key is the heading |
| Restyle a Streamlit control | `ui/css/04_widgets.css` | Each widget has its own labelled block |
| A Streamlit element reappeared after upgrading | `ui/css/02_streamlit_reset.css` | Right-click it → Inspect → copy its `data-testid` → add it to the list |

### 6.2 The taxonomy (asset classes and groupings)

All in **`settings.toml`**. Restart the app afterwards (see §10.2).

| I want to… | What to do |
|---|---|
| **Add an asset class** | Add an `[[asset_classes]]` block with `code`, `name`, `subgroup`, `group`. Then add that code to `data/model_portfolios.xlsx` and to **every** `data/cma/cma_*.csv` and `corr_*.csv`. |
| **Remove an asset class** | Delete its `[[asset_classes]]` block and its rows from the data files. |
| **Reorder the table rows** | Reorder the `[[asset_classes]]` blocks. Display order = file order. |
| Rename an asset class label | Change `name`. Leave `code` alone — `code` is what the data files use. |
| **Move a code to a different sub-group** | Change its `subgroup`. |
| **Move a code to a different group** | Change its `group`. These two are independent — changing one does not change the other. |
| Add/rename a sub-group | Add or edit a `[[subgroups]]` block, then point some `[[asset_classes]].subgroup` at it. |
| Add/rename a group | Same, with `[[groups]]`. |
| Change a risk profile's label | `[[risk_profiles]]` → `label` (long) or `short` (the "RP3" in the table header). |
| **Add a 6th risk profile** | Add an `[[risk_profiles]]` block with `id = 6`, and add `risk_profile = 6` rows to the Excel file. The table grows a column group automatically. |

### 6.3 Scenarios (ESAA / DSAA 2026 / DSAA 2025)

| I want to… | What to do |
|---|---|
| **Roll forward a year** (add DSAA 2027) | In `settings.toml` `[scenarios]`: add `"DSAA 2027"` to `columns` and set `change = ["DSAA 2027", "DSAA 2026"]`. Add a `DSAA 2027` column to `data/model_portfolios.xlsx`. Add a colour to `SCENARIO_LINE` in `ui/theme.py` if you now have more than 5 scenarios. |
| Rename a scenario | Change it in `[scenarios].columns` **and** the column header in the Excel file — they must match exactly. Also update `change` and `benchmark` if they referenced it. |
| **Change what "Change" means** | `[scenarios].change` — it is always `first − second`. |
| **Change the Tracking Error benchmark** | `[scenarios].benchmark`. That scenario's own tracking error is then always 0. |
| Change which 2 columns show by default | `ui/page_portfolios.py` → `visible_columns` (currently `cfg.scenarios[:2]`) |

### 6.4 The maths

| I want to… | Open this |
|---|---|
| **Check or change any formula** | `core/analytics.py` — the docstring lists every formula |
| Change the risk-free rate used for Sharpe | `settings.toml` `[metrics].risk_free` (blank = lowest-volatility asset) |
| **Add a new metric row** to the table | `core/report_tables.py`: add the name to `METRIC_ROWS` **and** a line in `metrics_block()`. It appears in the house table, the What-if panel and Excel automatically. |
| Change how the frontier is solved | `core/frontier.py` |
| Allow shorting on the frontier | `core/frontier.py` → `_solve()` → change `bounds=[(0.0, 1.0)]` to e.g. `(-1.0, 1.0)` |
| Cap any single asset on the frontier | Same `bounds`, e.g. `(0.0, 0.25)` for a 25% cap |
| Make the frontier smoother / faster | `settings.toml` `[frontier].points` (120 now; fewer = faster, less accurate gaps) |
| Loosen the "must sum to 100" check | `settings.toml` `[validation].weight_sum_tolerance` |
| **Check or change any backtest formula** | `core/backtest.py` — the docstring lists them all |
| **Change rebalancing** (monthly → quarterly) | `settings.toml` `[backtest].rebalance` — `"M"`, `"Q"`, `"Y"`, or blank for buy-and-hold |
| Change the backtest risk-free rate | `settings.toml` `[backtest].risk_free` (annual %, used for Sharpe and Sortino) |
| Change the VaR confidence level | `settings.toml` `[backtest].var_confidence` (0.95 → 95%) |
| Change the rolling-chart window | `settings.toml` `[backtest].rolling_months` |
| Change the default period shown | `settings.toml` `[backtest].default_years` |
| **Add a backtest metric** | `core/backtest.py`: add the name to `METRIC_ROWS` **and** a line in `summary_metrics()`. It appears in the table automatically. |
| Add a period preset (e.g. 15Y) | `ui/sections/backtest_controls.py` → `PERIOD_PRESETS` |

### 6.5 Structure and new features

| I want to… | What to do |
|---|---|
| **Add a new section to page 1** | 1. Create `ui/sections/my_section.py` with a `render(...)` function. 2. Import it in `ui/page_portfolios.py`. 3. Add one `my_section.render(...)` line at the bottom of `render()`. |
| **Reorder the sections** | Move those `render(...)` lines around in `ui/page_portfolios.py`. |
| **Remove a section** | Comment out its `render(...)` line. |
| **Add a new chart** | Write a function in `ui/charts.py` that returns a Plotly figure ending in `return style(fig, height)`, then call it from a section with `st.plotly_chart(fig, config=PLOTLY_CONFIG)`. |
| **Add a new page** | 1. Write `ui/page_mypage.py` with `render(cfg, data, store)`. 2. Add `("My page", "mypage")` to `NAV_GROUPS` in `ui/sidebar_nav.py`. 3. Add one `elif` branch in `app.py` `main()`. |
| Reorder / regroup the nav | `ui/sidebar_nav.py` → `NAV_GROUPS` |
| Move a page between Analysis and Inputs | `ui/sidebar_nav.py` → `NAV_GROUPS` |
| Change what the **small** Excel download contains | `core/report_tables.py` → `stacked_block()` (layout) or `core/excel_export.py` (sheets) |
| **Change what the full report contains** | `core/report_export.py` → `build_workbook()`. One `_sheet(...)` call per sheet; the README sheet is written last and moved to the front. |
| **Feed the full report something new** | `ui/report_builder.py` → `build()`. That file is the only part of the report that may touch `st.session_state`; `core/report_export.py` must stay Streamlit-free. |
| Move or relabel the report button | `ui/sidebar_nav.py` → `_render_report_button()` |
| Change the report filename | `ui/report_builder.py` → the last two lines of `build()` |
| **Edit the wording of the Start here page** | `ui/page_start.py` — it is all literal text |
| Land users on a different page | `ui/sidebar_nav.py` → `DEFAULT_PAGE` |
| Change which columns the What-if editor exposes | `ui/sections/whatif_editor.py` → `columns` |

### 6.6 Data and deployment

| I want to… | What to do |
|---|---|
| **Put my real data in** | Replace the files in `data/` keeping the schema in §8. Press "↻ Reload data" or restart. |
| Point at a different data folder | `settings.toml` `[data]` |
| **Read from a database instead of files** | `core/data_loader.py` — replace the file reads, return the same `LoadResult` shape, and nothing else changes |
| **Make CMA edits permanent and shared** | `core/cma_store.py` — write `self.overrides` to a JSON file in `_save_overrides()` and read it in `__init__`. ⚠ Then every user shares one CMA, which the current design deliberately avoids. |
| Add a currency | Add it to `settings.toml` `currencies`, add `data/cma/cma_<CCY>.csv` + `corr_<CCY>.csv` **and** `data/history/prices_<CCY>.csv`, then use that code in the `currency` column of the Excel file |
| **Put in real price history** | Replace `data/history/prices_<CCY>.csv` keeping the schema in §8. Press "↻ Reload data". |
| An asset class has no price history | Nothing to do — the Backtesting page warns, excludes it, and scales the other weights up to 100%. Add the column when you have it. |
| Set who appears in the change log | Set the `CIO_DASHBOARD_USER` environment variable, or edit `current_user()` in `core/cma_store.py` |
| Change the browser tab title | `settings.toml` `[app].title` |

---

## 7. Reference: `settings.toml`

Everything that is not data. **The app must be restarted after editing this
file** — see §10.2.

| Key | Meaning |
|---|---|
| `currencies` | Which CMA file sets exist. Needs `cma_<CCY>.csv` + `corr_<CCY>.csv` for each. |
| `[app].title` | Browser tab title |
| `[app].subtitle` | The small grey text next to the logo |
| `[data].model_portfolios` | Path to the portfolio file (`.xlsx` or `.csv`) |
| `[data].cma_dir` | Folder holding the CMA files |
| `[data].history_dir` | Folder holding the daily price files |
| `[scenarios].columns` | The weight column names, in display order. **Must match the Excel headers exactly.** |
| `[scenarios].change` | `[newer, older]` — the Change column is `newer − older` |
| `[scenarios].benchmark` | Tracking error is measured against this scenario |
| `[metrics].risk_free` | Sharpe's risk-free rate. Blank = use the lowest-volatility asset. |
| `[frontier].points` | How many points to solve along the frontier (120) |
| `[frontier].risk_free` | Risk-free rate for the max-Sharpe marker |
| `[backtest].rebalance` | `"M"` monthly, `"Q"` quarterly, `"Y"` yearly, blank = buy and hold |
| `[backtest].risk_free` | Annual %, used for backtest Sharpe and Sortino |
| `[backtest].var_confidence` | `0.95` → the table reports monthly VaR/CVaR at 95% |
| `[backtest].rolling_months` | Window for the rolling return / volatility charts |
| `[backtest].default_years` | How much history the Backtesting page shows on opening |
| `[validation].weight_sum_tolerance` | How far from 100 a scenario may sum before you get a warning |
| `[validation].allow_negative_weights` | `false` makes negative weights a fatal error |
| `[[risk_profiles]]` | `id` (matches the Excel column), `label`, `short` |
| `[[subgroups]]` | Level-2 summary rows: `name`, `color`. Order = display order. |
| `[[groups]]` | Level-1 summary rows: `name`, `color`. Order = display order. |
| `[[asset_classes]]` | `code` (matches the data files), `name`, `subgroup`, `group`. Order = row order. |

---

## 8. Reference: the data files

### `data/model_portfolios.xlsx`

One row per **(model, risk profile, asset code)**.

| Column | Notes |
|---|---|
| `model_id` | Stable id, e.g. `eur_emea`. Used for the Excel filename. |
| `model_name` | What the dropdown shows. Put the currency/region in here. |
| `currency` | One of `settings.toml` `currencies`. Picks the CMA. |
| `risk_profile` | Integer matching a `[[risk_profiles]].id` |
| `code` | Asset code matching an `[[asset_classes]].code` |
| `ESAA` | Weight in **percent**. Per (model, profile) must sum to 100. |
| `DSAA 2026` | ditto |
| `DSAA 2025` | ditto |

The three weight columns are named by `[scenarios].columns` — rename them in
both places together.

### `data/cma/cma_<CCY>.csv`

| Column | Notes |
|---|---|
| `code` | Asset code |
| `expected_return` | **Percent.** `7.0` means 7.0%, not 0.07 |
| `volatility` | Percent, same convention |

### `data/cma/corr_<CCY>.csv`

Square correlation matrix. First column is `code`; the remaining column headers
are the same codes. Should be positive semi-definite — the smoke test checks
this and will tell you if it is not.

### `data/history/prices_<CCY>.csv`  *(the Backtesting page)*

Daily **total-return index levels** — not raw prices, not returns. One file per
currency.

```
date,EME,DME,Gov,Infl,EMD_L,...        <- one column per asset code
2007-06-07,100.0,100.0,100.0,...       <- levels, any starting value
2007-06-08,100.62,100.21,99.98,...
```

| Rule | Why |
|---|---|
| `date` ascending, any pandas-readable format | it is parsed with `pd.to_datetime` |
| Column names must equal `[[asset_classes]].code` | that is how weights are matched to prices |
| **Total-return** levels (income reinvested) | otherwise bond and dividend returns are understated |
| Blanks are fine | different markets have different holidays; they are forward-filled |
| A missing **column** is fine | the page warns, excludes that asset, and scales the rest to 100% |

20 years of daily data is about 5,000 rows and 750 KB per currency. The files
are only read when you open the Backtesting page, and are cached after that.

> **Units are the single most common mistake.** Everything is percent, never
> fractions. If a number comes out 100× too big or small, this is why.

---

## 9. How data flows through the app

```
  settings.toml                data/model_portfolios.xlsx      data/cma/*.csv
        │                                │                           │
        ▼                                └───────────┬───────────────┘
 core/config.py                                      ▼
   → the `cfg` object                        core/data_loader.py
        │                                     → LoadResult (.portfolios,
        │                                        .cma, .corr, warnings, errors)
        │                                              │
        │                                              ▼
        │                                    core/cma_store.py
        │                                     imported CMA + THIS SESSION's edits
        │                                     → store.effective("EUR")
        │                                              │
        └──────────────┬───────────────────────────────┘
                       ▼
        ui/weight_edits.py        the session's editable copy of the weights
                       │          (seeded from file, mutated by the What-if editor)
                       ▼
        core/taxonomy.py          16 codes → 6 sub-groups → 4 groups
        core/analytics.py         return, volatility, Sharpe, tracking error
                       │
                       ▼
        core/report_tables.py     the four blocks, with the Change column
                       │
        ┌──────────────┼──────────────────┬────────────────────┐
        ▼              ▼                  ▼                    ▼
  house_table.py  whatif_editor.py  charts_section.py   frontier_section.py
   (HTML table)   (editor+metrics)   (donut+bars)       (+ core/frontier.py)
        │              │                  │                    │
        └──────────────┴────────┬─────────┴────────────────────┘
                                ▼
                         core/excel_export.py → the .xlsx download
```

The Backtesting page is a separate, shorter chain — it needs prices, not the
CMA:

```
  data/history/prices_<CCY>.csv
              │
              ▼
  core/history_loader.py        reads + cleans; reports missing asset classes
              │
              ▼
  ui/page_backtest.py           picks which weight vectors to test
              │                 (scenarios / risk profiles / your custom one)
              ▼
  core/backtest.py              align_weights -> run -> metrics_frame
              │
              ▼
  ui/sections/backtest_results.py   growth, drawdown, rolling, metrics table
```

The full report joins both chains at the end. It is the only thing in the app
that runs *everything* at once:

```
  sidebar "⬇ Build full report"
              │
              ▼
  ui/report_builder.py     reads st.session_state: which model is selected,
              │            which weights were edited, which CMA is in force
              ├──────────► core/frontier.py      (re-solved)
              ├──────────► core/report_tables.py (the house table, wide)
              ├──────────► core/backtest.py      (all 5 RP x 3 scenarios,
              │                                   over the FULL history)
              ▼
  core/report_export.py    → 17 sheets of .xlsx bytes, 3 native Excel charts
              │
              ▼
  sidebar "⬇ Download .xlsx"
```

Note what it does *not* do: it never reads the Backtesting page's period or
comparison controls. A downloaded report is deliberately complete rather than
a snapshot of whatever one screen happens to be showing.

The key thing: **the house table, the charts, the frontier, both Excel exports
and the backtest all read the same session weights.** That is why editing one
number updates everything at once.

---

## 10. Eight things that will surprise you

### 10.1 The house table is hand-written HTML, not `st.dataframe`

Streamlit draws dataframes onto an HTML `<canvas>`. A canvas cannot have
alternating row colours, black section rules, merged "RP1"/"RP2" header bars,
or a white gutter column — **no CSS can reach inside it.**

So `ui/sections/house_table.py` builds a plain `<table>` as a string, and
`ui/css/05_house_table.css` styles it. It still copy-pastes into Excel cleanly.

If you want to change the table's *structure*, edit the Python. If you want to
change its *appearance*, edit the CSS. The class names are documented at the
top of both files.

### 10.2 Editing `settings.toml` needs a restart; editing `data/` does not

`core/config.py` caches the config with `@lru_cache` for the life of the
process.

- **Changed `data/`?** → press "↻ Reload data" in the top bar. That is all.
- **Changed `settings.toml`?** → stop the app (Ctrl-C) and start it again.
- **Changed a `.py` file?** → restart. (Streamlit re-runs `app.py` on every
  interaction, but does not re-import modules.)
- **Changed a `.css` file?** → just refresh the browser. The CSS is re-read on
  every page load.

### 10.3 Why an edit in the What-if box updates the table *above* it

Streamlit runs your script top to bottom. The house table is drawn *before* the
editor, so by the time Streamlit reaches the editor it is too late to change
the table.

`ui/weight_edits.py` → `fold_in_pending_edits()` solves this. Before drawing
anything, it reads the editor's raw pending state out of `st.session_state`
and applies it to our own copy of the weights. Everything drawn afterwards is
therefore current.

That function maps *row number* → *asset code* using `cfg.asset_codes`. **If
you ever sort or filter the rows in that editor, this mapping breaks.** Sort a
copy for display only. The full explanation is in that file's header.

### 10.4 CMA edits are per-session on purpose

`core/cma_store.py` keeps overrides in `st.session_state`, never on disk. If
they were saved, one analyst testing a scenario would silently change every
other user's numbers.

To change the assumptions *for everyone*, edit `data/cma/cma_<CCY>.csv` and
press "↻ Reload data".

### 10.5 The backtest rebalances monthly, and that is a real assumption

`core/backtest.py` resets the portfolio to its target weights at the start of
every month; within the month the weights drift with the market. Change it in
`settings.toml` `[backtest].rebalance`.

This matters more than it looks. Buy-and-hold over 20 years lets equity grow
into a much larger share, so a "balanced" portfolio quietly becomes an
aggressive one and the drawdown numbers change substantially. If your real
models rebalance quarterly, set `"Q"` before you compare the output to
anything official.

### 10.6 Model portfolios sit *below* the efficient frontier — that is correct

The frontier assumes every asset class is directly investable at exactly its
CMA, long-only, fully invested, with no other constraints. Real model
portfolios carry diversification rules, liquidity limits, home bias and
governance constraints.

The "return gap" column is the price of those constraints. A gap of 1–2
percentage points is normal. A gap of **zero or negative** would mean something
is wrong — the smoke test checks for exactly that.

### 10.7 The report button builds first and downloads second

Streamlit's `st.download_button` has to be handed the finished bytes at the
moment it is *drawn*. There is no "generate on click". Since the report takes
several seconds to build, wiring it up directly would mean rebuilding it on
every single rerun — every dropdown change, every edited weight — and the
whole app would crawl.

So `ui/sidebar_nav.py` `_render_report_button()` does it in two steps:

```
click "⬇ Build full report"  ->  ui/report_builder.py build()
                                 bytes stashed in st.session_state[REPORT_KEY]
                                 rerun
                             ->  "⬇ Download .xlsx (750 KB)" now appears
```

If you ever see only the build button after clicking it, the build raised —
the error is shown in the sidebar.

**Speed.** The build is dominated by the backtests: 5 risk profiles x 3
scenarios = 15 portfolios over 20 years of daily data. This used to take 19
seconds because `core/backtest.py` looped over each month in Python; it now
does the same arithmetic with one grouped `cumprod` and takes about 1 second,
for a whole report in roughly 8. `scripts/smoke_test.py` reimplements the old
loop and asserts the two agree to the last bit — **if you touch
`_rebalanced_daily_returns()`, keep that check passing.**

### 10.8 Three CSS traps around the sidebar

All three produced a visible bug at some point, and all three are commented in
the CSS. They are worth knowing before you next edit it.

**1. `:first-of-type` matches every `.nav-group`.** Streamlit wraps *each*
`st.markdown()` call in its own container. So the GUIDE, ANALYSIS and INPUTS
headings are not siblings — each is the only child of its own wrapper, which
makes every one of them the "first of type". A rule meant to remove the top
margin from the first heading silently removed it from all of them, and the
headings collided with the buttons above. Use a plain `margin` on
`.nav-group`, not a `:first-of-type` exception.

**2. Display serifs need room.** The `CIO.` wordmark is set in Fraunces, a
display serif whose glyphs paint outside a tight line box. At `line-height:
1.15` the descenders overlapped the line below. Keep `.nav-brand .mark` at
**1.3 or more**. The same applies if you swap in another display face.

**3. Hiding Streamlit's header traps anyone who collapses the sidebar.**
`ui/css/02_streamlit_reset.css` used to carry
`header[data-testid="stHeader"] { display: none }`. That looked right, but the
`»` arrow that brings the sidebar *back* lives inside that header — so once a
user collapsed the navigation, their only way back was to reload with a fresh
session. A `display:none` parent cannot be overridden by a rule on its child,
so the header has to stay in the layout.

It is now transparent, `pointer-events: none` (clicks fall straight through to
the page), and everything inside it is hidden by name — Deploy, the hamburger,
the status widget — *except* `stExpandSidebarButton`, which gets
`pointer-events: auto` back. It also keeps `height: 3rem`: the header is
`position: absolute`, so that costs no layout space, but at height 0 the
toolbar centres the arrow on `y = 0` and half of it sits above the window.

If you ever add something to that hidden list, hide the **specific**
`data-testid`, not the header.

More generally, when a Streamlit control ignores your CSS: right-click it in
the browser, Inspect, and read the real `data-testid`. Streamlit's class names
are generated and change between versions — the `data-testid` attributes are
the stable hook. Two that are easy to get wrong:

| What you want to style | The selector that actually works |
|---|---|
| A segmented control's selected button | `[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected="true"]` |
| A sidebar button's *label* (e.g. to left-align it) | `[data-testid="stSidebar"] .stButton > button > div` — Streamlit centres the label with an inner flex div, so styling the `button` alone does nothing |

---

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| App won't start, `ModuleNotFoundError` | Not using the venv | Use `.venv/Scripts/python.exe -m streamlit run app.py`, not bare `streamlit` |
| "Data could not be loaded" | Missing file or column | The red list names the exact problem. Check §8. |
| "Data checks — N note(s)" expander | Non-fatal warnings | Usually weights not summing to 100, or a code missing from the CMA |
| Efficient frontier section shows an install message | SciPy missing | `.venv/Scripts/python.exe -m pip install scipy` |
| A number looks 100× off | Percent vs fraction | Data must be `7.0` for 7%, not `0.07`. See §8. |
| Edited `settings.toml`, nothing changed | Config is cached | Restart the app. §10.2 |
| Edited a `.py` file, nothing changed | Modules are cached | Restart the app. §10.2 |
| Edited CSS, nothing changed | Browser cache | Hard refresh (Ctrl-Shift-R) |
| Table shows a code but all zeros | Code in `settings.toml` but not in the data | Add it to the Excel file, or remove it from the config |
| Asset class missing from the table entirely | In the data but not in `settings.toml` | Add an `[[asset_classes]]` block. The "Data checks" expander warns about this. |
| Streamlit's hamburger/toolbar reappeared | Streamlit renamed a `data-testid` | §6.1, last row |
| Everything looks unstyled | A CSS file has a syntax error | Check the newest edit in `ui/css/`; one bad `{` kills the rest of that file |
| Weights no longer sum to 100 warning in What-if | You edited a weight without offsetting another | Expected — it's a scratchpad. "↺ Reset edits" restores. |
| Frontier is very slow | `[frontier].points` too high | Lower it, or check the `@st.cache_data` decorator is still on `_solve_frontier` |
| Backtesting page says it needs price history | `data/history/` empty or wrong filename | Run `scripts/generate_history_data.py`, or add `prices_<CCY>.csv`. The error names the exact path it looked for. |
| "No price history for X, Y" warning | Those asset codes have no column in the price file | Add the columns, or ignore it — they are excluded and the other weights scale to 100% |
| Backtest returns look far too high/low | Price file is not total-return, or is in the wrong units | Levels must be an index (income reinvested), not raw prices and not returns. §8. |
| Backtest CAGR disagrees with the CMA | Expected — CMA is forward-looking arithmetic, backtest is realised geometric | Geometric return is always below arithmetic by roughly ½σ² |
| Two backtest lines sit on top of each other | ESAA and DSAA differ by only a point or two of weight | That *is* the finding. Click a legend entry to isolate one. |
| Sidebar disappeared | A CSS edit re-hid it | Check `ui/css/02_streamlit_reset.css` does not list `stSidebar` |
| Collapsed the sidebar and cannot get it back | The `»` arrow lives in Streamlit's header — something re-hid it | §10.8 trap 3. Reload the page as a stopgap. |
| Sidebar text sits on top of other text | A `:first-of-type` rule, or too tight a `line-height` on the wordmark | §10.8 — both traps are commented in `ui/css/06_sidebar.css` |
| Sidebar nav labels are centred, not left-aligned | Streamlit centres the label in an inner flex `div` | Style `.stButton > button > div`, not the `button`. §10.8 |
| Clicked "Build full report", nothing downloaded | The build raised | The error prints in the sidebar. Most often SciPy missing (no frontier sheets) or no `data/history/` file |
| The report takes much longer than ~10 seconds | `_rebalanced_daily_returns()` was changed back to a Python loop | §10.7. Run the smoke test — it checks this |
| The report is missing the backtest sheets | No price history for that model's currency | Add `data/history/prices_<CCY>.csv`. The README sheet inside the report says so too |
| The report ignores a weight I edited | You edited on the Backtesting page's *custom* portfolio | Only the Portfolios page's What-if edits go into the report — that is `ui/weight_edits.py` state |
| "Start here" page is blank | `ui/page_start.py` raised | It reads only `data.portfolios` for a count; check the Data checks expander |

**When in doubt, run the smoke test.** It tells you which half of the codebase
the problem is in.

---

## 12. Glossary

| Term | Meaning |
|---|---|
| **CMA** | Capital Market Assumptions — expected return, volatility and correlations per asset class |
| **ESAA** | The strategic (anchor) asset allocation |
| **DSAA 2026** | The dynamic/tactical allocation for that year |
| **Change** | `DSAA 2026 − DSAA 2025` — the year-on-year move. Configurable. |
| **RP1…RP5** | Risk profiles, conservative → aggressive |
| **Sub-group** | The 6-way summary: Equity, Risky FI, Defensive FI, liquid alts, illiq alts, Cash |
| **Group** | The 4-way summary: Equity, Fixed Income, Alternatives, Cash |
| **Tracking Error** | √((w−b)ᵀΣ(w−b)) — how far a scenario is from the benchmark scenario |
| **GMV** | Global Minimum Variance — the lowest-risk portfolio on the frontier |
| **Max Sharpe / tangency** | The best return-per-unit-of-risk point on the frontier |
| **Return gap** | Extra return the frontier offers at a portfolio's own risk level |
| **Diversification ratio** | (weighted average vol) ÷ (portfolio vol). 1.0 = no diversification benefit |
| **Effective number of bets** | How many genuinely independent risk positions the portfolio holds |
| **pp** | Percentage points (a difference between two percentages) |
| **CAGR** | Compound annual growth rate — the realised annualised return |
| **Max drawdown** | Worst peak-to-trough fall over the period |
| **VaR 95% (monthly)** | The monthly loss only 5% of months are worse than |
| **CVaR 95%** | The *average* loss in that worst 5% of months. Always ≤ VaR. |
| **Sortino** | Like Sharpe but only penalising downside volatility |
| **Calmar** | CAGR ÷ |max drawdown| — return per unit of worst-case pain |
| **Rebalancing** | Resetting drifted weights back to target. Monthly here. |
| **Total-return index** | A price series with income reinvested |
| **House format / house table** | The RP1–RP5 layout on the Portfolios page |
| **Full report** | The 17-sheet Excel file built by the sidebar button. Not to be confused with the small per-RP download under the house table. |
| `cfg` | The config object from `core/config.py` — appears in almost every function |
| `data` / `LoadResult` | Everything read from `data/`, from `core/data_loader.py` |
| `store` | The `CmaStore` — imported CMA plus this session's edits |
| **weights matrix** | DataFrame: index = asset code, columns = scenarios, values = percent |

---

## One last thing

The fastest way to find anything:

0. If you are a *user* rather than a maintainer, the app's own **Start here**
   page answers most questions. This file is for changing the code.
1. Open `docs/page-1-portfolios.svg` — find the region of the screen you care
   about, read the filename on it.
2. Open that file — read the header block at the top.
3. If you're changing a number, you're in `core/`. If you're changing how it
   looks, you're in `ui/`.
4. Run `scripts/smoke_test.py` before you trust the result.
