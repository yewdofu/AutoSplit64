"""
Issue #41: the Open Route menu only listed .as64 files sitting directly in
the routes directory, while config's route.path can hold any absolute path.
Opening a route from elsewhere via "From File" worked, but switching away
from it dropped it from every menu - the only way back was to walk the file
dialog again.

Verifies the recently opened route history: _updated_recent_routes applies
the history rules (newest first, no duplicates, capped), and
_recent_route_entries lists only what is still worth offering - existing
files outside the routes directory - titling each one from the route file
and falling back to the file name when it cannot be read.

Everything here uses fake stand-in objects, tmp_path files, or a
monkeypatched config.get - none of it touches the real config.json.
"""
import json
import os

from as64core import config
from as64gui import constants
from as64gui.app import App


def _write_route(path, title, category=""):
    path.write_text(json.dumps({
        "__route__": True,
        "title": title,
        "category": category,
        "initial_star": 0,
        "version": "JP",
        "timing": "RTA",
        "splits": [{
            "title": "Split",
            "star_count": 1,
            "fade_out": 1,
            "fade_in": 0,
            "xcam": -1,
            "split_type": "Normal",
            "icon_path": ""
        }]
    }), encoding="utf-8")
    return str(path)


# --- _updated_recent_routes: pure history rules ---------------------------------

def test_opened_route_goes_to_the_front():
    assert App._updated_recent_routes(["b.as64", "c.as64"], "a.as64") == ["a.as64", "b.as64", "c.as64"]


def test_reopening_a_route_moves_it_up_without_duplicating():
    assert App._updated_recent_routes(["b.as64", "a.as64", "c.as64"], "a.as64") == ["a.as64", "b.as64", "c.as64"]


def test_same_path_written_differently_counts_as_one_entry():
    recent = ["C:/Routes/A.as64"]
    assert App._updated_recent_routes(recent, "C:\\Routes\\a.as64") == ["C:\\Routes\\a.as64"]


def test_history_is_capped_keeping_the_newest():
    recent = ["r{}.as64".format(i) for i in range(constants.MAX_RECENT_ROUTES)]

    updated = App._updated_recent_routes(recent, "new.as64")

    assert len(updated) == constants.MAX_RECENT_ROUTES
    assert updated[0] == "new.as64"
    assert recent[-1] not in updated


def test_empty_history_is_handled():
    assert App._updated_recent_routes([], "a.as64") == ["a.as64"]


def test_source_history_is_not_mutated():
    recent = ["b.as64"]
    App._updated_recent_routes(recent, "a.as64")
    assert recent == ["b.as64"]


# --- _remember_recent_route: persists through the single config path ------------

def test_remember_recent_route_saves_updated_history(monkeypatch):
    saved = []

    fake = type("F", (), {})()
    fake._updated_recent_routes = App._updated_recent_routes
    fake._set_and_save = lambda s, k, v: saved.append((s, k, v))
    monkeypatch.setattr(config, "get", lambda *a, **kw: ["b.as64"])

    App._remember_recent_route(fake, "a.as64")

    assert saved == [("route", "recent", ["a.as64", "b.as64"])]


# --- _recent_route_entries: what actually gets offered --------------------------

def _fake_app(recent, monkeypatch, routes_dir):
    fake = type("F", (), {})()
    monkeypatch.setattr(config, "get", lambda *a, **kw: recent)
    monkeypatch.setattr("as64gui.app.user_data_path", lambda *a: str(routes_dir))
    return fake


def test_route_outside_routes_dir_is_listed_by_title(tmp_path, monkeypatch):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    external = _write_route(tmp_path / "elsewhere.as64", "My External Route")

    fake = _fake_app([external], monkeypatch, routes_dir)

    assert App._recent_route_entries(fake) == [["My External Route", external]]


def test_route_inside_routes_dir_is_not_duplicated(tmp_path, monkeypatch):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    inside = _write_route(routes_dir / "inside.as64", "Listed By Category")

    fake = _fake_app([inside], monkeypatch, routes_dir)

    assert App._recent_route_entries(fake) == []


def test_deleted_route_is_dropped(tmp_path, monkeypatch):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    gone = str(tmp_path / "deleted.as64")

    fake = _fake_app([gone], monkeypatch, routes_dir)

    assert App._recent_route_entries(fake) == []


def test_unreadable_route_falls_back_to_file_name(tmp_path, monkeypatch):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    broken = tmp_path / "broken.as64"
    broken.write_text("{ not valid json", encoding="utf-8")

    fake = _fake_app([str(broken)], monkeypatch, routes_dir)

    assert App._recent_route_entries(fake) == [["broken.as64", str(broken)]]


def test_route_without_the_route_flag_falls_back_to_file_name(tmp_path, monkeypatch):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    not_a_route = tmp_path / "settings.as64"
    not_a_route.write_text(json.dumps({"something": "else"}), encoding="utf-8")

    fake = _fake_app([str(not_a_route)], monkeypatch, routes_dir)

    assert App._recent_route_entries(fake) == [["settings.as64", str(not_a_route)]]


def test_history_order_is_preserved(tmp_path, monkeypatch):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    first = _write_route(tmp_path / "first.as64", "First")
    second = _write_route(tmp_path / "second.as64", "Second")

    fake = _fake_app([second, first], monkeypatch, routes_dir)

    assert [title for title, _ in App._recent_route_entries(fake)] == ["Second", "First"]


def test_routes_dir_comparison_ignores_path_style(tmp_path, monkeypatch):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    inside = _write_route(routes_dir / "inside.as64", "Inside")

    # user_data_path returns forward slashes; the stored path uses os.sep.
    fake = type("F", (), {})()
    monkeypatch.setattr(config, "get", lambda *a, **kw: [os.path.normpath(inside)])
    monkeypatch.setattr("as64gui.app.user_data_path", lambda *a: str(routes_dir).replace("\\", "/"))

    assert App._recent_route_entries(fake) == []
