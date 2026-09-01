"""
Issue #19: with a capture device configured, any startup failure - including
"LiveSplit not connected" - sent AutoSplit64.on_error into the device
reconnect loop. The device itself opened fine, so the retry succeeded and
re-started the core, which failed the same check again, looping forever
between "Capture Wait" and "Start" and never showing the error.

Verifies errors are now classified: only capture-source failures are
retryable, everything else is surfaced to the user.
"""
import ast
from pathlib import Path

import pytest

BASE_SOURCE = Path(__file__).resolve().parent.parent / "as64core" / "base.py"

# (message fragment, expected capture_recoverable)
EXPECTED_CLASSIFICATION = [
    ("Could not open capture device", True),
    ("Could not find ", True),
    ("Could not capture from device", True),
    ("Could not capture ", True),
    ("Unable to capture from device", True),
    ("Unable to capture ", True),
    ("Capture windows dimensions have changed", False),
    ("Could not connect to LiveSplit", False),
    ("Unable to load route ", False),
    ("Unable to load prediction model ", False),
    ("LiveSplit connection failed", False),
    ("An error occurred while processing ", False),
]


def _error_calls():
    """Every _error_occurred(...) call in base.py, as (source_text, passes_recoverable_true)."""
    tree = ast.parse(BASE_SOURCE.read_text(encoding="utf-8"))
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "_error_occurred"):
            continue
        recoverable = any(
            kw.arg == "capture_recoverable"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in node.keywords
        )
        calls.append((ast.dump(node.args[0]) if node.args else "", recoverable))
    return calls


@pytest.mark.parametrize("fragment,expected_recoverable", EXPECTED_CLASSIFICATION)
def test_error_sites_are_classified_correctly(fragment, expected_recoverable):
    matching = [rec for src, rec in _error_calls() if fragment in src]
    assert matching, f"no _error_occurred call found containing {fragment!r}"
    assert all(rec is expected_recoverable for rec in matching), (
        f"{fragment!r}: expected capture_recoverable={expected_recoverable}, got {matching}"
    )


def test_on_error_only_retries_capture_recoverable_failures(monkeypatch):
    import AutoSplit64 as entry_point
    from as64core import config

    monkeypatch.setattr(config, "get", lambda section, key, *a: "device")

    emitted = []
    started = []
    retried = []

    fake = type("FakeSelf", (), {})()
    fake._device_retrying = False
    fake.error = type("Sig", (), {"emit": staticmethod(lambda msg: emitted.append(msg))})()
    fake.capture_waiting = type("Sig", (), {"emit": staticmethod(lambda v: retried.append(v))})()
    fake.app = type("App", (), {"set_started": staticmethod(lambda v: started.append(v))})()
    fake._retry_device_capture = lambda: None

    # Non-recoverable (e.g. LiveSplit not connected) must surface, not retry.
    entry_point.AutoSplit64.on_error(fake, "Could not connect to LiveSplit.", capture_recoverable=False)
    assert emitted == ["Could not connect to LiveSplit."]
    assert started == [False]
    assert retried == []
    assert fake._device_retrying is False


def test_on_error_still_retries_when_the_capture_device_is_at_fault(monkeypatch):
    import AutoSplit64 as entry_point
    from as64core import config

    monkeypatch.setattr(config, "get", lambda section, key, *a: "device")
    monkeypatch.setattr(entry_point, "Thread", lambda target, daemon=None: type("T", (), {"start": staticmethod(lambda: None)})())

    emitted = []
    waiting = []

    fake = type("FakeSelf", (), {})()
    fake._device_retrying = False
    fake.error = type("Sig", (), {"emit": staticmethod(lambda msg: emitted.append(msg))})()
    fake.capture_waiting = type("Sig", (), {"emit": staticmethod(lambda v: waiting.append(v))})()
    fake.app = type("App", (), {"set_started": staticmethod(lambda v: None)})()
    fake._retry_device_capture = lambda: None

    entry_point.AutoSplit64.on_error(fake, "Could not open capture device (index 0)", capture_recoverable=True)
    assert waiting == [True]
    assert emitted == []
    assert fake._device_retrying is True
