"""
=============================================================================
 DATA LOADER  —  reads and validates everything in data/
=============================================================================

WHAT THIS FILE DOES
    Reads the three kinds of file in data/ and returns them in one LoadResult,
    together with any problems it found.

    data/model_portfolios.xlsx    one row per (model, risk profile, asset code)
                                  columns: model_id, model_name, currency,
                                  risk_profile, code, + one per scenario
    data/cma/cma_<CCY>.csv        code, expected_return, volatility
    data/cma/corr_<CCY>.csv       square correlation matrix, first column=code

WHAT COMES BACK  (LoadResult)
    .portfolios  DataFrame — the tidy portfolio table
    .cma         {'USD': DataFrame, ...}   expected return + volatility
    .corr        {'USD': DataFrame, ...}   correlation matrices
    .warnings    list[str] — non-fatal; shown in the "Data checks" expander
    .errors      list[str] — fatal; the app stops and prints these
    .ok          True when there are no errors

VALIDATION IT PERFORMS
    * every required column is present               -> error if not
    * every model's currency has a CMA file          -> error if not
    * weights are non-negative                       -> error if not
    * each (model, risk profile, scenario) sums to 100
      within [validation].weight_sum_tolerance       -> warning if not
    * asset codes match settings.toml                -> warning if not

WHERE TO CHANGE WHAT
    * Accept a new column in the Excel file  -> BASE_COLS + the parsing below
    * Loosen / tighten the 100% check        -> settings.toml [validation]
    * Read from a database instead of files  -> replace _read_model_file() and
      the CMA reads; keep the LoadResult shape and nothing else has to change
    * File locations                         -> settings.toml [data]

NO STREAMLIT IN THIS FILE.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from core.config import Config

BASE_COLS = {"model_id", "model_name", "currency", "risk_profile", "code"}


@dataclass
class LoadResult:
    portfolios: pd.DataFrame           # long by (model, rp, code); one col per scenario
    cma: dict[str, pd.DataFrame]       # ccy -> [code, expected_return, volatility]
    corr: dict[str, pd.DataFrame]      # ccy -> NxN correlation frame (code index+cols)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _read_model_file(path: str) -> pd.DataFrame:
    if path.lower().endswith((".xlsx", ".xlsm", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


def load_all(cfg: Config) -> LoadResult:
    warnings: list[str] = []
    errors: list[str] = []
    scenarios = cfg.scenarios

    # ---- model portfolios ---------------------------------------------- #
    mp_path = cfg.path("model_portfolios")
    if not os.path.exists(mp_path):
        return LoadResult(pd.DataFrame(), {}, {}, errors=[f"Model portfolio file not found: {mp_path}"])

    df = _read_model_file(mp_path)
    df.columns = [str(c).strip() for c in df.columns]
    need = BASE_COLS | set(scenarios)
    missing = need - set(df.columns)
    if missing:
        errors.append(f"Model portfolio file missing columns: {sorted(missing)}")
        return LoadResult(pd.DataFrame(), {}, {}, errors=errors)

    df["risk_profile"] = pd.to_numeric(df["risk_profile"], errors="coerce").astype("Int64")
    df["code"] = df["code"].astype(str).str.strip()
    df["currency"] = df["currency"].astype(str).str.strip()
    for s in scenarios:
        df[s] = pd.to_numeric(df[s], errors="coerce")
    df = df.dropna(subset=["risk_profile", "code"])

    known = set(cfg.asset_codes)
    unknown = sorted(set(df["code"]) - known)
    if unknown:
        warnings.append(f"{len(unknown)} asset code(s) not in settings.toml (shown as-is): "
                        f"{', '.join(unknown[:8])}{' ...' if len(unknown) > 8 else ''}")

    missing_ccy = sorted(set(df["currency"]) - set(cfg.currencies))
    if missing_ccy:
        errors.append(f"Model(s) use currency with no CMA file: {missing_ccy}. "
                      f"Add data/cma/cma_<CCY>.csv or fix the data.")

    allow_neg = bool(cfg.validation.get("allow_negative_weights", False))
    tol = float(cfg.validation.get("weight_sum_tolerance", 0.5))
    for s in scenarios:
        if not allow_neg and (df[s].fillna(0) < 0).any():
            n = int((df[s].fillna(0) < 0).sum())
            errors.append(f"Negative weights in scenario '{s}' ({n} rows).")
        sums = df.groupby(["model_id", "risk_profile"])[s].sum()
        for (mid, rp), tot in sums[(sums - 100).abs() > tol].items():
            name = df.loc[df.model_id == mid, "model_name"].iloc[0]
            warnings.append(f"{name} / RP{rp} / {s}: weights sum to {tot:.2f} (expected 100 +/- {tol})")

    keep = ["model_id", "model_name", "currency", "risk_profile", "code"] + scenarios
    portfolios = (df[keep]
                  .groupby(["model_id", "model_name", "currency", "risk_profile", "code"],
                           as_index=False)[scenarios].sum())

    # ---- CMA --------------------------------------------------------- #
    cma: dict[str, pd.DataFrame] = {}
    corr: dict[str, pd.DataFrame] = {}
    cma_dir = cfg.path("cma_dir")
    used_ccys = sorted(set(portfolios["currency"]) & set(cfg.currencies)) or cfg.currencies
    for ccy in used_ccys:
        cpath = os.path.join(cma_dir, f"cma_{ccy}.csv")
        rpath = os.path.join(cma_dir, f"corr_{ccy}.csv")
        if not os.path.exists(cpath):
            errors.append(f"CMA file not found: {cpath}")
            continue
        c = pd.read_csv(cpath)
        c.columns = [str(x).strip() for x in c.columns]
        if "code" not in c.columns and "asset_class" in c.columns:
            c = c.rename(columns={"asset_class": "code"})
        for col in ("code", "expected_return", "volatility"):
            if col not in c.columns:
                errors.append(f"{cpath} missing column '{col}'")
        c["code"] = c["code"].astype(str).str.strip()
        cma[ccy] = c

        if os.path.exists(rpath):
            r = pd.read_csv(rpath)
            r.columns = [str(x).strip() for x in r.columns]
            key = "code" if "code" in r.columns else "asset_class"
            r = r.set_index(key)
            r.index = r.index.astype(str).str.strip()
            r.columns = [str(x).strip() for x in r.columns]
            corr[ccy] = r
        else:
            warnings.append(f"No correlation file for {ccy}; assuming identity (no diversification).")
            names = list(c["code"])
            corr[ccy] = pd.DataFrame(np.eye(len(names)), index=names, columns=names)

        miss = sorted(set(cfg.asset_codes) - set(c["code"]))
        if miss:
            warnings.append(f"CMA {ccy} missing {len(miss)} code(s): "
                            f"{', '.join(miss[:8])}{' ...' if len(miss) > 8 else ''}")

    return LoadResult(portfolios.reset_index(drop=True), cma, corr, warnings, errors)
