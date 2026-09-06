"""
=============================================================================
 FRONTIER  —  the long-only mean-variance efficient frontier
=============================================================================

WHAT THIS FILE DOES
    Solves "what is the best return achievable at each level of risk?" from
    the CMA, and measures how far a given portfolio sits below that curve.

    build()          solve the frontier -> a Frontier object
    Frontier.gap()   how much return a portfolio gives up at its own risk level
    Frontier.points  DataFrame of the curve itself (vol, ret)
    Frontier.gmv     the global minimum-variance portfolio (vol, ret)
    Frontier.tangency the max-Sharpe portfolio (vol, ret)
    Frontier.assets  each single asset class as a (vol, ret) point

CONSTRAINTS  (the same ones a real model portfolio has)
    sum(w) = 1     fully invested
    w >= 0         long only, no shorting, no leverage

HOW IT IS SOLVED
    For a grid of target returns, minimise variance subject to hitting that
    target — that is a small quadratic problem SciPy's SLSQP handles reliably.
    Analytic gradients are supplied (the `jac=` arguments), which is what makes
    120 solves take ~1.3 s instead of ~9 s. Don't remove them.

    The grid is denser at the low-risk end (`frac = linspace(...) ** 1.6`)
    because that is where model portfolios actually sit, so `gap()` stays
    accurate there.

WHY gap() IS NEVER NEGATIVE
    gap() reads the frontier return at a portfolio's volatility by
    interpolating between solved points. The frontier is concave, so a
    straight line between two points sits slightly BELOW the true curve — with
    too few points that can make a portfolio look better than optimal
    (a negative gap). 120 points keeps that error under ~0.02 pp, and values
    between -0.03 and 0 are clamped to 0.

DEPENDENCY
    This is the only file that needs SciPy. If SciPy is missing, the app still
    runs — ui/sections/frontier_section.py catches the ImportError and shows a
    message instead of that one section.

WHERE TO CHANGE WHAT
    * Number of points solved  -> settings.toml [frontier].points
    * Risk-free rate           -> settings.toml [frontier].risk_free
    * Allow shorting           -> change bounds=[(0.0, 1.0)] in _solve()
    * Add a max weight per asset -> change the same bounds, e.g. (0.0, 0.25)

UNITS: percent in, percent out, exactly like core/analytics.py.
NO STREAMLIT IN THIS FILE.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def _sigma(vol: np.ndarray, corr: np.ndarray) -> np.ndarray:
    return corr * np.outer(vol, vol)


def _solve(Sigma: np.ndarray, er: np.ndarray | None = None,
           target: float | None = None, w0: np.ndarray | None = None) -> np.ndarray | None:
    n = Sigma.shape[0]
    ones = np.ones(n)
    cons = [{"type": "eq",
             "fun": lambda w: float(np.sum(w) - 1.0),
             "jac": lambda w: ones}]
    if target is not None and er is not None:
        cons.append({"type": "eq",
                     "fun": lambda w, t=target: float(w @ er - t),
                     "jac": lambda w: er})
    res = minimize(
        lambda w: float(w @ Sigma @ w),
        np.full(n, 1.0 / n) if w0 is None else w0,
        jac=lambda w: 2.0 * (Sigma @ w),
        method="SLSQP", bounds=[(0.0, 1.0)] * n, constraints=cons,
        options={"maxiter": 200, "ftol": 1e-10},
    )
    if res.success:
        return res.x
    if er is not None and target is not None:      # accept near-feasible
        w = np.clip(res.x, 0, 1)
        s = w.sum()
        if s > 0 and abs(w @ er / s - target) < 0.05:
            return w / s
    return None


@dataclass
class Frontier:
    points: pd.DataFrame              # columns: vol, ret  (vol ascending, efficient)
    gmv: tuple[float, float]          # (vol, ret) global minimum-variance portfolio
    tangency: tuple[float, float] | None   # (vol, ret) max-Sharpe portfolio vs rf
    rf: float
    assets: pd.DataFrame             # asset_class, vol, ret  (single-asset points)
    _Sigma: np.ndarray = field(default=None, repr=False)
    _er: np.ndarray = field(default=None, repr=False)
    _r_lo: float = field(default=0.0, repr=False)
    _r_hi: float = field(default=0.0, repr=False)

    def frontier_return_at(self, vol: float) -> float:
        """Max expected return achievable at volatility `vol` (percent)."""
        v = self.points["vol"].to_numpy(dtype=float)
        r = self.points["ret"].to_numpy(dtype=float)
        if not np.isfinite(vol) or len(v) == 0:
            return float("nan")
        return float(np.interp(vol, v, r, left=r[0], right=r[-1]))

    def gap(self, port_vol: float, port_ret: float) -> float:
        """
        Extra expected return available on the frontier at the portfolio's own
        risk level, in percentage points. >= 0 -> portfolio sits below the
        frontier (return given up); ~0 -> on the frontier. The frontier is
        sampled densely enough that chord error is < ~0.02 pp.
        """
        g = self.frontier_return_at(port_vol) - port_ret
        return 0.0 if -0.03 < g < 0 else g


def build(cma: pd.DataFrame, corr: pd.DataFrame, asset_order: list[str],
          n_points: int = 120, rf: float | None = None) -> Frontier:
    key = "code" if "code" in cma.columns else "asset_class"
    df = cma.set_index(key)
    names = [a for a in asset_order if a in df.index]
    er = df.loc[names, "expected_return"].to_numpy(dtype=float)
    vol = df.loc[names, "volatility"].to_numpy(dtype=float)

    C = corr.reindex(index=names, columns=names).to_numpy(dtype=float)
    C = np.nan_to_num(C, nan=0.0)
    np.fill_diagonal(C, 1.0)
    Sigma = _sigma(vol, C)

    w_gmv = _solve(Sigma)
    if w_gmv is None:
        w_gmv = np.full(len(names), 1.0 / len(names))
    gmv_ret = float(w_gmv @ er)
    gmv_vol = float(np.sqrt(max(w_gmv @ Sigma @ w_gmv, 0.0)))

    r_lo, r_hi = gmv_ret, float(er.max())
    # target returns concentrated toward the low-risk end, where model
    # portfolios actually sit, so chord interpolation stays tight there
    n = max(n_points, 24)
    frac = np.linspace(0.0, 1.0, n) ** 1.6
    targets = r_lo + (r_hi * 0.99995 - r_lo) * frac
    rows, w_prev = [(gmv_vol, gmv_ret)], w_gmv
    for t in targets[1:]:
        w = _solve(Sigma, er, t, w0=w_prev)
        if w is None:
            w = _solve(Sigma, er, t)               # retry from equal weights
        if w is None:
            continue
        w_prev = w
        rows.append((float(np.sqrt(max(w @ Sigma @ w, 0.0))), float(w @ er)))

    fr = (pd.DataFrame(rows, columns=["vol", "ret"])
          .sort_values("vol").reset_index(drop=True))
    fr["ret"] = fr["ret"].cummax()
    fr = fr.drop_duplicates(subset="vol").reset_index(drop=True)

    if rf is None:
        rf = float(er[int(np.argmin(vol))])
    tangency = None
    if len(fr) > 1:
        with np.errstate(divide="ignore", invalid="ignore"):
            sharpe = (fr["ret"] - rf) / fr["vol"].replace(0.0, np.nan)
        if sharpe.notna().any():
            i = int(sharpe.idxmax())
            tangency = (float(fr.loc[i, "vol"]), float(fr.loc[i, "ret"]))

    assets = pd.DataFrame({"code": names, "vol": vol, "ret": er})
    return Frontier(fr[["vol", "ret"]], (gmv_vol, gmv_ret), tangency, float(rf),
                    assets, Sigma, er, r_lo, r_hi)
