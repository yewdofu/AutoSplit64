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


def test_up_rta_xcam_detection_starts_timer(monkeypatch):
    import as64processes.xcam as xcam_module

    calls = []
    runtime = SimpleNamespace(
        fade_status="none",
        FADEOUT_COMPLETE="fadeout-complete",
        FADEOUT_PARTIAL="fadeout-partial",
        fadeout_count=1,
        XCAM_REGION="xcam",
        fps=10,
        enable_predictions=lambda enabled: calls.append(("predictions", enabled)),
        get_region=lambda region: np.full((4, 4, 3), [10, 20, 100], dtype=np.uint8),
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
        fadein_count=2,
        fadeout_count=3,
        star_count=74,
        prediction_info=SimpleNamespace(prediction=-1, probability=0.0),
        route=SimpleNamespace(initial_star=74, splits=[SimpleNamespace(star_count=78)]),
        split_index=lambda: 0,
        current_split=lambda: SimpleNamespace(star_count=78),
        get_region=lambda region: np.zeros((4, 4, 3), dtype=np.uint8),
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
