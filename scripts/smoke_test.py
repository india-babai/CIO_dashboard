"""
=============================================================================
 SMOKE TEST  —  run this after ANY change, before you trust the app
=============================================================================

    .venv/Scripts/python.exe scripts/smoke_test.py        (Windows)
    .venv/bin/python scripts/smoke_test.py                (macOS / Linux)

WHAT THIS FILE DOES
    Exercises everything in core/ without launching Streamlit, and prints one
    line per check. It takes about 30 seconds (most of it solving frontiers).

    Exit code 0 = all good. Exit code 1 = at least one check failed.

    Because it imports nothing from ui/, a failure here is always a DATA or
    MATHS problem, never a layout problem. That split is deliberate: it tells
    you immediately which half of the codebase to look in.

THE CHECKS, IN ORDER
    1. data loads            files exist, columns present, weights sum to 100
    2. taxonomy              roll-ups preserve totals
    3. analytics             return/vol/contributions are self-consistent
    4. report tables         the four display blocks build correctly
    5. excel export          the workbook bytes are produced
    6. frontier              curve is well-formed; portfolios sit on/below it
    7. cma store             session edits apply and reset; new session is clean
    8. price history         daily files load; missing columns are reported
    9. backtest              growth, drawdown, metrics; the RP glide path makes
                             economic sense (risk rises from RP1 to RP5)

HOW TO ADD A CHECK
    Write  check(<something that should be True>, "plain english description")
    inside the relevant section. Keep the description short — it is printed.
"""
from __future__ import annotations

import os
import sys

# make `import core...` work when run as `python scripts/smoke_test.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from core import backtest as bt
from core.analytics import compute, portfolio_metrics
from core.cma_store import CmaStore
from core.config import load_config
from core.data_loader import load_all
from core.excel_export import workbook_bytes
from core.frontier import build as build_frontier
from core.history_loader import load_history
from core.report_tables import (METRIC_ROWS, granular_block, group_block,
                                metrics_block, stacked_block, subgroup_block)
from core.taxonomy import model_directory, rollup, scenario_matrix

FAILURES = 0


def check(condition: bool, description: str) -> None:
    """Print one result line and remember whether it failed."""
    global FAILURES
    print(("  ok  " if condition else " FAIL ") + description)
    if not condition:
        FAILURES += 1


def section(title: str) -> None:
    print(f"\n--- {title} " + "-" * max(0, 60 - len(title)))


# =========================================================================== #
# 1. DATA LOADS                                                              #
# =========================================================================== #
section("1. data loads")

cfg = load_config()
data = load_all(cfg)

check(data.ok, f"data loads without fatal errors (errors={data.errors})")
check(not data.portfolios.empty, "portfolio table is not empty")
if data.warnings:
    print(f"  ..  {len(data.warnings)} warning(s): " + "; ".join(data.warnings[:3]))

scenarios = cfg.scenarios
benchmark = cfg.scenario_benchmark
directory = model_directory(data.portfolios)

check(len(directory) >= 1, f"model directory built ({len(directory)} models)")
check(directory["currency"].notna().all()
      and set(directory["currency"]) <= set(cfg.currencies),
      f"every model has a known currency ({sorted(set(directory['currency']))})")

bad_weights = []
for model_id in data.portfolios["model_id"].unique():
    profiles = data.portfolios.loc[data.portfolios.model_id == model_id, "risk_profile"]
    for rp in sorted(profiles.unique()):
        weights = scenario_matrix(data.portfolios, cfg, model_id, int(rp))
        if list(weights.index) != cfg.asset_codes:
            bad_weights.append((model_id, rp, "asset codes do not match settings.toml"))
        for scenario in scenarios:
            total = weights[scenario].sum()
            if abs(total - 100) > 0.5 or (weights[scenario] < 0).any():
                bad_weights.append((model_id, rp, scenario, round(total, 2)))
check(not bad_weights,
      f"every model/RP/scenario sums to 100 and is non-negative "
      f"(problems: {bad_weights[:3]})")


# =========================================================================== #
# 2. TAXONOMY (roll-ups)                                                     #
# =========================================================================== #
section("2. taxonomy roll-ups")

sample_model = directory.iloc[0]["model_id"]
sample_currency = directory.iloc[0]["currency"]
sample_weights = scenario_matrix(data.portfolios, cfg, sample_model, 3)
sample_cma = data.cma[sample_currency]
sample_corr = data.corr[sample_currency]

