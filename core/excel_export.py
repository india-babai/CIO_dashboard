"""
=============================================================================
 EXCEL DOWNLOAD  (the "Download (Excel — one sheet per RP)" button)
=============================================================================

WHAT THIS FILE DOES
    Builds the .xlsx file the user downloads from the Portfolios page.
    One worksheet per risk profile (RP1 … RP5), each laid out exactly like
    the on-screen house table.

WHERE TO CHANGE WHAT
    * What goes on each sheet   -> core/report_tables.py  stacked_block()
    * Sheet names               -> sheet name argument below (cfg.rp_short)
    * Add a summary sheet       -> add another .to_excel() call in the loop

CALLED BY
    ui/page_portfolios.py  (the st.download_button)

NO STREAMLIT IN THIS FILE.
"""
from __future__ import annotations

import io

import pandas as pd

from core.config import Config
from core.report_tables import stacked_block


def workbook_bytes(cfg: Config, weights_by_rp: dict[int, pd.DataFrame],
                   cma: pd.DataFrame, corr: pd.DataFrame) -> bytes:
    """
    weights_by_rp : {1: <weights matrix>, 2: <weights matrix>, ...}
    Returns the raw bytes of an .xlsx workbook, ready for st.download_button.
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for rp, weights in weights_by_rp.items():
            stacked_block(cfg, weights, cma, corr).to_excel(
                writer, sheet_name=cfg.rp_short(rp)
            )
    return buffer.getvalue()
