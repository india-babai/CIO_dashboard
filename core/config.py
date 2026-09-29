"""
=============================================================================
 CONFIG  —  reads settings.toml and hands it to the rest of the app
=============================================================================

WHAT THIS FILE DOES
    Loads settings.toml once and wraps it in a Config object with tidy
    accessors, so no other file ever has to know the shape of the TOML.

    Everywhere you see `cfg` in this codebase, it is one of these objects.

THE ACCESSORS YOU WILL USE MOST
    cfg.asset_codes        ['EME', 'DME', 'Gov', ...]   in display order
    cfg.asset_name         {'EME': 'Emerging Markets Equity', ...}
    cfg.subgroups          ['Equity', 'Risky FI', ...]
    cfg.groups             ['Equity', 'Fixed Income', ...]
    cfg.subgroup_of        {'EME': 'Equity', ...}       code -> sub-group
    cfg.group_of           {'EME': 'Equity', ...}       code -> group
    cfg.scenarios          ['ESAA', 'DSAA 2026', 'DSAA 2025']
    cfg.scenario_change    ('DSAA 2026', 'DSAA 2025')   the Change subtraction
    cfg.scenario_benchmark 'ESAA'                       tracking-error base
    cfg.rp_ids             [1, 2, 3, 4, 5]
    cfg.rp_short(3)        'RP3'          cfg.rp_label(3)  'RP3 - Balanced'
    cfg.currencies         ['USD', 'SGD', 'EUR', 'GBP']
    cfg.path('cma_dir')    absolute path from the [data] section

WHERE TO CHANGE WHAT
    * Add an asset class, group, scenario, risk profile -> settings.toml
    * Add a NEW SETTING                                 -> add it to
      settings.toml, then add a matching @property here so the app can read it
    * Colours for charts/CSS                            -> ui/css/01_variables.css
      (only the per-group colours live in settings.toml)

NOTE ON CACHING
    load_config() is @lru_cache'd, so settings.toml is read once per process.
    ==> After editing settings.toml you must RESTART the app (Ctrl-C and run
        again). The "Reload data" button only re-reads the data/ folder.
"""
from __future__ import annotations

import os
import tomllib
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(ROOT, "settings.toml")


def _lighten(hex_color: str, factor: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02X}{g:02X}{b:02X}"


class Config:
    def __init__(self, raw: dict):
        self._raw = raw

    # -- raw sections --------------------------------------------------- #
    @property
    def app(self) -> dict:
        return self._raw["app"]

    @property
    def validation(self) -> dict:
        return self._raw.get("validation", {})

    @property
    def frontier(self) -> dict:
        return self._raw.get("frontier", {"points": 120, "risk_free": ""})

    @property
    def backtest(self) -> dict:
        """The [backtest] table, with defaults if the section is absent."""
        return self._raw.get("backtest", {
            "rebalance": "M", "risk_free": 0.0, "var_confidence": 0.95,
            "rolling_months": 12, "default_years": 10,
        })

    @property
    def metrics_risk_free(self):
        v = str(self._raw.get("metrics", {}).get("risk_free", "")).strip()
        return float(v) if v else None

    def path(self, key: str) -> str:
        return os.path.join(ROOT, self._raw["data"][key])

    # -- currencies -------------------------------------------------- #
    @property
    def currencies(self) -> list[str]:
        return list(self._raw["currencies"])

    # -- scenarios ------------------------------------------------- #
    @property
    def scenarios(self) -> list[str]:
        return list(self._raw["scenarios"]["columns"])

    @property
    def scenario_change(self) -> tuple[str, str]:
        a, b = self._raw["scenarios"]["change"]
        return a, b

    @property
    def scenario_benchmark(self) -> str:
        return self._raw["scenarios"].get("benchmark", self.scenarios[0])

    # -- risk profiles ------------------------------------------- #
    @property
    def risk_profiles(self) -> list[dict]:
        return list(self._raw["risk_profiles"])

    @property
    def rp_ids(self) -> list[int]:
        return [rp["id"] for rp in self.risk_profiles]

    def rp_label(self, rp_id: int) -> str:
        for rp in self.risk_profiles:
            if rp["id"] == rp_id:
                return rp["label"]
        return f"RP{rp_id}"

    def rp_short(self, rp_id: int) -> str:
        for rp in self.risk_profiles:
            if rp["id"] == rp_id:
                return rp["short"]
        return f"RP{rp_id}"

    # -- groups (Level 1) & sub-groups (Level 2) ---------------- #
    @property
    def groups(self) -> list[str]:
        return [g["name"] for g in self._raw["groups"]]

    @property
    def group_colors(self) -> dict[str, str]:
        return {g["name"]: g["color"] for g in self._raw["groups"]}

    @property
    def group_order(self) -> dict[str, int]:
        return {g["name"]: i for i, g in enumerate(self._raw["groups"])}

    @property
    def subgroups(self) -> list[str]:
        return [s["name"] for s in self._raw["subgroups"]]

    @property
    def subgroup_colors(self) -> dict[str, str]:
        return {s["name"]: s["color"] for s in self._raw["subgroups"]}

    @property
    def subgroup_order(self) -> dict[str, int]:
        return {s["name"]: i for i, s in enumerate(self._raw["subgroups"])}

    # -- asset classes (granular, code-based) ------------------- #
    @property
    def asset_codes(self) -> list[str]:
        return [a["code"] for a in self._raw["asset_classes"]]

    @property
    def asset_name(self) -> dict[str, str]:
        return {a["code"]: a["name"] for a in self._raw["asset_classes"]}

    @property
    def code_order(self) -> dict[str, int]:
        return {a["code"]: i for i, a in enumerate(self._raw["asset_classes"])}

    @property
    def subgroup_of(self) -> dict[str, str]:
        return {a["code"]: a["subgroup"] for a in self._raw["asset_classes"]}

    @property
    def group_of(self) -> dict[str, str]:
        return {a["code"]: a["group"] for a in self._raw["asset_classes"]}

    def codes_in_subgroup(self, sub: str) -> list[str]:
        return [a["code"] for a in self._raw["asset_classes"] if a["subgroup"] == sub]

    def codes_in_group(self, grp: str) -> list[str]:
        return [a["code"] for a in self._raw["asset_classes"] if a["group"] == grp]

    def asset_color(self, code: str) -> str:
        """Granular codes inherit their sub-group colour, shaded by position."""
        sub = self.subgroup_of.get(code, "")
        base = self.subgroup_colors.get(sub, "#888888")
        siblings = self.codes_in_subgroup(sub)
        try:
            pos = siblings.index(code)
        except ValueError:
            return base
        n = max(len(siblings) - 1, 1)
        return _lighten(base, 0.5 * (pos / n))


@lru_cache(maxsize=1)
def load_config() -> Config:
    with open(SETTINGS_PATH, "rb") as fh:
        raw = tomllib.load(fh)
    return Config(raw)