for scenario in scenarios:
    column = sample_weights[scenario]
    check(abs(rollup(column, cfg, "subgroup").sum() - column.sum()) < 1e-6,
          f"[{scenario}] sub-group roll-up preserves the total")
    check(abs(rollup(column, cfg, "group").sum() - column.sum()) < 1e-6,
          f"[{scenario}] group roll-up preserves the total")


# =========================================================================== #
# 3. ANALYTICS                                                               #
# =========================================================================== #
section("3. analytics")

current_scenario = scenarios[1] if len(scenarios) > 1 else scenarios[0]
result = compute(sample_weights[current_scenario], sample_cma, sample_corr, cfg)

check(np.isfinite(result.exp_return) and result.volatility > 0
      and result.div_ratio >= 1 - 1e-6
      and 0 < result.enb <= len(cfg.asset_codes),
      f"[{sample_currency}] return={result.exp_return:.2f}%  "
      f"vol={result.volatility:.2f}%  diversification={result.div_ratio:.2f}  "
      f"effective bets={result.enb:.1f}")
check(abs(result.per_code["risk_contrib"].sum() - result.volatility) < 1e-6,
      "risk contributions add up to portfolio volatility")
check(abs(result.per_code["ret_contrib"].sum() - result.exp_return) < 1e-6,
      "return contributions add up to expected return")

benchmark_weights = sample_weights[benchmark]
at_benchmark = portfolio_metrics(benchmark_weights, sample_cma, sample_corr, cfg,
                                 benchmark=benchmark_weights)
at_current = portfolio_metrics(sample_weights[current_scenario], sample_cma,
                               sample_corr, cfg, benchmark=benchmark_weights)
check(abs(at_benchmark.tracking_error) < 1e-9,
      f"tracking error of {benchmark} against itself is 0")
check(at_current.tracking_error is not None and at_current.tracking_error >= -1e-9,
      f"tracking error {current_scenario} vs {benchmark} "
      f"= {at_current.tracking_error:.2f}%")
check(np.isfinite(at_current.sharpe), f"sharpe computes ({at_current.sharpe:.2f})")


# =========================================================================== #
# 4. REPORT TABLES (what the house table and Excel show)                     #
# =========================================================================== #
section("4. report tables")

granular = granular_block(cfg, sample_weights)
subgroup = subgroup_block(cfg, sample_weights)
group = group_block(cfg, sample_weights)
metrics = metrics_block(cfg, sample_weights, sample_cma, sample_corr)
newer, older = cfg.scenario_change

check(list(granular.index) == cfg.asset_codes,
      f"granular block has the {len(cfg.asset_codes)} asset codes in order")
check(list(subgroup.index) == cfg.subgroups,
      f"sub-group block has the {len(cfg.subgroups)} sub-groups in order")
check(list(group.index) == cfg.groups,
      f"group block has the {len(cfg.groups)} groups in order")
check(list(metrics.index) == METRIC_ROWS,
      f"metrics block has the rows {METRIC_ROWS}")
check("Change" in granular.columns
      and abs((granular[newer] - granular[older] - granular["Change"]).abs().max()) < 1e-9,
      f"Change column really is {newer} minus {older}")
check(abs(subgroup[newer].sum() - granular[newer].sum()) < 1e-6,
      "sub-group block totals match the granular block")

stacked = stacked_block(cfg, sample_weights, sample_cma, sample_corr)
expected_rows = (len(cfg.asset_codes) + 1 + len(cfg.subgroups) + 1
                 + len(cfg.groups) + 1 + len(METRIC_ROWS))
check(len(stacked) == expected_rows,
      f"stacked Excel block has {len(stacked)} rows (expected {expected_rows})")


# =========================================================================== #
# 5. EXCEL EXPORT                                                            #
# =========================================================================== #
section("5. excel export")

weights_by_rp = {rp: scenario_matrix(data.portfolios, cfg, sample_model, rp)
                 for rp in cfg.rp_ids}
workbook = workbook_bytes(cfg, weights_by_rp, sample_cma, sample_corr)
check(isinstance(workbook, bytes) and len(workbook) > 5000,
      f"workbook builds ({len(workbook):,} bytes, {len(cfg.rp_ids)} sheets)")
check(workbook[:2] == b"PK", "workbook really is a zip/xlsx file")


# =========================================================================== #
# 6. FRONTIER                                                                #
# =========================================================================== #
section("6. efficient frontier")

