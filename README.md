# CIO Model Portfolio Dashboard

A four-page Streamlit dashboard for CIO model portfolios: a plain-English
guide page, the RP1–RP5 house table with editable weights, historical
backtesting, and the capital market assumptions behind both. Everything on
screen can be pulled down as a single multi-sheet Excel report. Maroon-and-
black theme with a dark left-hand nav.

> ### ➜ New here, or coming back after a while? Read **[HOW_TO_NAVIGATE.md](HOW_TO_NAVIGATE.md)**
> It is the full manual: what every file does, and exactly which file to open
> for any change you want to make. This README is only the quick start.

---

## Quick start

Requires **Python 3.11+**.

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

```bash
.venv/Scripts/python.exe -m streamlit run app.py
```

(macOS/Linux: use `.venv/bin/python` instead of `.venv/Scripts/python.exe`.)

Two other commands:

```bash
.venv/Scripts/python.exe scripts/smoke_test.py           # 67 checks, ~40s. Run after every change.
.venv/Scripts/python.exe scripts/generate_sample_data.py # rebuild ALL demo data incl. price history (OVERWRITES data/)
```

---

## What it does

**Page 0 — Start here.** The landing page: a two-minute, plain-English guide
to the other three, aimed at whoever is *using* the dashboard rather than
maintaining it. Static text only, so it loads even if the data files are
broken.

**Page 1 — Portfolios.** Pick one model portfolio. Its five risk profiles are
shown side by side in the house format:

| block | rows |
|---|---|
| Granular allocation | the 16 asset-class codes |
| Sub-group summary | Equity / Risky FI / Defensive FI / liquid alts / illiq alts / Cash |
| Group summary | Equity / Fixed Income / Alternatives / Cash |
| Risk-Return Metrics | Exp Ret, Exp Vol, Exp Sharpe, Tracking Error |

Each block has one column per scenario (ESAA, DSAA 2026, DSAA 2025) plus a
Change column. Below the table: a **What-if editor** that recalculates
everything live, **charts**, and the **efficient frontier** with each
scenario's RP1–RP5 plotted on it. One-click Excel export.

**Page 2 — Backtesting.** Runs the same portfolios through 20 years of daily
price history, rebalanced monthly. Compare the three scenarios for one risk
profile, all five risk profiles for one scenario, or **build your own portfolio**
and test it alongside. Any period from 1Y to the full history. Growth,
drawdown and rolling 12-month return/volatility charts, plus a full metrics
table — CAGR, ann. volatility, Sharpe, Sortino, max drawdown, Calmar, monthly
VaR/CVaR, best/worst month, % positive months, tracking error. Asset classes
with no price history are reported and excluded rather than silently ignored.

**Page 3 — Capital Market Assumptions.** Expected return, volatility and the
correlation matrix, per currency. Editable — but **edits are private to your
browser session and are never saved**. A new session always starts from the
files in `data/`.

**Download full report** (in the sidebar, on every page). Builds one `.xlsx`
with 17 named sheets covering the selected model end to end: the allocation
table per risk profile and combined, risk-return metrics, the CMA and
correlation matrix, the efficient frontier and each portfolio's gap to it, and
every backtest series and metric — with native Excel line and scatter charts
on the growth, drawdown and frontier sheets. It includes any weight or CMA
edits made in the session, and takes about 8 seconds to build.

Because nothing a user changes is ever written to disk, this report is the
only way to keep anything.

---

## Layout

```
app.py            entry point
settings.toml     ALL configuration (asset classes, groups, scenarios, profiles)
core/             pure Python — data loading, taxonomy, analytics, frontier,
                  backtest, exports
ui/               all Streamlit — sidebar nav, pages, sections, charts, CSS
data/             your data: model_portfolios.xlsx + cma/*.csv + history/*.csv
scripts/          smoke test + sample data generators
docs/             annotated diagrams of the pages
```

Two rules explain the whole structure:

1. **`core/` never imports Streamlit; `ui/` never does maths.** So the smoke
   test can verify everything important without a browser.
2. **Adding an asset class, group, scenario or risk profile is a
   `settings.toml` edit, not a code edit.**

---

## Your data

Replace the files in `data/`, keeping these schemas
(full detail in [HOW_TO_NAVIGATE.md §8](HOW_TO_NAVIGATE.md#8-reference-the-data-files)):

**`data/model_portfolios.xlsx`** — one row per (model, risk profile, asset code):

`model_id`, `model_name`, `currency`, `risk_profile`, `code`, `ESAA`, `DSAA 2026`, `DSAA 2025`

**`data/cma/cma_<CCY>.csv`** — `code`, `expected_return`, `volatility`

**`data/cma/corr_<CCY>.csv`** — square correlation matrix, first column `code`

**`data/history/prices_<CCY>.csv`** — daily total-return index levels:
`date` + one column per asset code (for the Backtesting page)

All figures are in **percent** (`7.0` means 7.0%, not 0.07).

After changing data, press **↻ Reload data** in the app. After changing
`settings.toml` or any `.py`, restart the app.

---

## Notes

- Colours live in **one** place: `ui/css/01_variables.css`. `ui/theme.py` reads
  that file so the charts and the CSS can never drift apart.
- SciPy is only needed for the efficient frontier. Without it the rest of the
  app still runs.
- Model portfolios sitting 1–2 pp below the frontier is expected — the frontier
  has none of the real-world constraints a model portfolio carries.
- All figures are illustrative until you drop in real data.
