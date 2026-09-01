"""Regression tests for File Select and Up RTA timer startup state."""

from types import SimpleNamespace

import numpy as np


def test_new_base_resets_timing_detection_state(monkeypatch):
    import as64core.base as base_module

    runtime = SimpleNamespace(
        current_time=123.0,
        last_split=122.0,
        collection_time=121.0,
        xcam_count=4,
        xcam_percent=0.5,
        in_xcam=True,
        fadeout_count=7,
        fadein_count=6,
        fade_status="stale",
    )
    monkeypatch.setattr(base_module, "as64", runtime, raising=False)

    base = base_module.Base.__new__(base_module.Base)
    base._reset_runtime_state()

    assert runtime.current_time == 0.0
    assert runtime.last_split == 0
    assert runtime.collection_time == 0
    assert runtime.xcam_count == 0
    assert runtime.xcam_percent == 0.0
    assert runtime.in_xcam is False
    assert runtime.fadeout_count == 0
    assert runtime.fadein_count == 0
    assert runtime.fade_status == base_module.NO_FADE


def test_manual_livesplit_reset_rearms_initial_timing(monkeypatch):
    import as64core.base as base_module

    initial_split = SimpleNamespace(star_count=81)
    runtime = SimpleNamespace(
        star_count=81,
        fadeout_count=2,
        fadein_count=1,
        xcam_count=3,
        xcam_percent=0.8,
        in_xcam=True,
        fade_status="stale",
        last_split=123.0,
        collection_time=0.0,
        previous_split_initial_star=0,
        next_split_split_star=0,
    )
    monkeypatch.setattr(base_module, "as64", runtime, raising=False)

    base = base_module.Base.__new__(base_module.Base)
    base._route = SimpleNamespace(initial_star=74, splits=[initial_split])
    base._current_split = initial_split
    base._last_livesplit_index = 0
    base._in_game = True
    base._make_predictions = False
    base._count_fades = True
    base._count_xcams = True
    base._split_on_current_xcam = True
    base._matching_consecutive_predictions = 4
    base._previous_prediction = SimpleNamespace(prediction=81, probability=1.0)
    base._prediction_processing_length = 3
    base._update_listener = lambda *args: None

    base._sync_livesplit_state(-1)

    assert base._last_livesplit_index == -1
    assert base._in_game is False
    assert base._make_predictions is True
    assert base._count_fades is False
    assert base._count_xcams is False
    assert base._split_on_current_xcam is False
    assert runtime.star_count == 74
    assert runtime.fadeout_count == 0
    assert runtime.fadein_count == 0
    assert runtime.xcam_count == 0
    assert runtime.xcam_percent == 0.0
    assert runtime.in_xcam is False
    assert runtime.fade_status == base_module.NO_FADE
    assert runtime.last_split == 0


def test_initial_stopped_livesplit_does_not_rearm(monkeypatch):
    import as64core.base as base_module

    base = base_module.Base.__new__(base_module.Base)
    base._last_livesplit_index = None
    base.split_index = lambda: 0
    rearm_calls = []
    base._rearm_initial_timing = lambda: rearm_calls.append(True)

    base._sync_livesplit_state(-1)
    base._sync_livesplit_state(-1)

    assert rearm_calls == []
    assert base._last_livesplit_index == -1


def test_up_rta_xcam_detection_starts_timer(monkeypatch):
    import as64processes.xcam as xcam_module

    calls = []
    runtime = SimpleNamespace(
        fade_status="none",
        FADEOUT_COMPLETE="fadeout-complete",
        FADEOUT_PARTIAL="fadeout-partial",
        fadeout_count=1,
        in_xcam=True,
        fps=10,
        enable_predictions=lambda enabled: calls.append(("predictions", enabled)),
        split=lambda: calls.append(("split",)),
        set_in_game=lambda in_game: calls.append(("in_game", in_game)),
    )
    monkeypatch.setattr(xcam_module, "as64core", runtime)

    process = xcam_module.ProcessXCamStartUpSegment()
    result = process.execute()

    assert result is process.signals["START"]
    assert ("split",) in calls
    assert ("in_game", True) in calls
    assert runtime.fadeout_count == 0