for currency in sorted(set(directory["currency"])):
    corr_matrix = data.corr[currency]
    smallest_eigenvalue = np.linalg.eigvalsh(corr_matrix.to_numpy(float)).min()
    check(smallest_eigenvalue > -1e-8,
          f"[{currency}] correlation matrix is positive semi-definite")

    frontier = build_frontier(data.cma[currency], corr_matrix, cfg.asset_codes,
                              n_points=int(cfg.frontier.get("points", 120)))
    vols = frontier.points["vol"].to_numpy(float)
    rets = frontier.points["ret"].to_numpy(float)
    check(np.all(np.diff(vols) >= -1e-6) and np.all(np.diff(rets) >= -1e-6),
          f"[{currency}] frontier rises monotonically")
    check(frontier.gmv[0] <= vols.min() + 1e-6,
          f"[{currency}] minimum-variance point is the lowest-risk point")

    gaps = []
    for model_id in directory.loc[directory.currency == currency, "model_id"]:
        profiles = data.portfolios.loc[data.portfolios.model_id == model_id,
                                       "risk_profile"]
        for rp in sorted(profiles.unique()):
            weights = scenario_matrix(data.portfolios, cfg, model_id, int(rp))
            point = compute(weights[current_scenario], data.cma[currency],
                            corr_matrix, cfg)
            gaps.append(frontier.gap(point.volatility, point.exp_return))
    gaps = np.array(gaps)
    check(np.nanmin(gaps) > -0.05,
          f"[{currency}] every model portfolio sits on or below the frontier "
          f"(smallest gap {np.nanmin(gaps):+.3f}, largest {np.nanmax(gaps):.2f} pp)")


# =========================================================================== #
# 7. CMA STORE (session-only edits)                                          #
# =========================================================================== #
section("7. cma store")

fake_session: dict = {}
store = CmaStore(cfg, data.cma, fake_session)
first_code = cfg.asset_codes[0]
base_return = data.cma[sample_currency].set_index("code").loc[first_code,
                                                             "expected_return"]

before = store.change_count()
changed = store.set_value(sample_currency, first_code, "expected_return",
                          base_return + 1.0, user="smoke-test")
check(changed and store.change_count() == before + 1,
      "an edit is recorded in the session store")
check(abs(store.effective(sample_currency).set_index("code")
          .loc[first_code, "expected_return"] - (base_return + 1.0)) < 1e-6,
      "the effective CMA reflects that edit")
check(store.reset(sample_currency, user="smoke-test") >= 1
      and not store.is_modified(sample_currency),
      "reset clears the edit")
check(CmaStore(cfg, data.cma, {}).is_modified() is False,
      "a brand-new session starts from the imported CMA")


# =========================================================================== #
# 8. PRICE HISTORY                                                           #
# =========================================================================== #
section("8. price history")

history = load_history(cfg, sample_currency)
check(history.ok, f"[{sample_currency}] price history loads "
                  f"(errors={history.errors})")

if history.ok:
    check(len(history.prices) > 250,
          f"{len(history.prices):,} daily rows covering {history.years:.1f} years")
    check(not history.missing_codes,
          f"every asset class has prices (missing: {history.missing_codes})")
    check(history.prices.index.is_monotonic_increasing, "dates are in order")
    check(not history.prices.isna().any().any(), "no gaps left after cleaning")

    # a column that settings.toml does not know about must be reported, and a
    # missing column must be reported rather than silently ignored
    trimmed = history.prices.drop(columns=history.prices.columns[:2])
    weights_all = scenario_matrix(data.portfolios, cfg, sample_model, 3)[current_scenario]
    aligned, dropped = bt.align_weights(weights_all, trimmed)
    check(len(dropped) >= 1,
          f"assets with no price history are reported, not silently dropped "
          f"({dropped})")
    check(abs(aligned.sum() - 1.0) < 1e-9,
          "remaining weights are renormalised back to 100%")


# =========================================================================== #
# 9. BACKTEST                                                                #
# =========================================================================== #
section("9. backtest")

