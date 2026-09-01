"""
Issue #13: AutoSplit64.py imported as64processes.* with `import *`, letting
helper symbols (e.g. resource_utils.resource_path) leak in implicitly
alongside the intended Process classes. Verifies the wildcard imports are
gone and the explicit replacements still resolve correctly.
"""
import ast
import subprocess
import sys
from pathlib import Path

ENTRY_POINT = Path(__file__).resolve().parent.parent / "AutoSplit64.py"


def _source():
    return ENTRY_POINT.read_text(encoding="utf-8")


def test_no_wildcard_imports_in_source():
    tree = ast.parse(_source())
    wildcard_imports = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and any(alias.name == "*" for alias in node.names)
    ]
    assert wildcard_imports == [], (
        f"found wildcard import(s) at line(s): {[n.lineno for n in wildcard_imports]}"
    )


def test_entry_point_imports_cleanly():
    # Exercise everything up to (not including) the __main__ QApplication
    # block, in a fresh subprocess. AutoSplit64.py must import onnxruntime
    # before PyQt5 (a Windows DLL-loading order requirement, per the comment
    # on that import) - running in-process risks another test having
    # already imported PyQt5 first and breaking that order.
    module_code = _source().split("if __name__")[0]
    result = subprocess.run(
        [sys.executable, "-c", module_code],
        cwd=ENTRY_POINT.parent, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_resource_path_is_explicitly_imported():
    # resource_path is used directly in the __main__ block (font loading) and
    # must now come from an explicit import rather than a wildcard leak.
    tree = ast.parse(_source())
    imported_names = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "resource_path" in imported_names
