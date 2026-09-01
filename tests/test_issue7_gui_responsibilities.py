"""
Issue #7: CaptureEditor, RouteEditor, and App each saved the same settings
through more than one path and mixed data conversion into widget-reading
code, making the conversion untestable without a running dialog.

Verifies the extracted pure conversions (CaptureEditor._widget_state,
RouteEditor._row_to_split/_build_route, App._set_and_save) work correctly
using plain stand-in objects - no real Qt widgets, no config file access.

Every test here either uses a fake stand-in object or monkeypatches
config.save_config to a no-op, so none of them touch the real config.json.
"""
import pytest

from as64core.constants import SPLIT_NORMAL, SPLIT_FADE_ONLY, SPLIT_XCAM, TIMING_RTA


# --- CaptureEditor._widget_state -------------------------------------------------

class _FakeCombo:
    def __init__(self, index, text=None, data=None):
        self._index = index
        self._text = text
        self._data = data

    def currentIndex(self):
        return self._index

    def currentText(self):
        return self._text

    def currentData(self):
        return self._data


class _FakeRegionPanel:
    def __init__(self, data):
        self._data = data

    def get_data(self):
        return self._data


def test_widget_state_window_mode():
    from as64gui.dialogs.capture_editor_dialog import CaptureEditor, CAPTURE_SOURCE_WINDOW

    fake = type("FakeSelf", (), {})()
    fake._is_device_mode = lambda: False
    fake.game_region_panel = _FakeRegionPanel([1, 2, 640, 480])
    fake._preview_size = (640, 480)
    fake.process_combo = _FakeCombo(0, text="game.exe")
    fake.device_combo = None
    fake.resolution_combo = None

    state = CaptureEditor._widget_state(fake)

    assert state == {
        "capture_source": CAPTURE_SOURCE_WINDOW,
        "game_region": [1, 2, 640, 480],
        "capture_size": [640, 480],
        "process_name": "game.exe",
    }


def test_widget_state_device_mode():
    from as64gui.dialogs.capture_editor_dialog import CaptureEditor, CAPTURE_SOURCE_DEVICE

    fake = type("FakeSelf", (), {})()
    fake._is_device_mode = lambda: True
    fake.game_region_panel = _FakeRegionPanel([1, 2, 640, 480])
    fake._preview_size = (1920, 1080)
    fake.device_combo = _FakeCombo(0, text="Cam 1", data=2)
    fake.resolution_combo = _FakeCombo(0, data=(1920, 1080))
    fake.process_combo = _FakeCombo(-1)

    state = CaptureEditor._widget_state(fake)

    assert state == {
        "capture_source": CAPTURE_SOURCE_DEVICE,
        "game_region": [1, 2, 640, 480],
        "capture_size": [1920, 1080],
        "device_index": 2,
        "device_name": "Cam 1",
        "device_resolution": [1920, 1080],
    }


# --- RouteEditor._row_to_split / _build_route -----------------------------------

def test_row_to_split_valid_row():
    from as64gui.dialogs.route_editor_dialog import RouteEditor

    split, error, col = RouteEditor._row_to_split(1, "Bob-omb Battlefield", "5", "1", "0", "-1", SPLIT_NORMAL, "icon.png")
    assert error is None
    assert split.title == "Bob-omb Battlefield"
    assert split.star_count == 5


def test_row_to_split_empty_title_errors():
    from as64gui.dialogs.route_editor_dialog import RouteEditor

    split, error, col = RouteEditor._row_to_split(2, "", "5", "1", "0", "-1", SPLIT_NORMAL, "")
    assert split is None
    assert error == "Invalid Title - Row: 2"
    assert col == 1


def test_row_to_split_invalid_star_count_allowed_on_fade_only():
    from as64gui.dialogs.route_editor_dialog import RouteEditor

    split, error, col = RouteEditor._row_to_split(3, "Split", "abc", "1", "0", "-1", SPLIT_FADE_ONLY, "")
    assert error is None
    assert split.star_count == -1


def test_row_to_split_invalid_fadeout_on_normal_is_caught():
    """
    Regression: extracting this from route_editor_dialog.py's save() fixed
    three `cellWidget(...).currentText` comparisons that were missing their
    `()`, so they always compared a bound method to a string and never
    actually validated fadeout/fadein/xcam for SPLIT_NORMAL/SPLIT_XCAM rows.
    """
    from as64gui.dialogs.route_editor_dialog import RouteEditor

    split, error, col = RouteEditor._row_to_split(5, "Split", "5", "abc", "0", "-1", SPLIT_NORMAL, "")
    assert error == "Invalid Fadeout - Row: 5"
    assert col == 3


def test_row_to_split_invalid_fadeout_on_non_normal_allowed():
    from as64gui.dialogs.route_editor_dialog import RouteEditor

    split, error, col = RouteEditor._row_to_split(6, "Split", "5", "abc", "0", "-1", SPLIT_XCAM, "")
    assert error is None
    assert split.on_fadeout == -1


def test_build_route_empty_title_errors():
    from as64gui.dialogs.route_editor_dialog import RouteEditor

    route, error = RouteEditor._build_route("/tmp/x.as64", "", [], "0", "JP", "", TIMING_RTA)
    assert route is None
    assert error == "Invalid Route Title"


def test_build_route_invalid_initial_star_errors():
    from as64gui.dialogs.route_editor_dialog import RouteEditor

    route, error = RouteEditor._build_route("/tmp/x.as64", "Title", [], "abc", "JP", "", TIMING_RTA)
    assert route is None
    assert error == "Invalid Initial Star"


def test_build_route_requires_at_least_one_split():
    from as64gui.dialogs.route_editor_dialog import RouteEditor

    route, error = RouteEditor._build_route("/tmp/x.as64", "My Route", [], "0", "JP", "16 Star", TIMING_RTA)
    assert route is None
    assert "split" in error.lower()


# --- App._set_and_save -----------------------------------------------------------

def test_set_and_save_is_the_only_path_used(monkeypatch):
    from as64gui.app import App
    from as64core import config

    calls = []
    monkeypatch.setattr(config, "set_key", lambda *a, **kw: calls.append(("set_key", a)))
    monkeypatch.setattr(config, "save_config", lambda: calls.append(("save_config",)))

    fake = type("FakeSelf", (), {})()
    App._set_and_save(fake, "general", "srl_mode", True)

    assert calls == [("set_key", ("general", "srl_mode", True)), ("save_config",)]
