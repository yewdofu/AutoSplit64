"""
Issue #13: AutoSplit64.py imported as64processes.* with `import *`, letting
helper symbols (e.g. resource_utils.resource_path) leak in implicitly
alongside the intended Process classes. Verifies the wildcard imports are
gone and the explicit replacements still resolve correctly.
"""
import ast
import types
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
    # Exercise everything up to (not including) the __main__ QApplication block.
    module_code = _source().split("if __name__")[0]
    module = types.ModuleType("autosplit64_entry_point_check")
    exec(compile(module_code, str(ENTRY_POINT), "exec"), module.__dict__)

    assert hasattr(module, "AutoSplit64"), "AutoSplit64 class should be defined after import"
    # resource_path is used directly in the __main__ block (font loading) and
    # must now come from an explicit import rather than a wildcard leak.
    assert "resource_path" in module.__dict__
