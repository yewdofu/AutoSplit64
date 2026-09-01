"""
Issue #4 (partial): every runtime function in as64core/__init__.py was a
silent no-op until Base.__init__ overwrote it on the module object, so
calling e.g. as64core.split() or as64core.get_region() before init() just
did nothing instead of signaling a programming error.

Verifies functions Base actually wires up raise NotInitializedError before
init() has run, while stop() (called unconditionally by AutoSplit64.stop()
on app shutdown, including when the app is closed without ever pressing
Start) and the handful of functions Base never wires up regardless of init
state (fadeout/fadein/increment_star/load/save - a separate, pre-existing
dead-code issue, #12) remain safe no-ops.

None of this calls as64core.init() - that would require a real game
capture, LiveSplit connection, and prediction model, none of which are
available in this environment.
"""
import pytest

import as64core


def test_base_is_none_before_init():
    assert as64core._base is None


@pytest.mark.parametrize("call", [
    lambda: as64core.start(),
    lambda: as64core.set_star_count(0),
    lambda: as64core.enable_predictions(True),
    lambda: as64core.enable_fade_count(True),
    lambda: as64core.enable_xcam_count(True),
    lambda: as64core.set_in_game(True),
    lambda: as64core.get_region("x"),
    lambda: as64core.get_region_rect("x"),
    lambda: as64core.register_split_processor("x", None),
    lambda: as64core.split(),
    lambda: as64core.reset(),
    lambda: as64core.skip(),
    lambda: as64core.undo(),
    lambda: as64core.incoming_split(),
    lambda: as64core.current_split(),
    lambda: as64core.split_index(),
    lambda: as64core.set_update_listener(None),
    lambda: as64core.set_error_listener(None),
    lambda: as64core.set_started_listener(None),
    lambda: as64core.force_update(),
])
def test_wired_functions_fail_fast_before_init(call):
    with pytest.raises(as64core.NotInitializedError):
        call()


def test_stop_is_a_safe_noop_before_init():
    # Must not raise - AutoSplit64.stop() calls this unconditionally on
    # shutdown, including before Start has ever been pressed.
    as64core.stop()


@pytest.mark.parametrize("call", [
    lambda: as64core.fadeout(),
    lambda: as64core.fadein(),
    lambda: as64core.increment_star(),
    lambda: as64core.load(),
    lambda: as64core.save(),
])
def test_never_wired_functions_remain_noops(call):
    # Base never overwrites these regardless of init state, so turning them
    # into a fail-fast trap would break the (already dead) call site in
    # as64processes/standard.py rather than catch a real programming error.
    call()
