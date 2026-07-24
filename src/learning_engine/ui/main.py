"""Application entry: page config, logging, and real multipage navigation.

Everything the old app.py did at module level (provider probing, debug
prints, client creation) now happens inside the pages on demand; the only
boot work left is page config and logger setup.
"""

from __future__ import annotations

import streamlit as st

from learning_engine.logger import setup_logging
from learning_engine.settings import get_settings
from learning_engine.ui.pages import analytics, study


@st.cache_resource
def _init_logging():
    """Configure logging once per process, not on every rerun."""
    return setup_logging()


def run() -> None:
    """Launch the app: set page config, then hand control to st.navigation."""
    app = get_settings().app
    st.set_page_config(page_title=app.title, page_icon=app.page_icon, layout=app.layout)
    _init_logging()

    pages = [
        st.Page(
            study.render,
            title="Quiz & Study Materials",
            icon="📚",
            url_path="study",
            default=True,
        ),
        st.Page(analytics.render, title="Learning Analytics", icon="📊", url_path="analytics"),
    ]
    st.navigation(pages).run()
