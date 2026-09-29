"""
=============================================================================
 SAMPLE DATA GENERATOR  —  makes fake but realistic data/ files
=============================================================================

    .venv/Scripts/python.exe scripts/generate_sample_data.py

WHAT THIS FILE DOES
    Writes a complete, self-consistent set of demo files so the app runs
    straight out of the box, and so you always have something to compare
    against if your real data misbehaves.

    IT OVERWRITES:
        data/model_portfolios.xlsx
        data/cma/cma_<CCY>.csv      and  data/cma/corr_<CCY>.csv
        data/history/prices_<CCY>.csv   (by calling generate_history_data.py
                                         at the end - one command does it all)

    ==> Once you have put YOUR OWN data in data/, do not run this again —
        it will overwrite it. Keep a copy of your real files elsewhere.

WHAT IT PRODUCES
    10 model portfolios across 4 currencies (USD, SGD, EUR, GBP)
    5 risk profiles each, 16 asset classes, 3 scenarios
    A plausible correlation matrix, forced to be positive semi-definite

    Every (model, risk profile, scenario) is normalised to exactly 100.

THE USEFUL PART IF YOU ARE WIRING IN REAL DATA
    Read the column names in the `records.append({...})` block near the
    bottom — that is exactly the schema data/model_portfolios.xlsx must have.
    Same for the CMA files in the "write CMA files" block.

HOW THE FAKE NUMBERS ARE BUILT
    GLIDE   target Equity/Fixed Income/Alternatives/Cash split per risk profile
    SPLIT   how each of those groups divides across asset codes
    MODELS  the list of models, each with a currency and a style tilt
    ESAA        = GLIDE x SPLIT (+ the model's tilt)
    DSAA 2026   = ESAA + a pro-risk tactical shift
    DSAA 2025   = ESAA + a more defensive shift

NO STREAMLIT IN THIS FILE.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CMA = os.path.join(DATA, "cma")
os.makedirs(CMA, exist_ok=True)
rng = np.random.default_rng(7)

SCENARIOS = ["ESAA", "DSAA 2026", "DSAA 2025"]

# code, name, subgroup, group, USD expected return %, volatility %
ASSETS = [
    ("EME",   "Emerging Markets Equity",        "Equity",       "Equity",        8.2, 21.0),
    ("DME",   "Developed Markets Equity",        "Equity",       "Equity",        7.1, 16.0),
    ("Gov",   "Government Bonds",                "Defensive FI", "Fixed Income",  4.0,  5.0),
    ("Infl",  "Inflation-Linked Bonds",          "Defensive FI", "Fixed Income",  3.9,  6.0),
    ("EMD_L", "EM Debt - Local Currency",        "Risky FI",     "Fixed Income",  6.8, 12.0),
    ("EMD_H", "EM Debt - Hard Currency",         "Risky FI",     "Fixed Income",  6.4,  9.0),
    ("EMD_C", "EM Debt - Corporate",             "Risky FI",     "Fixed Income",  6.2,  8.5),
    ("IG",    "Investment Grade Credit",         "Risky FI",     "Fixed Income",  4.9,  6.0),
    ("HYD",   "High Yield Debt",                 "Risky FI",     "Fixed Income",  6.3, 10.0),
    ("SIG",   "Securitised / Structured Credit", "Risky FI",     "Fixed Income",  5.2,  5.5),
    ("PD",    "Private Debt",                    "illiq alts",   "Alternatives",  8.0, 11.0),
    ("Com",   "Commodities",                     "liquid alts",  "Alternatives",  4.6, 15.0),
    ("RE",    "Real Estate",                     "illiq alts",   "Alternatives",  6.6, 14.0),
    ("PE",    "Private Equity",                  "illiq alts",   "Alternatives", 10.5, 24.0),
    ("HF",    "Hedge Funds",                     "liquid alts",  "Alternatives",  5.2,  7.0),
    ("Cash",  "Cash",                            "Cash",         "Cash",          3.3,  0.6),
]
CODES = [a[0] for a in ASSETS]
GROUP = {a[0]: a[3] for a in ASSETS}

CCY = {"USD": 0.0, "SGD": -0.5, "EUR": -1.2, "GBP": -0.6}   # return shift

# --------------------------------------------------------------------------- #
# correlation matrix                                                         #
# --------------------------------------------------------------------------- #
def base_corr() -> np.ndarray:
    n = len(CODES)
    C = np.eye(n)

    def rho(a: str, b: str) -> float:
        ga, gb = GROUP[a], GROUP[b]
        pair = {a, b}
        if "Cash" in (ga, gb):
            return 0.02
        if ga == gb == "Equity":
            return 0.80
        if ga == "Equity" or gb == "Equity":
            other = b if ga == "Equity" else a
            return {"Gov": -0.10, "Infl": 0.00, "IG": 0.30, "SIG": 0.25,
                    "HYD": 0.65, "EMD_L": 0.60, "EMD_H": 0.50, "EMD_C": 0.50,
                    "PE": 0.75, "HF": 0.50, "RE": 0.55, "Com": 0.25, "PD": 0.50
                    }.get(other, 0.3)
        if ga == gb == "Fixed Income":
            if pair == {"Gov", "Infl"}:
                return 0.75
            if "Gov" in pair:
                return {"IG": 0.55, "SIG": 0.45}.get((pair - {"Gov"}).pop(), 0.15)
            if pair == {"EMD_L", "EMD_H"}:
                return 0.70
            if pair == {"EMD_H", "EMD_C"}:
                return 0.80
            return 0.55
        if ga == gb == "Alternatives":
            if pair == {"PE", "PD"}:
                return 0.55
            if pair == {"RE", "PE"}:
                return 0.50
            if "Com" in pair:
                return 0.15
            return 0.32
        # FI <-> Alternatives
        if "Com" in pair:
            return 0.05
        if pair == {"HYD", "PD"}:
            return 0.60
        return 0.25

    for i in range(n):
        for j in range(i + 1, n):
            v = rho(CODES[i], CODES[j]) + rng.normal(0, 0.02)
            C[i, j] = C[j, i] = float(np.clip(v, -0.95, 0.97))
    return C


def nearest_psd(C: np.ndarray) -> np.ndarray:
    C = (C + C.T) / 2
    vals, vecs = np.linalg.eigh(C)
    C = vecs @ np.diag(np.clip(vals, 1e-4, None)) @ vecs.T
    d = np.sqrt(np.diag(C))
    C = C / np.outer(d, d)
    np.fill_diagonal(C, 1.0)
    return C


CORR = nearest_psd(base_corr())

for ccy, shift in CCY.items():
    rows = [dict(code=c, expected_return=round(er + shift, 2), volatility=vol)
            for c, _n, _s, _g, er, vol in ASSETS]
    pd.DataFrame(rows).to_csv(os.path.join(CMA, f"cma_{ccy}.csv"), index=False)
    cdf = pd.DataFrame(CORR, index=CODES, columns=CODES).round(4)
    cdf.insert(0, "code", CODES)
    cdf.to_csv(os.path.join(CMA, f"corr_{ccy}.csv"), index=False)

# --------------------------------------------------------------------------- #
# model portfolios                                                           #
# --------------------------------------------------------------------------- #
# ESAA group glide path (Equity, Fixed Income, Alternatives, Cash) per RP
GLIDE = {
    1: [12, 60, 20, 8],
    2: [28, 50, 18, 4],
    3: [45, 38, 15, 2],
    4: [62, 24, 12, 2],
    5: [80,  8, 10, 2],
}
GROUP_ORDER = ["Equity", "Fixed Income", "Alternatives", "Cash"]

SPLIT = {
    "Equity": {"EME": 30, "DME": 70},
    "Fixed Income": {"Gov": 26, "Infl": 8, "EMD_L": 8, "EMD_H": 8, "EMD_C": 6,
                     "IG": 22, "HYD": 12, "SIG": 10},
    "Alternatives": {"HF": 34, "RE": 22, "Com": 14, "PE": 18, "PD": 12},
    "Cash": {"Cash": 100},
}

MODELS = [
    ("USD Global Balanced",     "USD", None),
    ("USD Global Sustainable",  "USD", "esg"),
    ("USD APAC",                "USD", "apac"),
    ("USD APAC Income",         "USD", "apac_income"),
    ("SGD APAC",                "SGD", "apac"),
    ("SGD Global",              "SGD", None),
    ("EUR EMEA",                "EUR", "eu"),
    ("EUR EMEA Income",         "EUR", "income"),
    ("GBP UK",                  "GBP", "uk"),
    ("USD US Core",             "USD", "us"),
]


def split_for(group: str, tilt: str | None) -> dict[str, float]:
    raw = dict(SPLIT[group])
    if group == "Equity":
        if tilt in ("apac", "apac_income"):
            raw["EME"], raw["DME"] = 45, 55
        elif tilt == "us":
            raw["EME"], raw["DME"] = 12, 88
        elif tilt == "eu":
            raw["EME"], raw["DME"] = 22, 78
    if group == "Fixed Income" and tilt in ("income", "apac_income"):
        raw["HYD"] += 8; raw["EMD_H"] += 4; raw["Gov"] = max(2, raw["Gov"] - 8); raw["Infl"] = max(2, raw["Infl"] - 4)
    if group == "Alternatives" and tilt in ("income", "apac_income"):
        raw["PD"] += 8; raw["RE"] += 6; raw["PE"] = max(2, raw["PE"] - 8); raw["HF"] = max(2, raw["HF"] - 6)
    if group == "Alternatives" and tilt == "esg":
        raw["Com"] = max(1, raw["Com"] - 8); raw["RE"] += 4; raw["HF"] += 4
    tot = sum(raw.values())
    return {k: v / tot for k, v in raw.items()}


def esaa_weights(rp: int, tilt: str | None) -> dict[str, float]:
    g = dict(zip(GROUP_ORDER, GLIDE[rp]))
    w = {}
    for grp, gw in g.items():
        for code, share in split_for(grp, tilt).items():
            w[code] = w.get(code, 0.0) + gw * share
    return w


def apply_tilt(base: dict[str, float], moves: dict[str, float]) -> dict[str, float]:
    w = {c: base.get(c, 0.0) for c in CODES}
    for c, dv in moves.items():
        w[c] = w.get(c, 0.0) + dv
    w = {c: max(0.0, v + rng.normal(0, 0.15)) for c, v in w.items()}
    tot = sum(w.values())
    return {c: round(v / tot * 100, 2) for c, v in w.items()}


DSAA26_MOVES = {"EME": 2.0, "DME": 1.5, "HYD": 2.0, "PE": 1.0,
                "Gov": -3.5, "Infl": -1.5, "Cash": -1.0, "IG": -0.5}
DSAA25_MOVES = {"EME": -1.0, "DME": -1.5, "Gov": 2.5, "Infl": 1.0,
                "HYD": -1.0, "Cash": 0.5, "IG": 0.5}

records = []
for name, ccy, tilt in MODELS:
    mid = name.lower().replace(" ", "_")
    for rp in range(1, 6):
        esaa = esaa_weights(rp, tilt)
        esaa_pct = apply_tilt(esaa, {})                       # normalise ESAA too
        d26 = apply_tilt(esaa, DSAA26_MOVES)
        d25 = apply_tilt(esaa, DSAA25_MOVES)
        for code in CODES:
            records.append({
                "model_id": mid, "model_name": name, "currency": ccy,
                "risk_profile": rp, "code": code,
                "ESAA": esaa_pct[code], "DSAA 2026": d26[code], "DSAA 2025": d25[code],
            })

df = pd.DataFrame.from_records(records)

# fix rounding so every (model, rp, scenario) sums to exactly 100
for s in SCENARIOS:
    for (mid, rp), idx in df.groupby(["model_id", "risk_profile"]).groups.items():
        sub = df.loc[idx, s]
        j = sub.idxmax()
        df.loc[j, s] = round(df.loc[j, s] + (100.0 - sub.sum()), 2)

order = {c: i for i, c in enumerate(CODES)}
df["_o"] = df["code"].map(order)
df = df.sort_values(["model_name", "risk_profile", "_o"]).drop(columns="_o")

out = os.path.join(DATA, "model_portfolios.xlsx")
df.to_excel(out, index=False, sheet_name="model_portfolios")
print(f"wrote {out}  ({len(df)} rows, {df.model_id.nunique()} models, {len(CODES)} codes)")
for ccy in CCY:
    print(f"wrote cma/cma_{ccy}.csv  +  cma/corr_{ccy}.csv")
for s in SCENARIOS:
    chk = df.groupby(["model_id", "risk_profile"])[s].sum().round(2)
    print(f"  {s}: weight-sum range {chk.min()} .. {chk.max()}")

# --------------------------------------------------------------------------- #
# finally, the daily price history the Backtesting page needs                #
# --------------------------------------------------------------------------- #
# Kept in its own file because it is a different job with different maths;
# called from here so that ONE command regenerates every data file.
print()
print("generating daily price history...")
import generate_history_data           # noqa: E402  (must run after the CMA files)
generate_history_data.main()
