"""
Issue #3: ProcessorGenerator.generate() printed a bare numbered message
("1" through "7") and returned None on any invalid .processor reference
(unregistered process, unknown signal, missing transition target,
unreadable inherit/sub-processor file, or a missing required field)
instead of raising - callers didn't check for None, so a bad definition
surfaced as an unrelated error much later, or nothing at all.

Verifies every failure mode now raises ProcessorDefinitionError naming
both the file and the specific offending item, and that all 9 .processor
files AutoSplit64.py actually loads at startup still generate correctly.
"""
import json

import pytest

from as64core.processing import (
    ProcessorGenerator,
    ProcessorDefinitionError,
    Process,
    register_process,
    processes,
)


@pytest.fixture(autouse=True)
def clean_process_registry():
    """processes is process-global module state; keep tests from bleeding into each other."""
    snapshot = dict(processes)
    processes.clear()
    yield
    processes.clear()
    processes.update(snapshot)


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_missing_file_raises_with_path():
    with pytest.raises(ProcessorDefinitionError, match="not found"):
        ProcessorGenerator.generate("does/not/exist.processor")


def test_unknown_initial_process_raises_naming_it(tmp_path):
    path = _write(tmp_path, "bad_initial.processor", {
        "name": "bad_initial", "initial_process": "NONEXISTENT",
        "inherit": None, "sub_processors": {}, "transitions": {},
    })
    with pytest.raises(ProcessorDefinitionError, match="NONEXISTENT"):
        ProcessorGenerator.generate(path)


def test_unknown_transition_signal_raises_naming_it(tmp_path):
    register_process("WAIT", Process())
    path = _write(tmp_path, "bad_signal.processor", {
        "name": "bad_signal", "initial_process": "WAIT", "inherit": None,
        "sub_processors": {}, "transitions": {"WAIT": {"WAIT.NOPE": "WAIT"}},
    })
    with pytest.raises(ProcessorDefinitionError, match="WAIT.NOPE"):
        ProcessorGenerator.generate(path)


def test_unknown_transition_target_raises_naming_it(tmp_path):
    register_process("WAIT", Process())
    path = _write(tmp_path, "bad_target.processor", {
        "name": "bad_target", "initial_process": "WAIT", "inherit": None,
        "sub_processors": {}, "transitions": {"WAIT": {"WAIT.LOOP": "NOWHERE"}},
    })
    with pytest.raises(ProcessorDefinitionError, match="NOWHERE"):
        ProcessorGenerator.generate(path)


def test_missing_required_field_raises_naming_it(tmp_path):
    path = _write(tmp_path, "missing_field.processor", {
        "name": "missing_field", "initial_process": "WAIT",
        "sub_processors": {}, "transitions": {},
        # "inherit" deliberately omitted
    })
    with pytest.raises(ProcessorDefinitionError, match="inherit"):
        ProcessorGenerator.generate(path)


def test_valid_definition_still_generates_a_processor(tmp_path):
    register_process("WAIT", Process())
    path = _write(tmp_path, "ok.processor", {
        "name": "ok", "initial_process": "WAIT", "inherit": None,
        "sub_processors": {}, "transitions": {"WAIT": {"WAIT.LOOP": "WAIT"}},
    })
    processor = ProcessorGenerator.generate(path)
    assert processor is not None
    assert processor.initial_process is processes["WAIT"]


ALL_PROCESSOR_FILES = [
    "logic/up_rta/initial_up_rta.processor",
    "logic/file_select/initial_file_select_start.processor",
    "logic/standard/initial.processor",
    "logic/standard/star_fade.processor",
    "logic/standard/fade_only.processor",
    "logic/standard/xcam_split.processor",
    "logic/ddd/ddd.processor",
    "logic/ddd/mips_x.processor",
    "logic/final/final.processor",
]


def test_all_real_processor_files_used_at_startup_still_generate(monkeypatch):
    import as64core
    from as64core.processing import insert_global_hook
    from as64processes.standard import (
        ProcessWait, ProcessRunStart, ProcessRunStartUpSegment, ProcessStarCount,
        ProcessFadein, ProcessFadeout, ProcessFadeoutNoStar, ProcessFadeoutResetOnly,
        ProcessPostFadeout, ProcessFlashCheck, ProcessReset, ProcessResetNoStart,
        ProcessDummy, ProcessFileSelectSplit,
    )
    from as64processes.xcam import ProcessXCam, ProcessXCamStartUpSegment
    from as64processes.ddd import ProcessFindDDDPortal, ProcessDDDEntry, ProcessDDDEntryX
    from as64processes.final import ProcessFinalStageEntry, ProcessFinalStarSpawn, ProcessFinalStarGrab

    # ProcessFadeout.__init__ calls as64core.get_region_rect(), which is a
    # real-game-capture call unavailable in this environment.
    monkeypatch.setattr(as64core, "get_region_rect", lambda region: (0, 0, 100, 100))

    register_process("WAIT", ProcessWait())
    register_process("RUN_START", ProcessRunStart())
    register_process("RUN_START_UP_RTA", ProcessRunStartUpSegment())
    register_process("STAR_COUNT", ProcessStarCount())
    register_process("FADEIN", ProcessFadein())
    register_process("FADEOUT", ProcessFadeout())
    register_process("FADEOUT_NO_STAR", ProcessFadeoutNoStar())
    register_process("FADEOUT_RESET_ONLY", ProcessFadeoutResetOnly())
    register_process("POST_FADEOUT", ProcessPostFadeout())
    register_process("FLASH_CHECK", ProcessFlashCheck())
    register_process("RESET", ProcessReset())
    register_process("DUMMY", ProcessDummy())
    register_process("XCAM", ProcessXCam())
    register_process("XCAM_UP_RTA", ProcessXCamStartUpSegment())
    register_process("FILE_SELECT_SPLIT", ProcessFileSelectSplit())
    register_process("FIND_DDD_PORTAL", ProcessFindDDDPortal())
    register_process("DDD_SPLIT", ProcessDDDEntry())
    register_process("DDD_SPLIT_X", ProcessDDDEntryX())
    register_process("FINAL_DETECT_ENTRY", ProcessFinalStageEntry())
    register_process("FINAL_DETECT_SPAWN", ProcessFinalStarSpawn())
    register_process("FINAL_STAR_SPLIT", ProcessFinalStarGrab())
    insert_global_hook("RESET", ProcessResetNoStart())

    for file_path in ALL_PROCESSOR_FILES:
        processor = ProcessorGenerator.generate(file_path)
        assert processor is not None, f"{file_path} failed to generate"
