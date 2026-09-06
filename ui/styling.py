"""
=============================================================================
 STYLING  —  loads the CSS files into the page
=============================================================================

WHAT THIS FILE DOES
    Reads every .css file in  ui/css/  in filename order and injects them as
    one <style> block. That is the whole mechanism — there is no build step,
    no bundler, no preprocessor.

HOW TO ADD A NEW STYLESHEET
    Drop a file into ui/css/ with a number prefix that puts it in the right
    place, e.g. "06_my_new_section.css". It is picked up automatically on the
    next page load. Later files win when two rules have equal specificity.

WHY NUMBER PREFIXES
    01_variables.css        must come first (defines the colours)
    02_streamlit_reset.css  hides Streamlit's chrome
    03_layout_and_headings  page frame
    04_widgets              controls
    05_house_table          the big table

CALLED BY
    app.py, once per page load.
"""
from __future__ import annotations

import os

import streamlit as st

CSS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "css")


def read_all_css() -> str:
    """Concatenate every .css file in ui/css/, sorted by filename."""
    if not os.path.isdir(CSS_DIR):
        return ""
    parts = []
    for filename in sorted(os.listdir(CSS_DIR)):
        if not filename.lower().endswith(".css"):
            continue
        with open(os.path.join(CSS_DIR, filename), "r", encoding="utf-8") as fh:
            parts.append(f"/* ==== {filename} ==== */\n{fh.read()}")
    return "\n\n".join(parts)


def inject_css() -> None:
    """Put the stylesheet into the page. Call once, at the top of app.main()."""
    st.markdown(f"<style>{read_all_css()}</style>", unsafe_allow_html=True)
