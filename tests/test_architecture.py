"""Executable enforcement of the architecture rules the modernization established.

These were prose in `docs/modernization/02-target-architecture.md` and a grep in
each phase's verify step. A rule that is only checked by remembering to grep is a
rule that erodes, so they run in CI now.

R1 — nothing below `ui/` imports Streamlit.
R4 — configuration lives in settings.py, not in literals sprinkled through code.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "learning_engine"
UI = PACKAGE / "ui"

ALL_MODULES = sorted(PACKAGE.rglob("*.py"))
BELOW_UI = [p for p in ALL_MODULES if UI not in p.parents and p.parent != UI]


def _ids(paths):
    return [str(p.relative_to(PACKAGE)) for p in paths]


def _imported_names(path: Path) -> set[str]:
    """Top-level module names imported by `path`, including inside functions."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


# --------------------------------------------------------------------------- #
# R1 — the UI boundary
# --------------------------------------------------------------------------- #


def test_the_package_actually_has_modules_below_ui():
    """Guards the guard: an empty list would make every R1 test vacuously pass."""
    assert len(BELOW_UI) >= 10


@pytest.mark.parametrize("module", BELOW_UI, ids=_ids(BELOW_UI))
def test_no_streamlit_below_the_ui_layer(module):
    """R1. Detects lazy `import streamlit` inside a function too, which grep misses."""
    assert "streamlit" not in _imported_names(module), (
        f"{module.relative_to(PACKAGE)} imports Streamlit but sits below ui/. "
        "Move the Streamlit-facing part into ui/, or pass the data in as arguments."
    )


def test_the_ui_layer_is_where_streamlit_lives():
    """The mirror of R1: if nothing in ui/ imported Streamlit, the test above is meaningless."""
    ui_modules = [p for p in ALL_MODULES if p not in BELOW_UI]
    assert any("streamlit" in _imported_names(p) for p in ui_modules)


# --------------------------------------------------------------------------- #
# Dependency direction
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("module", BELOW_UI, ids=_ids(BELOW_UI))
def test_nothing_below_ui_imports_the_ui_package(module):
    """Dependencies point one way: ui → generation/analytics → llm/extraction → settings."""
    source = module.read_text(encoding="utf-8")
    assert "learning_engine.ui" not in source, (
        f"{module.relative_to(PACKAGE)} reaches up into the UI layer."
    )


def test_models_and_settings_are_the_foundation():
    """The two leaf modules must not depend on the rest of the package (BUG-7 territory)."""
    for leaf in (PACKAGE / "models.py", PACKAGE / "settings.py"):
        source = leaf.read_text(encoding="utf-8")
        offenders = re.findall(r"^\s*(?:from|import)\s+learning_engine\.(\w+)", source, re.M)
        assert not offenders, f"{leaf.name} should import nothing from the package, got {offenders}"


# --------------------------------------------------------------------------- #
# R4 — configuration lives in settings.py
# --------------------------------------------------------------------------- #

# Values that used to be scattered literals; settings.py is now their only home.
CONFIG_LITERALS = ("11434", "gemma2:2b", "gpt-4o-mini", "gpt-3.5-turbo")


@pytest.mark.parametrize("literal", CONFIG_LITERALS)
def test_configuration_literals_live_only_in_settings(literal):
    """R4. Phase 7 routed these through settings; this stops them creeping back."""
    offenders = [
        str(p.relative_to(PACKAGE))
        for p in ALL_MODULES
        if p.name != "settings.py" and literal in p.read_text(encoding="utf-8")
    ]
    assert not offenders, f"{literal!r} is hardcoded in {offenders}. Read it from settings instead."


def test_no_module_calls_load_dotenv_except_settings():
    """One place reads the environment, so configuration cannot fork."""
    offenders = [
        str(p.relative_to(PACKAGE))
        for p in ALL_MODULES
        if p.name != "settings.py" and "load_dotenv" in p.read_text(encoding="utf-8")
    ]
    assert not offenders


def test_prompts_module_owns_the_model_facing_difficulty_instructions():
    """They lived in three divergent copies before Phase 4; keep it to one.

    The marker is the imperative form the *model* is given ("Create
    university-level questions..."). The UI's one-line descriptions in
    ui/difficulty.py describe the same levels to a human and are deliberately
    separate text — they are not a fourth copy of the prompt.
    """
    owners = [
        str(p.relative_to(PACKAGE))
        for p in ALL_MODULES
        if "create university-level questions" in p.read_text(encoding="utf-8").lower()
    ]
    assert owners == ["generation/prompts.py"], f"prompt instructions also found in {owners}"


def test_difficulty_levels_agree_between_the_prompts_and_the_ui():
    """A level offered in the sidebar with no prompt instructions would silently
    fall back to Standard, so the two lists must not drift apart."""
    from learning_engine.generation.prompts import (
        OPEN_ENDED_DIFFICULTY_INSTRUCTIONS,
        QUIZ_DIFFICULTY_INSTRUCTIONS,
    )
    from learning_engine.ui.difficulty import DIFFICULTY_DISPLAY, LEVELS, SCORING_BANDS

    assert set(LEVELS) == set(QUIZ_DIFFICULTY_INSTRUCTIONS)
    assert set(LEVELS) == set(OPEN_ENDED_DIFFICULTY_INSTRUCTIONS)
    assert set(LEVELS) == set(DIFFICULTY_DISPLAY)
    assert set(LEVELS) == set(SCORING_BANDS)


def test_every_scoring_band_list_ends_at_zero():
    """The last band is the catch-all; without a 0 threshold a low score renders nothing."""
    from learning_engine.ui.difficulty import SCORING_BANDS

    for level, bands in SCORING_BANDS.items():
        thresholds = [threshold for threshold, _kind, _msg in bands]
        assert thresholds[-1] == 0, f"{level} has no catch-all band"
        assert thresholds == sorted(thresholds, reverse=True), f"{level} bands are out of order"
        assert all(kind in {"success", "info", "warning"} for _t, kind, _m in bands)
