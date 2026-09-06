# CIO Model Portfolio Dashboard

A two-page Streamlit dashboard for CIO model portfolios: the RP1–RP5 house
table with editable weights, and the capital market assumptions behind it.
Re-skinned in maroon and black — no sidebar, no default Streamlit look.

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
.venv/Scripts/python.exe scripts/smoke_test.py           # 46 checks, ~30s. Run after every change.
.venv/Scripts/python.exe scripts/generate_sample_data.py # rebuild the demo data (OVERWRITES data/)
```

---

## What it does

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

**Page 2 — Capital Market Assumptions.** Expected return, volatility and the
correlation matrix, per currency. Editable — but **edits are private to your
browser session and are never saved**. A new session always starts from the
files in `data/`.

---

## Layout

```
app.py            entry point
settings.toml     ALL configuration (asset classes, groups, scenarios, profiles)
core/             pure Python — data loading, taxonomy, maths, exports
ui/               all Streamlit — pages, sections, charts, CSS
data/             your data: model_portfolios.xlsx + cma/*.csv
scripts/          smoke test + sample data generator
docs/             annotated diagrams of both pages
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
