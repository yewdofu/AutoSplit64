"""
Issue #18: "Generate Reset Templates" refused to open while the core was
running (it opens its own capture of the same window/device), but
"Capture Setup..." had no such guard - opening it mid-run crashed with
"Unknown C++ exception from OpenCV code".

Verifies both entries now share one _capture_in_use() check, and that it
reports the capture as in use exactly when the start button is not in its
idle ("start") state.
"""
import ast
from pathlib import Path

import pytest

from as64gui.app import App

APP_SOURCE = Path(__file__).resolve().parent.parent / "as64gui" / "app.py"


class _FakeStartButton:
    def __init__(self, state):
        self._state = state

    def get_state(self):
        return self._state


def _fake_app(button_state):
    fake = type("FakeSelf", (), {})()
    fake.start_btn = _FakeStartButton(button_state)
    return fake


@pytest.mark.parametrize("state,expected", [
    ("start", False),      # idle - safe to open capture dialogs
    ("stop", True),        # running
    ("init", True),        # starting up
    ("waiting", True),     # waiting on capture device
])
def test_capture_in_use_reflects_button_state(state, expected):
    assert App._capture_in_use(_fake_app(state)) is expected


def test_both_capture_dialogs_are_guarded():
    """
    Both Capture Setup and Reset Template Generator branches must consult
    _capture_in_use() - a regression here is exactly the #18 bug.
    """
    source = APP_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)

    context_menu = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "contextMenuEvent"
    )

    # Collect the guard condition for each dialog-opening branch.
    guarded_dialogs = set()
    for node in ast.walk(context_menu):
        if not isinstance(node, ast.If):
            continue
        calls_guard = any(
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Attribute)
            and sub.func.attr == "_capture_in_use"
            for sub in ast.walk(node.test)
        )
        if not calls_guard:
            continue
        opened = {
            sub.value
            for sub in ast.walk(node)
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
        }
        guarded_dialogs |= {name for name in ("capture_editor", "reset_dialog") if name in opened}

    assert guarded_dialogs == {"capture_editor", "reset_dialog"}, (
        f"expected both dialogs behind a _capture_in_use() guard, found: {guarded_dialogs}"
    )
