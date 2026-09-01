"""
Issue #6: ProcessFadeout, ProcessFadeoutNoStar, and ProcessFadeoutResetOnly
each carried their own copy of template loading, SM64-logo reset detection,
the LiveSplit undo/reset/split sequence, and on_transition's
fps/prediction/xcam handling - identical except for incidental formatting
differences, now unified into _FadeoutProcessBase.

Verifies each subclass's distinct split condition, reset-template
detection, and the shared on_transition behavior - and specifically that
the "mismatched judgment" bug is fixed: ProcessFadeoutNoStar.execute() used
to check `as64core.fade_status == self._is_reset(reset_region, template)`
(a fade-status string compared to a bool - never true) instead of
`if self._is_reset(...)`, so reset_frame_one could never trigger a reset
for that variant.

Uses a mocked as64core/config (no real game capture, LiveSplit connection,
or GUI) and the project's real default reset template images so
_is_reset has something meaningful to match against.
"""
import unittest.mock as mock

import cv2
import pytest

import as64processes.standard as standard_mod

TEMPLATE_ONE = cv2.imread("templates/default_reset_one.jpg")
TEMPLATE_TWO = cv2.imread("templates/default_reset_two.jpg")

CONFIG_VALUES = {
    ("advanced", "fadeout_process_frame_rate"): 29.97,
    ("thresholds", "reset_threshold"): 0.1,
    ("thresholds", "black_threshold"): 0.1,
    ("thresholds", "undo_threshold"): 4.5,
    ("advanced", "reset_frame_one"): "templates/default_reset_one.jpg",
    ("advanced", "reset_frame_two"): "templates/default_reset_two.jpg",
    ("general", "srl_mode"): False,
}


@pytest.fixture(autouse=True)
def _assert_templates_loaded():
    assert TEMPLATE_ONE is not None and TEMPLATE_TWO is not None, "default reset templates must exist"


class _FakeSplit:
    def __init__(self, split_type):
        self.split_type = split_type


def _make_as64core_mock(reset_region, fade_status="NO_FADE", split_type="Normal"):
    m = mock.MagicMock()
    m.RESET_REGION = "RESET_REGION"
    m.SPLIT_NORMAL = "Normal"
    m.SPLIT_FADE_ONLY = "Fade Only"
    m.FADEOUT_COMPLETE = "FADEOUT_COMPLETE"
    m.FADEOUT_PARTIAL = "FADEOUT_PARTIAL"
    m.NO_FADE = "NO_FADE"
    m.get_region_rect.return_value = (0, 0, TEMPLATE_ONE.shape[1], TEMPLATE_ONE.shape[0])
    m.get_region.return_value = reset_region
    m.current_time = 100.0
    m.last_split = 0.0
    m.start_on_reset = True
    m.route.initial_star = 0
    m.fade_status = fade_status
    m.current_split.return_value = _FakeSplit(split_type)
    return m


def _make_config_mock():
    m = mock.MagicMock()
    m.get.side_effect = lambda section, key, *a: CONFIG_VALUES[(section, key)]
    return m


@pytest.fixture()
def mocks(request):
    """Patches as64processes.standard's as64core/config; yields the as64core mock for assertions."""
    reset_region, fade_status, split_type = getattr(request, "param", (TEMPLATE_ONE * 0, "NO_FADE", "Normal"))
    as64core_mock = _make_as64core_mock(reset_region, fade_status, split_type)
    config_mock = _make_config_mock()
    with mock.patch.object(standard_mod, "as64core", as64core_mock), \
         mock.patch.object(standard_mod, "config", config_mock):
        yield as64core_mock


# --- ProcessFadeout ---------------------------------------------------------------

@pytest.mark.parametrize("mocks", [(TEMPLATE_ONE * 0, "NO_FADE", "Normal")], indirect=True)
def test_fadeout_split_fires_on_incoming_split(mocks):
    mocks.incoming_split.return_value = True
    with mock.patch.object(standard_mod, "is_black", return_value=True):
        standard_mod.ProcessFadeout().execute()
    mocks.split.assert_called_once()


@pytest.mark.parametrize("mocks", [(TEMPLATE_ONE, "NO_FADE", "Normal")], indirect=True)
def test_fadeout_reset_template_one_triggers_reset(mocks):
    mocks.incoming_split.return_value = False
    with mock.patch.object(standard_mod, "is_black", return_value=False):
        proc = standard_mod.ProcessFadeout()
        result = proc.execute()
    assert result == proc.signals["RESET"]
    mocks.reset.assert_called_once()


# --- ProcessFadeoutNoStar ----------------------------------------------------------

@pytest.mark.parametrize("mocks", [(TEMPLATE_ONE, "NO_FADE", "Fade Only")], indirect=True)
def test_fadeout_no_star_reset_template_one_triggers_reset_bug_fixed(mocks):
    """The original `fade_status == _is_reset(...)` bug meant this never fired."""
    mocks.incoming_split.return_value = False
    with mock.patch.object(standard_mod, "is_black", return_value=False):
        proc = standard_mod.ProcessFadeoutNoStar()
        result = proc.execute()
    assert result == proc.signals["RESET"]


@pytest.mark.parametrize("mocks", [(TEMPLATE_ONE * 0, "NO_FADE", "Fade Only")], indirect=True)
def test_fadeout_no_star_split_condition_uses_star_count_false(mocks):
    mocks.incoming_split.return_value = True
    with mock.patch.object(standard_mod, "is_black", return_value=True):
        standard_mod.ProcessFadeoutNoStar().execute()
    mocks.incoming_split.assert_called_with(star_count=False)
    mocks.split.assert_called_once()


# --- ProcessFadeoutResetOnly -------------------------------------------------------

@pytest.mark.parametrize("mocks", [(TEMPLATE_ONE * 0, "NO_FADE", "Normal")], indirect=True)
def test_fadeout_reset_only_never_splits(mocks):
    with mock.patch.object(standard_mod, "is_black", return_value=True):
        standard_mod.ProcessFadeoutResetOnly().execute()
    mocks.split.assert_not_called()
    mocks.incoming_split.assert_not_called()


@pytest.mark.parametrize("mocks", [(TEMPLATE_TWO, "NO_FADE", "Normal")], indirect=True)
def test_fadeout_reset_only_template_two_triggers_reset(mocks):
    proc = standard_mod.ProcessFadeoutResetOnly()
    result = proc.execute()
    assert result == proc.signals["RESET"]
    mocks.reset.assert_called_once()


# --- Shared behavior ---------------------------------------------------------------

@pytest.mark.parametrize("cls_name", ["ProcessFadeout", "ProcessFadeoutNoStar", "ProcessFadeoutResetOnly"])
def test_on_transition_shared_across_all_variants(mocks, cls_name):
    cls = getattr(standard_mod, cls_name)
    proc = cls()
    proc.on_transition()
    assert mocks.fps == CONFIG_VALUES[("advanced", "fadeout_process_frame_rate")]
    mocks.enable_predictions.assert_called_with(False)
    mocks.enable_xcam_count.assert_called_with(False)
