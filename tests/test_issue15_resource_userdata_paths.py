"""
Issue #15: resource_utils mixed three different bases (sys.argv[0]'s
directory, the current working directory, and PyInstaller's _MEIPASS)
across base_path/absolute_path/resource_path, so it wasn't obvious which
callers were resolving read-only assets vs. writable user data - and
base_path's use of sys.argv[0] made a dev run's resolution depend on how the
interpreter was invoked.

Verifies the two replacement APIs (resource_path for bundled read-only
assets, user_data_path for writable data) both anchor off resource_utils.py's
own location - not argv or cwd - and that the relative<->absolute helpers
round-trip through user_data_path.
"""
from pathlib import Path

from as64core import resource_utils

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_resource_path_anchors_at_project_root_when_not_frozen():
    result = resource_utils.resource_path("defaults.json")
    assert result == str(PROJECT_ROOT / "defaults.json").replace("\\", "/")


def test_user_data_path_anchors_at_project_root_when_not_frozen():
    result = resource_utils.user_data_path("config.json")
    assert result == str(PROJECT_ROOT / "config.json").replace("\\", "/")


def test_user_data_path_with_no_argument_returns_root():
    assert resource_utils.user_data_path() == str(PROJECT_ROOT).replace("\\", "/")


def test_rel_to_abs_and_abs_to_rel_round_trip():
    rel = "resources/gui/some_icon.png"
    absolute = resource_utils.rel_to_abs(rel)
    assert absolute == str(PROJECT_ROOT / rel).replace("\\", "/")
    assert resource_utils.abs_to_rel(absolute) == rel


def test_rel_to_abs_leaves_already_absolute_paths_untouched():
    already_absolute = str(PROJECT_ROOT / "somewhere" / "file.txt")
    assert resource_utils.rel_to_abs(already_absolute) == already_absolute


def test_resource_and_user_data_share_the_same_root_when_not_frozen():
    # Dev and a packaged build should resolve to the same relative layout;
    # in dev, that means both APIs share one root.
    assert resource_utils.resource_path("x") .rsplit("/", 1)[0] == \
           resource_utils.user_data_path("x").rsplit("/", 1)[0]
