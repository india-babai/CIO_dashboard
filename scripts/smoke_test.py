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

from core.analytics import compute, portfolio_metrics
from core.cma_store import CmaStore
from core.config import load_config
from core.data_loader import load_all
from core.excel_export import workbook_bytes
from core.frontier import build as build_frontier
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
print()
if FAILURES:
    print(f"{FAILURES} check(s) FAILED")
    sys.exit(1)
print("all checks passed")
