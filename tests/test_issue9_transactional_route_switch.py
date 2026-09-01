"""
Issue #9: _save_open_route saved the candidate path and restarted the core
(via open_route -> _reset) before validation ran. On an invalid route it
displayed an error, then saved the previous path and restarted the core a
second time to recover - so picking a bad route file caused two restarts
and a moment where config pointed at a route that had already failed to
load.

Verifies _load_and_validate_route is side-effect-free (no config, display,
or core access), and that _save_open_route only saves/displays/restarts -
each exactly once - on success, leaving everything untouched on failure.
Also verifies open_route's three branches (empty path, missing file, valid
route) keep their original return values and reset-call behavior.

Everything here uses fake stand-in objects or monkeypatches config.get -
none of it touches the real config.json or instantiates a QApplication.
"""
from as64gui.app import App


class _FakeSelf:
    pass


def _fake_with_recorder():
    fake = _FakeSelf()
    fake._load_and_validate_route = App._load_and_validate_route
    fake.calls = []
    fake._reset = lambda: fake.calls.append("reset")
    fake._display_route = lambda route: fake.calls.append("display")
    fake._load_route_dir = lambda: fake.calls.append("load_route_dir")
    fake._set_and_save = lambda s, k, v: fake.calls.append(("set_and_save", s, k, v))
    fake.display_error_message = lambda msg, title: fake.calls.append(("error", msg))
    return fake


# --- _load_and_validate_route: pure, no side effects ----------------------------

def test_load_and_validate_missing_file():
    route, error, missing = App._load_and_validate_route("C:/nonexistent/does_not_exist.as64")
    assert route is None
    assert error == "Could not load route"
    assert missing is True


def test_load_and_validate_real_route_file():
    route, error, missing = App._load_and_validate_route("routes/16_lblj.as64")
    assert route is not None
    assert error is None
    assert missing is False


# --- _save_open_route: transactional ---------------------------------------------

def test_save_open_route_failure_touches_nothing():
    fake = _fake_with_recorder()
    App._save_open_route(fake, "C:/nonexistent/bad_route.as64")
    assert fake.calls == [("error", "Could not load route")]


def test_save_open_route_success_saves_displays_restarts_once_in_order():
    fake = _fake_with_recorder()
    App._save_open_route(fake, "routes/16_lblj.as64")
    kinds = [c[0] if isinstance(c, tuple) else c for c in fake.calls]
    assert kinds == ["set_and_save", "display", "reset"]


# --- open_route: preserves its three original branches --------------------------

def test_open_route_empty_configured_path(monkeypatch):
    from as64core import config

    fake = _fake_with_recorder()
    monkeypatch.setattr(config, "get", lambda *a, **kw: "")

    result = App.open_route(fake)

    assert fake.calls == ["reset"]
    assert result is None


def test_open_route_missing_file_resets_first_then_cleans_up(monkeypatch):
    from as64core import config

    fake = _fake_with_recorder()
    monkeypatch.setattr(config, "get", lambda *a, **kw: "C:/nonexistent/bad.as64")

    result = App.open_route(fake)

    assert fake.calls[0] == "reset"
    assert ("error", "Could not load route") in fake.calls
    assert "load_route_dir" in fake.calls
    assert ("set_and_save", "route", "path", "") in fake.calls
    assert "display" not in fake.calls
    assert result is False


def test_open_route_valid_route_resets_first_then_displays(monkeypatch):
    from as64core import config

    fake = _fake_with_recorder()
    monkeypatch.setattr(config, "get", lambda *a, **kw: "routes/16_lblj.as64")

    result = App.open_route(fake)

    assert fake.calls[0] == "reset"
    assert "display" in fake.calls
    assert not any(isinstance(c, tuple) and c[0] == "error" for c in fake.calls)
    assert result is True
