"""
Issue #43: the version is written out in four places - pyproject.toml, the
GUI constant, .version, and CLAUDE.md - with nothing tying them together.
A release only needs one of them missed to ship an executable whose About
box, update check, and package metadata disagree.

Pins them to each other so a bump that misses one fails here rather than
in a release, and checks the value is a semver release number, since tags
and the update check compare it as one.
"""
import json
import re
import tomllib
from pathlib import Path

import pytest

from as64gui import constants

_ROOT = Path(__file__).resolve().parent.parent

# MAJOR.MINOR.PATCH, no pre-release or build metadata: the release workflow
# triggers on tags matching [0-9]* and the updater compares plain releases.
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _pyproject_version():
    with open(_ROOT / "pyproject.toml", "rb") as file:
        return tomllib.load(file)["project"]["version"]


def _dot_version():
    with open(_ROOT / ".version", encoding="utf-8") as file:
        return json.load(file)["version"]


def _claude_md_version():
    text = (_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    match = re.search(r"^- Version: (.+)$", text, re.MULTILINE)
    assert match, "CLAUDE.md no longer documents the version as '- Version: X.Y.Z'"
    return match.group(1).strip()


@pytest.mark.parametrize("name, reader", [
    ("pyproject.toml", _pyproject_version),
    (".version", _dot_version),
    ("CLAUDE.md", _claude_md_version),
])
def test_version_matches_the_gui_constant(name, reader):
    assert reader() == constants.VERSION, \
        "{} disagrees with as64gui/constants.py VERSION".format(name)


def test_version_is_a_semver_release():
    assert _SEMVER.match(constants.VERSION), \
        "VERSION must be MAJOR.MINOR.PATCH, got {!r}".format(constants.VERSION)
