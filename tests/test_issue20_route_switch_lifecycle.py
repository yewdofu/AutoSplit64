"""Regression tests for non-blocking, repeated route-switch shutdowns."""

from threading import Event, Lock


def test_gui_stop_schedules_the_exact_base_off_thread(monkeypatch):
    import AutoSplit64 as entry_point

    stopped = []

    class FakeBase:
        def stop(self):
            stopped.append("old-base")

    old_base = FakeBase()
    scheduled = []

    class FakeThread:
        def __init__(self, target, daemon=False):
            self.target = target
            self.daemon = daemon
            scheduled.append(self)

        def start(self):
            # Returning without invoking the target proves the GUI-facing
            # method does not wait for resource cleanup.
            pass

    monkeypatch.setattr(entry_point, "Thread", FakeThread)
    monkeypatch.setattr(entry_point.as64core, "_base", old_base)
    monkeypatch.setattr(
        entry_point.as64core,
        "stop",
        lambda: (_ for _ in ()).throw(AssertionError("global stop must not be scheduled")),
    )

    fake = type("FakeSelf", (), {})()
    fake._device_retrying = True
    fake._lifecycle_lock = Lock()
    fake._start_requested = True
    fake._start_generation = 7

    entry_point.AutoSplit64.stop(fake)

    assert fake._device_retrying is False
    assert fake._start_requested is False
    assert fake._start_generation == 8
    assert len(scheduled) == 1
    assert scheduled[0].daemon is True
    assert scheduled[0].target == old_base.stop
    assert stopped == []

    scheduled[0].target()
    assert stopped == ["old-base"]


def test_base_resource_release_is_idempotent(monkeypatch):
    import as64core.base as base_module

    released = []
    disconnected = []

    class FakeDeviceCapture:
        def release(self):
            released.append(True)

    monkeypatch.setattr(base_module, "DeviceCapture", FakeDeviceCapture)
    monkeypatch.setattr(base_module.livesplit, "disconnect", lambda sock: disconnected.append(sock))

    base = base_module.Base.__new__(base_module.Base)
    base._running = True
    base._stop_event = Event()
    base._stop_lock = Lock()
    base._resources_released = False
    base._game_capture = FakeDeviceCapture()
    base._ls_socket = object()

    base.stop()
    base.stop()

    assert base._running is False
    assert base._stop_event.is_set()
    assert released == [True]
    assert disconnected == [base._ls_socket]
