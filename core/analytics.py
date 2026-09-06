"""
=============================================================================
 ANALYTICS  —  ALL the portfolio maths lives here
=============================================================================

WHAT THIS FILE DOES
    Turns a weight vector + the CMA into risk and return numbers. If you ever
    need to check or change a formula, this is the only file to open.

    TWO PUBLIC FUNCTIONS
      portfolio_metrics()  the headline four: expected return, volatility,
                           Sharpe, tracking error.  Used by the metrics block.
      compute()            the same plus per-asset contributions, the
                           diversification ratio and effective number of bets.
                           Used by the charts and the frontier.

THE FORMULAS  (i = one asset class, w = weights as fractions)

    expected return          = Σ  wᵢ · erᵢ
    covariance      Σ_ij     = corr_ij · volᵢ · vol_j
    portfolio volatility     = √( wᵀ Σ w )
    tracking error vs b      = √( (w−b)ᵀ Σ (w−b) )
    Sharpe                   = (return − risk-free) / volatility
    risk contribution  RC_i  = wᵢ · (Σw)ᵢ / volatility      (Σ RC_i = volatility)
    diversification ratio    = (Σ wᵢ·volᵢ) / volatility      (1.0 = no benefit)
    effective number of bets = exp( −Σ pᵢ·ln pᵢ ),  pᵢ = RC_i / volatility

UNITS — THE ONE THING TO GET RIGHT
    Everything in and out is in PERCENT, not fractions:  7.0 means 7.0%.
    Weights arrive as percent and are divided by 100 internally, once, in
    _align(). If you add a formula, follow that convention or your numbers
    will be out by a factor of 100.

WHAT HAPPENS TO MISSING DATA
    _align() keeps only asset codes that appear in BOTH the weights and the
    CMA. `coverage` on the result tells you what percentage of the portfolio
    that was — if a code is missing from the CMA it is silently excluded, and
    coverage drops below 100.

WHERE TO CHANGE WHAT
    * The risk-free rate     -> settings.toml [metrics].risk_free
                                (blank = use the lowest-volatility asset)
    * Add a new metric       -> add it here, then surface it in
                                core/report_tables.py metrics_block()
    * Change a formula       -> here, then re-run scripts/smoke_test.py, which
                                checks that contributions still add up

NO STREAMLIT IN THIS FILE.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.config import Config


@dataclass
class Metrics:
    exp_return: float
    exp_vol: float
    sharpe: float
    tracking_error: float | None
    coverage: float


@dataclass
class PortfolioMetrics:
    exp_return: float
    volatility: float
    return_risk: float
    div_ratio: float
    enb: float
    coverage: float
    per_code: pd.DataFrame
    per_subgroup: pd.DataFrame
    per_group: pd.DataFrame


def _sigma(vol: np.ndarray, corr: np.ndarray) -> np.ndarray:
    return corr * np.outer(vol, vol)


def _align(weights: pd.Series, cma: pd.DataFrame, corr: pd.DataFrame):
    cma_idx = cma.set_index("code")
    codes = [c for c in weights.index if c in cma_idx.index]
    w = weights.reindex(codes).fillna(0.0).to_numpy(dtype=float) / 100.0
    er = cma_idx.loc[codes, "expected_return"].to_numpy(dtype=float)
    sig = cma_idx.loc[codes, "volatility"].to_numpy(dtype=float)
    C = np.eye(len(codes))
    have = [c for c in codes if c in corr.index and c in corr.columns]
    if have:
        sub = corr.loc[have, have].to_numpy(dtype=float)
        pos = {c: i for i, c in enumerate(codes)}
        for i, a in enumerate(have):
            for j, b in enumerate(have):
                C[pos[a], pos[b]] = sub[i, j]
    np.fill_diagonal(C, 1.0)
    return codes, w, er, sig, C


def _rf(er: np.ndarray, sig: np.ndarray, rf) -> float:
    if rf is not None:
        return float(rf)
    return float(er[int(np.argmin(sig))]) if len(sig) else 0.0


def portfolio_metrics(weights: pd.Series, cma: pd.DataFrame, corr: pd.DataFrame,
                      cfg: Config, benchmark: pd.Series | None = None,
                      rf=None) -> Metrics:
    codes, w, er, sig, C = _align(weights, cma, corr)
    coverage = float(weights.reindex(codes).fillna(0.0).sum()) if codes else 0.0
    if not codes or w.sum() == 0:
        return Metrics(np.nan, np.nan, np.nan, None, coverage)

    Sigma = _sigma(sig, C)
    ret = float(w @ er)
    vol = float(np.sqrt(max(w @ Sigma @ w, 0.0)))
    rate = _rf(er, sig, rf)
    sharpe = (ret - rate) / vol if vol > 0 else np.nan

    te = None
    if benchmark is not None:
        wb = benchmark.reindex(codes).fillna(0.0).to_numpy(dtype=float) / 100.0
        d = w - wb
        te = float(np.sqrt(max(d @ Sigma @ d, 0.0)))

    return Metrics(ret, vol, sharpe, te, coverage)


def compute(weights: pd.Series, cma: pd.DataFrame, corr: pd.DataFrame,
            cfg: Config) -> PortfolioMetrics:
    codes, w, er, sig, C = _align(weights, cma, corr)
    coverage = float(weights.reindex(codes).fillna(0.0).sum()) if codes else 0.0

    base = pd.DataFrame({"code": codes})
    base["subgroup"] = base["code"].map(cfg.subgroup_of)
    base["group"] = base["code"].map(cfg.group_of)
    base["weight"] = weights.reindex(codes).fillna(0.0).to_numpy(dtype=float)

    if not codes or w.sum() == 0:
        empty = base.assign(expected_return=np.nan, volatility=np.nan,
                            ret_contrib=np.nan, ret_contrib_pct=np.nan,
                            risk_contrib=np.nan, risk_contrib_pct=np.nan)
        return PortfolioMetrics(np.nan, np.nan, np.nan, np.nan, np.nan, coverage,
                                empty, _roll(empty, cfg, "subgroup"),
                                _roll(empty, cfg, "group"))

    Sigma = _sigma(sig, C)
    port_ret = float(w @ er)
    vol = float(np.sqrt(max(w @ Sigma @ w, 0.0)))
    Sw = Sigma @ w
    rc = w * Sw / vol if vol > 0 else np.zeros_like(w)
    rc_pct = rc / vol * 100.0 if vol > 0 else np.zeros_like(w)
    wavg_vol = float(np.dot(w, sig))
    div_ratio = wavg_vol / vol if vol > 0 else np.nan
    p = rc / rc.sum() if rc.sum() > 0 else np.zeros_like(rc)
    nz = p[p > 0]
    enb = float(np.exp(-np.sum(nz * np.log(nz)))) if nz.size else np.nan
    ret_contrib = w * er

    per_code = base.assign(
        expected_return=er, volatility=sig,
        ret_contrib=ret_contrib,
        ret_contrib_pct=ret_contrib / port_ret * 100.0 if port_ret else np.nan,
        risk_contrib=rc, risk_contrib_pct=rc_pct,
    )

    return PortfolioMetrics(
        exp_return=port_ret, volatility=vol,
        return_risk=port_ret / vol if vol > 0 else np.nan,
        div_ratio=div_ratio, enb=enb, coverage=coverage,
        per_code=per_code,
        per_subgroup=_roll(per_code, cfg, "subgroup"),
        per_group=_roll(per_code, cfg, "group"),
    )


def _roll(per_code: pd.DataFrame, cfg: Config, level: str) -> pd.DataFrame:
    order = cfg.subgroups if level == "subgroup" else cfg.groups
    agg = per_code.groupby(level, as_index=False).agg(
        weight=("weight", "sum"),
        ret_contrib=("ret_contrib", "sum"),
        ret_contrib_pct=("ret_contrib_pct", "sum"),
        risk_contrib=("risk_contrib", "sum"),
        risk_contrib_pct=("risk_contrib_pct", "sum"),
    ).rename(columns={level: "name"})
    agg["_o"] = agg["name"].map({n: i for i, n in enumerate(order)}).fillna(9_999)
    return agg.sort_values("_o").drop(columns="_o").reset_index(drop=True)


def diff_series(a: pd.Series, b: pd.Series) -> pd.Series:
    idx = a.index.union(b.index)
    return a.reindex(idx).fillna(0.0) - b.reindex(idx).fillna(0.0)
