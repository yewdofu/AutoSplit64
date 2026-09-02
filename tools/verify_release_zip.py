"""Check a release zip before it is published.

An update is installed by the updater that shipped in the *previous* release,
so a packaging mistake here cannot be fixed by a later release - every
existing install is already pointed at the broken artifact. This is the last
gate before `gh release create`.

Verifies that the zip contains, at its top level:

  * the updater executable that as64core/updater.py launches by name, and
  * the application executable that the updater restarts after installing.

Usage:
    python tools/verify_release_zip.py AutoSplit64-0.4.1.zip
"""
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def launched_updater_name():
    """The updater name as64core/updater.py hands to WinExec."""
    text = (ROOT / "as64core" / "updater.py").read_text(encoding="utf-8")
    match = re.search(r"WinExec\(\s*r?['\"]([^'\"]+)['\"]", text)
    if not match:
        raise AssertionError("as64core/updater.py no longer launches the updater via WinExec('...')")
    return match.group(1)


def packaged_app_name():
    """The executable name PyInstaller produces, from the EXE() block in the spec."""
    text = (ROOT / "AutoSplit64.spec").read_text(encoding="utf-8")
    match = re.search(r"^\s*name=['\"]([^'\"]+)['\"]", text, re.MULTILINE)
    if not match:
        raise AssertionError("AutoSplit64.spec no longer sets a name= on its EXE()")
    return match.group(1) + ".exe"


def missing_entries(zip_path, required):
    """The required names absent from the top level of zip_path, compared case-insensitively."""
    with zipfile.ZipFile(zip_path) as archive:
        present = {name.lower() for name in archive.namelist()}
    return [name for name in required if name.lower() not in present]


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2

    zip_path = Path(argv[1])
    required = [launched_updater_name(), packaged_app_name()]
    missing = missing_entries(zip_path, required)

    for name in required:
        print("{} {}".format("MISSING" if name in missing else "ok     ", name))

    if missing:
        print("\n{} is missing {}".format(zip_path.name, ", ".join(missing)), file=sys.stderr)
        return 1

    print("\n{} is complete".format(zip_path.name))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
