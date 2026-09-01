"""
Issue #41: the Open Route menu only listed .as64 files sitting directly in
the routes directory, while config's route.path can hold any absolute path.
Opening a route from elsewhere via "From File" worked, but switching away
from it dropped it from every menu - the only way back was to walk the file
dialog again.

Verifies the recently opened route history: _updated_recent_routes applies
the history rules (newest first, no duplicates, capped), and _route_paths /
_load_routes fold remembered routes into the same category-grouped listing
as the routes directory, so where a route file lives stays invisible to the
menu.

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


def _routes_dir(tmp_path, recent, monkeypatch):
    """A routes directory at tmp_path/routes, with config's history stubbed out."""
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    monkeypatch.setattr(config, "get", lambda *a, **kw: recent)
    monkeypatch.setattr("as64gui.app.user_data_path", lambda *a: str(routes_dir))
    return routes_dir


# --- _updated_recent_routes: pure history rules ---------------------------------

def test_opened_route_goes_to_the_front():
    assert App._updated_recent_routes(["b.as64", "c.as64"], "a.as64") == ["a.as64", "b.as64", "c.as64"]


def test_reopening_a_route_moves_it_up_without_duplicating():
    assert App._updated_recent_routes(["b.as64", "a.as64", "c.as64"], "a.as64") == ["a.as64", "b.as64", "c.as64"]


def test_same_path_written_differently_counts_as_one_entry():
    assert App._updated_recent_routes(["C:/Routes/A.as64"], "C:\\Routes\\a.as64") == ["C:\\Routes\\a.as64"]


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


# --- _route_paths: which files get listed ---------------------------------------

def test_routes_directory_is_listed(tmp_path, monkeypatch):
    routes_dir = _routes_dir(tmp_path, [], monkeypatch)
    inside = _write_route(routes_dir / "inside.as64", "Inside")

    assert App._route_paths() == [inside]


def test_non_route_files_in_the_directory_are_ignored(tmp_path, monkeypatch):
    routes_dir = _routes_dir(tmp_path, [], monkeypatch)
    (routes_dir / "notes.txt").write_text("ignore me", encoding="utf-8")

    assert App._route_paths() == []


def test_remembered_route_outside_the_directory_is_listed(tmp_path, monkeypatch):
    _routes_dir(tmp_path, [str(tmp_path / "elsewhere.as64")], monkeypatch)
    external = _write_route(tmp_path / "elsewhere.as64", "External")

    assert App._route_paths() == [external]


def test_remembered_route_inside_the_directory_is_not_listed_twice(tmp_path, monkeypatch):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    inside = _write_route(routes_dir / "inside.as64", "Inside")
    monkeypatch.setattr(config, "get", lambda *a, **kw: [os.path.normpath(inside)])
    # user_data_path returns forward slashes; the stored path uses os.sep.
    monkeypatch.setattr("as64gui.app.user_data_path", lambda *a: str(routes_dir).replace("\\", "/"))

    listed = [os.path.normcase(os.path.normpath(path)) for path in App._route_paths()]

    assert listed == [os.path.normcase(os.path.normpath(inside))]


def test_deleted_route_is_dropped(tmp_path, monkeypatch):
    _routes_dir(tmp_path, [str(tmp_path / "deleted.as64")], monkeypatch)

    assert App._route_paths() == []


def test_directory_routes_come_before_remembered_ones(tmp_path, monkeypatch):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    external = _write_route(tmp_path / "external.as64", "External")
    monkeypatch.setattr(config, "get", lambda *a, **kw: [external])
    monkeypatch.setattr("as64gui.app.user_data_path", lambda *a: str(routes_dir))
    inside = _write_route(routes_dir / "inside.as64", "Inside")

    assert App._route_paths() == [inside, external]


def test_missing_routes_directory_is_created(tmp_path, monkeypatch):
    routes_dir = tmp_path / "routes"
    monkeypatch.setattr(config, "get", lambda *a, **kw: [])
    monkeypatch.setattr("as64gui.app.user_data_path", lambda *a: str(routes_dir))

    assert App._route_paths() == []
    assert routes_dir.is_dir()


# --- _load_routes: remembered routes group by category like any other -----------

def _load(fake=None):
    fake = fake or type("F", (), {})()
    fake._route_paths = App._route_paths
    App._load_routes(fake)
    return fake._routes


def test_remembered_route_is_grouped_by_its_own_category(tmp_path, monkeypatch):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    external = _write_route(tmp_path / "external.as64", "16 Star Custom", category="16 Star")
    monkeypatch.setattr(config, "get", lambda *a, **kw: [external])
    monkeypatch.setattr("as64gui.app.user_data_path", lambda *a: str(routes_dir))
    inside = _write_route(routes_dir / "inside.as64", "LBLJ", category="16 Star")

    assert _load() == {"16 Star": [["LBLJ", inside], ["16 Star Custom", external]]}


def test_uncategorised_routes_share_the_empty_category(tmp_path, monkeypatch):
    routes_dir = _routes_dir(tmp_path, [], monkeypatch)
    inside = _write_route(routes_dir / "inside.as64", "Upstairs")

    assert _load() == {"": [["Upstairs", inside]]}


def test_unreadable_route_is_skipped(tmp_path, monkeypatch):
    routes_dir = _routes_dir(tmp_path, [], monkeypatch)
    (routes_dir / "broken.as64").write_text("{ not valid json", encoding="utf-8")
    good = _write_route(routes_dir / "good.as64", "Good")

    assert _load() == {"": [["Good", good]]}


def test_json_without_the_route_flag_is_skipped(tmp_path, monkeypatch):
    routes_dir = _routes_dir(tmp_path, [], monkeypatch)
    (routes_dir / "settings.as64").write_text(json.dumps({"something": "else"}), encoding="utf-8")

    assert _load() == {}