if history.ok:
    rebalance = cfg.backtest.get("rebalance", "M")
    risk_free = float(cfg.backtest.get("risk_free", 0.0))

    weights, _ = bt.align_weights(sample_weights[current_scenario], history.prices)
    index = bt.run(history.prices, weights, rebalance=rebalance)

    check(not index.empty and len(index) == len(history.prices),
          f"backtest produces one index point per trading day ({len(index):,})")
    check(abs(index.iloc[0] - bt.BASE_LEVEL) < 1e-6,
          f"the index starts at {bt.BASE_LEVEL:.0f}")
    check((index > 0).all(), "the index never goes to zero or negative")

    drawdown = bt.drawdown_series(index)
    check((drawdown <= 1e-9).all(), "drawdown is never positive")
    check(abs(drawdown.max()) < 1e-6, "drawdown touches 0 at the peaks")

    metrics = bt.summary_metrics(index, risk_free=risk_free)
    check(all(np.isfinite(metrics[k]) for k in
              ["Total return %", "CAGR %", "Ann. volatility %", "Max drawdown %"]),
          f"headline metrics compute: CAGR {metrics['CAGR %']:.2f}%  "
          f"vol {metrics['Ann. volatility %']:.2f}%  "
          f"maxDD {metrics['Max drawdown %']:.1f}%")
    check(metrics["Monthly CVaR 95 %"] <= metrics["Monthly VaR 95 %"] + 1e-9,
          f"CVaR is at least as bad as VaR "
          f"({metrics['Monthly CVaR 95 %']:.2f} <= {metrics['Monthly VaR 95 %']:.2f})")
    check(metrics["Worst month %"] <= metrics["Best month %"],
          "worst month is not better than best month")
    check(0.0 <= metrics["% positive months"] <= 100.0,
          f"% positive months is a percentage ({metrics['% positive months']:.1f})")

    # tracking error against itself must be exactly zero
    self_te = bt.summary_metrics(index, benchmark=index)["Tracking error %"]
    check(abs(self_te) < 1e-9, "tracking error against itself is 0")

    # the glide path: risk must increase from RP1 to RP5
    vols, drawdowns = [], []
    for rp in cfg.rp_ids:
        rp_weights = scenario_matrix(data.portfolios, cfg, sample_model, rp)[current_scenario]
        aligned_rp, _ = bt.align_weights(rp_weights, history.prices)
        rp_metrics = bt.summary_metrics(bt.run(history.prices, aligned_rp, rebalance),
                                        risk_free=risk_free)
        vols.append(rp_metrics["Ann. volatility %"])
        drawdowns.append(rp_metrics["Max drawdown %"])
    check(all(b > a for a, b in zip(vols, vols[1:])),
          f"volatility rises with every risk profile "
          f"({vols[0]:.1f}% -> {vols[-1]:.1f}%)")
    check(all(b < a for a, b in zip(drawdowns, drawdowns[1:])),
          f"max drawdown deepens with every risk profile "
          f"({drawdowns[0]:.1f}% -> {drawdowns[-1]:.1f}%)")

    frame = bt.metrics_frame({"A": index, "B": index}, benchmark_name="A",
                             risk_free=risk_free)
    check(list(frame.index) == bt.METRIC_ROWS,
          f"metrics table has the {len(bt.METRIC_ROWS)} expected rows")

    # REGRESSION GUARD ---------------------------------------------------
    # _rebalanced_daily_returns() was rewritten from a per-month Python loop
    # to a single grouped cumprod for speed (~19s -> ~1s across a report).
    # The obvious loop version is reproduced here; the two must agree exactly.
    def _reference_loop(returns, weights, rebalance):
        groups = ([(None, returns)] if not rebalance
                  else list(returns.groupby(returns.index.to_period(rebalance))))
        pieces = []
        for _period, block in groups:
            grown = (1.0 + block).cumprod()
            value = grown.mul(weights, axis=1).sum(axis=1)
            pieces.append(value / value.shift(1).fillna(1.0) - 1.0)
        return pd.concat(pieces).sort_index()

    aligned_columns = list(weights.index)
    daily_returns = history.prices[aligned_columns].pct_change().fillna(0.0)
    worst_difference = 0.0
    for frequency in ["M", "Q", "Y", None]:
        fast = bt._rebalanced_daily_returns(daily_returns, weights, frequency)
        slow = _reference_loop(daily_returns, weights, frequency)
        worst_difference = max(worst_difference, float((fast - slow).abs().max()))
    check(worst_difference < 1e-12,
          f"vectorised rebalancing matches the reference loop exactly "
          f"(worst difference {worst_difference:.1e})")


# =========================================================================== #
print()
if FAILURES:
    print(f"{FAILURES} check(s) FAILED")
    sys.exit(1)
print("all checks passed")
