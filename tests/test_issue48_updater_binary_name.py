"""
Issue #48: the updater's file name is written in two places that have to
agree - the release workflow builds it, and as64core/updater.py launches it
by name. Nothing tied them together, so a rename in one place would ship a
build whose "install update" button starts nothing at all, and the failure
is invisible because as64core/updater.py swallows the WinExec error.

The same applies in the other direction: the updater restarts the app by
name after installing, so that literal has to match the executable
PyInstaller actually produces.

Pins the three names to each other so a rename that misses one fails here
rather than in a release nobody can update from. tools/verify_release_zip.py
checks the built artifact against the same two names at release time; its
resolvers are reused here so there is one definition of each.
"""
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(_ROOT / "tools"))

from verify_release_zip import launched_updater_name, packaged_app_name  # noqa: E402


def _built_updater_name():
    """The name the release workflow builds into dist/AutoSplit64/."""
    text = (_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    match = re.search(r"go build .*-o \.\.\\dist\\AutoSplit64\\(\S+\.exe)", text)
    assert match, "release.yml no longer builds the updater into dist\\AutoSplit64\\"
    return match.group(1)


def test_the_app_launches_the_updater_that_is_actually_built():
    assert launched_updater_name() == _built_updater_name(), \
        "as64core/updater.py launches a different name than release.yml builds"


def test_the_updater_restarts_the_executable_that_is_actually_packaged():
    app_exe = packaged_app_name()
    text = (_ROOT / "updater" / "main.go").read_text(encoding="utf-8")
    assert '"{}"'.format(app_exe) in text, \
        "updater/main.go does not restart {}, the executable PyInstaller builds".format(app_exe)
