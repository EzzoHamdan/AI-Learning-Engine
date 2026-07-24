"""Rendering generated material to portable formats.

Study materials were previously trapped in the browser session: generate a
cheat sheet, close the tab, lose it. These renderers turn any material model
into Markdown, which pastes into Obsidian/Notion, prints, and survives.

Pure functions of the domain models — no Streamlit (architecture rule R1), so
the UI supplies only the download button.
"""

from __future__ import annotations

from learning_engine.export.markdown import material_to_markdown, quiz_to_markdown

__all__ = ["material_to_markdown", "quiz_to_markdown"]
