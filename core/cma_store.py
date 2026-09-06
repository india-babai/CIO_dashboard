"""
=============================================================================
 CMA STORE  —  the imported CMA + this session's private edits on top
=============================================================================

WHAT THIS FILE DOES
    Keeps the imported capital market assumptions (shared, read-only) separate
    from whatever the current user has typed (private, temporary), and hands
    out the combination.

        data/cma/cma_USD.csv        the imported numbers — never modified
              +
        st.session_state            this user's overrides — never saved
              =
        store.effective('USD')      what the app actually calculates with

    ==> NOTHING IS EVER WRITTEN TO DISK. One user's edits cannot be seen by
        another user, and a new browser session always starts from the files
        again. This is deliberate: the CMA page is a personal scratchpad, not
        a shared editor.

HOW THE SESSION SCOPE IS ACHIEVED
    The constructor takes a `state` mapping and stores everything inside it:

        app.py                   CmaStore(cfg, data.cma, st.session_state)
        scripts/smoke_test.py    CmaStore(cfg, data.cma, {})

    st.session_state is per-browser-session, so each user gets their own.
    Passing a plain dict makes the class testable with no Streamlit running.

    Two keys are used inside that mapping:
        "cma_overrides"  {currency: {code: {field: value}}}
        "cma_audit"      list of edit records, for the Change log tab

THE MAIN METHODS
    effective(ccy)    the CMA to calculate with (imported + this session's edits)
    set_value(...)    record one edit             (returns False if unchanged)
    reset(ccy=None)   drop edits for one currency, or all of them
    is_modified()     has this session edited anything?
    banner_text()     the amber "edited for this session only" strip
    audit_df()        the Change log table

WHERE TO CHANGE WHAT
    * Which fields can be edited  -> EDITABLE_FIELDS below
    * The banner wording          -> banner_text() below
    * Who the "user" is in the log-> current_user(); set the CIO_DASHBOARD_USER
                                     environment variable, or wire in SSO here
    * MAKE EDITS PERSIST (a shared, saved CMA) -> this is the file to change:
      write self.overrides to a JSON file in _save_overrides() and read it back
      in __init__. Be aware that then every user shares one CMA, which is
      exactly what the current design avoids.

NO STREAMLIT IMPORT IN THIS FILE — it only ever touches the mapping it is given.
"""
from __future__ import annotations

import getpass
import os
from datetime import datetime

import pandas as pd

from core.config import Config

EDITABLE_FIELDS = ("expected_return", "volatility")
_AUDIT_COLS = ["timestamp", "user", "currency", "code", "field",
               "old_value", "new_value", "action"]


def current_user() -> str:
    for getter in (lambda: os.environ.get("CIO_DASHBOARD_USER"),
                   getpass.getuser,
                   lambda: os.environ.get("USERNAME") or os.environ.get("USER")):
        try:
            v = getter()
            if v:
                return str(v)
        except Exception:
            pass
    return "unknown"


