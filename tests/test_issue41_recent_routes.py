"""
Issue #41: the Open Route menu only listed .as64 files sitting directly in
the routes directory, while config's route.path can hold any absolute path.
Opening a route from elsewhere via "From File" worked, but switching away
from it dropped it from every menu - the only way back was to walk the file
dialog again.

The menu now lists the routes that have been opened, wherever they live:
_updated_recent_routes applies the history rules (newest first, no
duplicates, capped), _route_paths decides what is still worth listing,
_load_routes groups it by category, and Reset History trims the list back
to the route currently open.

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


def _history(recent, monkeypatch):
    monkeypatch.setattr(config, "get", lambda *a, **kw: recent)


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
    _history(["b.as64"], monkeypatch)

    App._remember_recent_route(fake, "a.as64")

    assert saved == [("route", "recent", ["a.as64", "b.as64"])]


# --- _route_paths: which files get listed ---------------------------------------

def _routes_dir(tmp_path, recent, monkeypatch):
    """A routes directory at tmp_path/routes, with config's history stubbed out."""
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    _history(recent, monkeypatch)
    monkeypatch.setattr("as64gui.app.user_data_path", lambda *a: str(routes_dir))
    return routes_dir


def test_routes_directory_is_listed_without_being_opened(tmp_path, monkeypatch):
    routes_dir = _routes_dir(tmp_path, [], monkeypatch)
    inside = _write_route(routes_dir / "inside.as64", "Inside")

    assert App._route_paths() == [inside]


def test_non_route_files_in_the_directory_are_ignored(tmp_path, monkeypatch):
    routes_dir = _routes_dir(tmp_path, [], monkeypatch)
    (routes_dir / "notes.txt").write_text("ignore me", encoding="utf-8")

    assert App._route_paths() == []


def test_missing_routes_directory_lists_nothing(tmp_path, monkeypatch):
    _history([], monkeypatch)
    monkeypatch.setattr("as64gui.app.user_data_path", lambda *a: str(tmp_path / "routes"))

    assert App._route_paths() == []


def test_remembered_route_outside_the_directory_is_listed(tmp_path, monkeypatch):
    _routes_dir(tmp_path, [str(tmp_path / "elsewhere.as64")], monkeypatch)
    external = _write_route(tmp_path / "elsewhere.as64", "External")

    assert App._route_paths() == [external]


def test_directory_routes_come_before_remembered_ones(tmp_path, monkeypatch):
    routes_dir = _routes_dir(tmp_path, [str(tmp_path / "external.as64")], monkeypatch)
    external = _write_route(tmp_path / "external.as64", "External")
    inside = _write_route(routes_dir / "inside.as64", "Inside")

    assert App._route_paths() == [inside, external]


def test_remembered_route_inside_the_directory_is_not_listed_twice(tmp_path, monkeypatch):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    inside = _write_route(routes_dir / "inside.as64", "Inside")
    _history([os.path.normpath(inside)], monkeypatch)
    # user_data_path returns forward slashes; the stored path uses os.sep.
    monkeypatch.setattr("as64gui.app.user_data_path", lambda *a: str(routes_dir).replace("\\", "/"))

    listed = [os.path.normcase(os.path.normpath(path)) for path in App._route_paths()]

    assert listed == [os.path.normcase(os.path.normpath(inside))]


def test_deleted_route_is_dropped(tmp_path, monkeypatch):
    _routes_dir(tmp_path, [str(tmp_path / "deleted.as64")], monkeypatch)

    assert App._route_paths() == []


def test_same_path_spelled_differently_is_listed_once(tmp_path, monkeypatch):
    _routes_dir(tmp_path, [], monkeypatch)
    route = _write_route(tmp_path / "route.as64", "Route")
    _history([route, route.replace("\\", "/")], monkeypatch)

    assert App._route_paths() == [route]


def test_empty_history_and_empty_directory_list_nothing(tmp_path, monkeypatch):
    _routes_dir(tmp_path, [], monkeypatch)

    assert App._route_paths() == []


# --- _load_routes: grouping by category -----------------------------------------

def _load(tmp_path, monkeypatch, recent):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir(exist_ok=True)
    _history(recent, monkeypatch)
    monkeypatch.setattr("as64gui.app.user_data_path", lambda *a: str(routes_dir))

    fake = type("F", (), {})()
    fake._route_paths = App._route_paths
    App._load_routes(fake)
    return fake._routes


def test_routes_group_by_category_wherever_they_live(tmp_path, monkeypatch):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    inside = _write_route(routes_dir / "inside.as64", "LBLJ", category="16 Star")
    external = _write_route(tmp_path / "external.as64", "16 Star Custom", category="16 Star")

    assert _load(tmp_path, monkeypatch, [external]) == {
        "16 Star": [["LBLJ", inside], ["16 Star Custom", external]]
    }


def test_uncategorised_routes_share_the_empty_category(tmp_path, monkeypatch):
    route = _write_route(tmp_path / "route.as64", "Upstairs")

    assert _load(tmp_path, monkeypatch, [route]) == {"": [["Upstairs", route]]}


def test_unreadable_route_is_skipped(tmp_path, monkeypatch):
    broken = tmp_path / "broken.as64"
    broken.write_text("{ not valid json", encoding="utf-8")
    good = _write_route(tmp_path / "good.as64", "Good")

    assert _load(tmp_path, monkeypatch, [str(broken), good]) == {"": [["Good", good]]}


def test_json_without_the_route_flag_is_skipped(tmp_path, monkeypatch):
    not_a_route = tmp_path / "settings.as64"
    not_a_route.write_text(json.dumps({"something": "else"}), encoding="utf-8")

    assert _load(tmp_path, monkeypatch, [str(not_a_route)]) == {}


# --- _history_after_reset: what survives Reset History ---------------------------

def test_reset_keeps_only_the_open_route():
    assert App._history_after_reset("C:/Routes/open.as64") == ["C:/Routes/open.as64"]


def test_reset_with_no_open_route_empties_the_history():
    assert App._history_after_reset("") == []


# --- reset_route_history: confirmation gates the reset ---------------------------

def _reset_fake(monkeypatch, answer):
    from PyQt5 import QtWidgets

    calls = []
    fake = type("F", (), {})()
    fake._history_after_reset = App._history_after_reset
    fake._set_and_save = lambda s, k, v: calls.append((s, k, v))
    fake._load_routes = lambda: calls.append("load_routes")

    monkeypatch.setattr(config, "get", lambda *a, **kw: "C:/Routes/open.as64")
    monkeypatch.setattr(QtWidgets.QMessageBox, "question", staticmethod(lambda *a, **kw: answer))

    return fake, calls


def test_declining_the_confirmation_changes_nothing(monkeypatch):
    from PyQt5 import QtWidgets

    fake, calls = _reset_fake(monkeypatch, QtWidgets.QMessageBox.No)

    App.reset_route_history(fake)

    assert calls == []


def test_confirming_saves_the_trimmed_history_and_reloads(monkeypatch):
    from PyQt5 import QtWidgets

    fake, calls = _reset_fake(monkeypatch, QtWidgets.QMessageBox.Yes)

    App.reset_route_history(fake)

    assert calls == [("route", "recent", ["C:/Routes/open.as64"]), "load_routes"]
