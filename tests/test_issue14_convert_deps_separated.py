"""
Issue #14: TensorFlow/tf2onnx/tf-keras (only needed by
tools/convert_to_onnx.py) lived in the "dev" group alongside pyinstaller, so
`uv sync` and the release build pulled them in too. Verifies they've moved
to their own "convert" group that isn't a uv default group, and that the
"dev" group is free of them.
"""
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONVERT_ONLY_PACKAGES = {"tensorflow", "tf2onnx", "tf-keras"}


def _load_pyproject():
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def _package_names(requirement_strings):
    # Strip version specifiers etc. - just need the bare package name.
    names = set()
    for req in requirement_strings:
        name = req
        for sep in ("==", ">=", "<=", ">", "<", "~=", "!=", "["):
            name = name.split(sep)[0]
        names.add(name.strip())
    return names


def test_dev_group_excludes_conversion_packages():
    groups = _load_pyproject()["dependency-groups"]
    dev_packages = _package_names(groups["dev"])
    assert dev_packages.isdisjoint(CONVERT_ONLY_PACKAGES), (
        f"conversion-only packages still in dev group: {dev_packages & CONVERT_ONLY_PACKAGES}"
    )


def test_convert_group_has_conversion_packages():
    groups = _load_pyproject()["dependency-groups"]
    assert "convert" in groups
    convert_packages = _package_names(groups["convert"])
    assert CONVERT_ONLY_PACKAGES.issubset(convert_packages)


def test_tools_convert_script_documents_the_convert_group():
    script = (ROOT / "tools" / "convert_to_onnx.py").read_text(encoding="utf-8")
    assert "--group convert" in script
