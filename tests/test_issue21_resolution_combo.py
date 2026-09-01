"""
Issue #21: switching capture profiles left the Resolution dropdown showing
the previous profile's value.

Root cause: the dropdown stores (width, height) tuples as userData, and
PyQt5's QComboBox.findData() compares Python-object userData by identity,
not value - so the equal-but-distinct tuple rebuilt from config (JSON)
never matched and setCurrentIndex() was never called, leaving the combo on
its default first entry.

Verifies the replacement lookup (_find_resolution_index) matches by value,
and that switching profiles now updates the dropdown in both directions.
"""
import copy

import pytest

from as64core import config


@pytest.fixture(autouse=True)
def restore_config():
    if not config._config:
        config.load_config()
    snapshot = copy.deepcopy(config._config)
    yield
    config.replace_config(snapshot)


@pytest.fixture()
def editor(qapp):
    from as64gui.dialogs.capture_editor_dialog import CaptureEditor

    dlg = CaptureEditor()
    # Real screen/device capture isn't available in this environment.
    dlg.refresh_graphics_scene = lambda *a, **kw: None
    dlg._refresh_device_list = lambda *a, **kw: None
    dlg._draft = config.copy_config()
    dlg._pending_template_copies = []
    return dlg


def test_pyqt_finddata_cannot_match_equal_tuples(qapp):
    """Documents the PyQt5 behavior this fix works around."""
    from PyQt5 import QtWidgets

    combo = QtWidgets.QComboBox()
    stored = (1280, 720)
    combo.addItem("1280 x 720", stored)

    assert combo.findData(stored) == 0                    # same object: found
    assert combo.findData(tuple([1280, 720])) == -1       # equal but distinct: not found


def test_find_resolution_index_matches_by_value(editor):
    # A tuple rebuilt the way config does it (from a JSON list).
    assert editor._find_resolution_index(tuple([1280, 720])) >= 0
    assert editor._find_resolution_index([1280, 720]) == editor._find_resolution_index((1280, 720))


def test_find_resolution_index_returns_minus_one_for_unknown(editor):
    assert editor._find_resolution_index((1234, 5678)) == -1
    assert editor._find_resolution_index(None) == -1
    assert editor._find_resolution_index([]) == -1


def test_switching_profiles_updates_resolution_dropdown(editor):
    profile_a = config.get_active_capture_profile_id(editor._draft)
    config.set_key("game", "capture_source", "device", editor._draft)
    config.set_key("game", "device_resolution", [1920, 1080], editor._draft)

    profile_b = config.create_capture_profile("TestProfileB", profile_a, editor._draft)
    config.set_active_capture_profile(profile_b, editor._draft)
    config.set_key("game", "device_resolution", [1280, 720], editor._draft)
    config.set_active_capture_profile(profile_a, editor._draft)

    editor._populate_profiles()
    editor._load_active_profile()
    assert editor.resolution_combo.currentData() == (1920, 1080)

    editor.profile_combo.setCurrentIndex(editor.profile_combo.findData(profile_b))
    assert editor.resolution_combo.currentData() == (1280, 720)

    editor.profile_combo.setCurrentIndex(editor.profile_combo.findData(profile_a))
    assert editor.resolution_combo.currentData() == (1920, 1080)