def test_up_rta_waits_for_configured_xcam_detection(monkeypatch):
    import as64processes.xcam as xcam_module

    calls = []
    runtime = SimpleNamespace(
        fade_status="none",
        FADEOUT_COMPLETE="fadeout-complete",
        FADEOUT_PARTIAL="fadeout-partial",
        fadeout_count=1,
        in_xcam=False,
        fps=10,
        split=lambda: calls.append(("split",)),
    )
    monkeypatch.setattr(xcam_module, "as64core", runtime)

    process = xcam_module.ProcessXCamStartUpSegment()

    assert process.execute() is process.signals["LOOP"]
    assert calls == []


def test_file_select_detection_starts_timer(monkeypatch):
    import as64processes.standard as standard_module

    calls = []

    def config_get(section, key):
        values = {
            ("general", "mid_run_start_enabled"): False,
            ("advanced", "file_select_frame_offset"): -29,
            ("thresholds", "probability_threshold"): 0.9,
        }
        return values[(section, key)]

    runtime = SimpleNamespace(
        fade_status="none",
        FADEOUT_COMPLETE="fadeout-complete",
        FADEOUT_PARTIAL="fadeout-partial",
        FADEOUT_REGION="fadeout",
        fadein_count=1,
        fadeout_count=3,
        star_count=74,
        prediction_info=SimpleNamespace(prediction=-1, probability=0.0),
        route=SimpleNamespace(initial_star=74, splits=[SimpleNamespace(star_count=78)]),
        split_index=lambda: 0,
        current_split=lambda: SimpleNamespace(star_count=78),
        get_region=lambda region: np.full((4, 4, 3), [0, 0, 100], dtype=np.uint8),
        split=lambda: calls.append(("split",)),
        set_in_game=lambda in_game: calls.append(("in_game", in_game)),
    )
    monkeypatch.setattr(standard_module.config, "get", config_get)
    monkeypatch.setattr(standard_module, "as64core", runtime)
    monkeypatch.setattr(standard_module.time, "sleep", lambda delay: calls.append(("sleep", delay)))

    process = standard_module.ProcessFileSelectSplit()
    result = process.execute()

    assert result is process.signals["COMPLETE"]
    assert ("split",) in calls
    assert ("in_game", True) in calls
    assert any(call[0] == "sleep" for call in calls)
    assert runtime.fadein_count == 0
    assert runtime.fadeout_count == 0


def test_file_select_waits_for_transition_colour(monkeypatch):
    import as64processes.standard as standard_module

    calls = []

    def config_get(section, key):
        values = {
            ("general", "mid_run_start_enabled"): False,
            ("advanced", "file_select_frame_offset"): -29,
            ("thresholds", "probability_threshold"): 0.9,
        }
        return values[(section, key)]

    runtime = SimpleNamespace(
        fade_status="none",
        FADEOUT_COMPLETE="fadeout-complete",
        FADEOUT_PARTIAL="fadeout-partial",
        FADEOUT_REGION="fadeout",
        fadein_count=1,
        fadeout_count=0,
        star_count=74,
        prediction_info=SimpleNamespace(prediction=-1, probability=0.0),
        route=SimpleNamespace(initial_star=74, splits=[SimpleNamespace(star_count=78)]),
        split_index=lambda: 0,
        current_split=lambda: SimpleNamespace(star_count=78),
        get_region=lambda region: np.full((4, 4, 3), 100, dtype=np.uint8),
        split=lambda: calls.append(("split",)),
    )
    monkeypatch.setattr(standard_module.config, "get", config_get)
    monkeypatch.setattr(standard_module, "as64core", runtime)

    process = standard_module.ProcessFileSelectSplit()

    assert process.execute() is process.signals["LOOP"]
    assert calls == []