class CmaStore:
    """
    `state` is a mutable mapping scoped to one session — pass `st.session_state`
    in the app, or a fresh dict in tests / headless use. Nothing is persisted.
    """

    OV_KEY = "cma_overrides"
    AUDIT_KEY = "cma_audit"

    def __init__(self, cfg: Config, base_cma: dict[str, pd.DataFrame], state):
        self.cfg = cfg
        self.base = {k: v.copy() for k, v in base_cma.items()}
        self._state = state
        if not isinstance(state.get(self.OV_KEY), dict):
            state[self.OV_KEY] = {}
        if not isinstance(state.get(self.AUDIT_KEY), list):
            state[self.AUDIT_KEY] = []

    # ------------------------------------------------------------------ #
    # session-scoped persistence                                        #
    # ------------------------------------------------------------------ #
    @property
    def overrides(self) -> dict[str, dict[str, dict[str, float]]]:
        return self._state[self.OV_KEY]

    def _save_overrides(self) -> None:
        clean = {c: {a: dict(fields) for a, fields in assets.items() if fields}
                 for c, assets in self.overrides.items()}
        self._state[self.OV_KEY] = {c: a for c, a in clean.items() if a}

    def _append_audit(self, rows: list[dict]) -> None:
        self._state[self.AUDIT_KEY].extend(rows)

    def audit_df(self) -> pd.DataFrame:
        rows = self._state.get(self.AUDIT_KEY, [])
        return pd.DataFrame(rows, columns=_AUDIT_COLS) if rows \
            else pd.DataFrame(columns=_AUDIT_COLS)

    # ------------------------------------------------------------------ #
    # reads                                                             #
    # ------------------------------------------------------------------ #
    def effective(self, ccy: str) -> pd.DataFrame:
        """Imported CMA for `ccy` with this session's overrides applied."""
        df = self.base[ccy].copy()
        ov = self.overrides.get(ccy, {})
        if not ov:
            return df
        df = df.set_index("code")
        for code, fields in ov.items():
            if code not in df.index:
                continue
            for f, val in fields.items():
                if f in df.columns:
                    df.loc[code, f] = val
        return df.reset_index()

    def is_modified(self, ccy: str | None = None) -> bool:
        if ccy is None:
            return any(self.overrides.get(c) for c in self.base)
        return bool(self.overrides.get(ccy))

    def change_count(self, ccy: str | None = None) -> int:
        ccys = [ccy] if ccy else list(self.base)
        return sum(len(fields)
                   for c in ccys
                   for fields in self.overrides.get(c, {}).values())

    def last_edit(self) -> dict | None:
        df = self.audit_df()
        edits = df[df["action"] == "edit"] if not df.empty else df
        if edits.empty:
            return None
        row = edits.iloc[-1]
        return dict(user=row["user"], timestamp=row["timestamp"])

    def banner_text(self) -> str | None:
        if not self.is_modified():
            return None
        n = self.change_count()
        ccys = ", ".join(c for c in self.base if self.overrides.get(c))
        last = self.last_edit()
        who = f" · {last['user']} at {last['timestamp'][11:16]}" if last else ""
        return (f"CMA edited for this session only — {n} change{'s' if n != 1 else ''} "
                f"({ccys}){who}. Not saved; other users are unaffected.")

    # ------------------------------------------------------------------ #
    # writes (session only)                                             #
    # ------------------------------------------------------------------ #
    def set_value(self, ccy: str, code: str, field: str, new_value: float,
                  user: str | None = None) -> bool:
        """Record an override for this session. True if a change was made."""
        if field not in EDITABLE_FIELDS:
            raise ValueError(f"field must be one of {EDITABLE_FIELDS}")
        user = user or current_user()
        cur = self.effective(ccy).set_index("code")
        if code not in cur.index:
            raise KeyError(f"{code!r} not in {ccy} CMA")
        old_value = float(cur.loc[code, field])
        new_value = round(float(new_value), 4)
        if abs(old_value - new_value) < 1e-9:
            return False

        base_val = float(self.base[ccy].set_index("code").loc[code, field])
        self.overrides.setdefault(ccy, {}).setdefault(code, {})
        if abs(new_value - base_val) < 1e-9:
            self.overrides[ccy][code].pop(field, None)     # back to base -> drop overlay
        else:
            self.overrides[ccy][code][field] = new_value
        self._save_overrides()
        self._append_audit([dict(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            user=user, currency=ccy, code=code, field=field,
            old_value=round(old_value, 4), new_value=new_value, action="edit",
        )])
        return True

    def reset(self, ccy: str | None = None, user: str | None = None) -> int:
        """Drop this session's overrides (all, or one currency)."""
        user = user or current_user()
        targets = [ccy] if ccy else list(self.overrides.keys())
        removed, rows = 0, []
        for c in targets:
            for code, fields in list(self.overrides.get(c, {}).items()):
                for f in list(fields.keys()):
                    rows.append(dict(
                        timestamp=datetime.now().isoformat(timespec="seconds"),
                        user=user, currency=c, code=code, field=f,
                        old_value=fields[f], new_value="", action="reset",
                    ))
                    removed += 1
            self.overrides.pop(c, None)
        if removed:
            self._save_overrides()
            self._append_audit(rows)
        return removed
