import sys
from pathlib import Path

# Project root when running from source (parent of the as64core package).
_DEV_ROOT = Path(__file__).resolve().parent.parent


def _is_frozen():
    return hasattr(sys, "_MEIPASS")


def _resource_root():
    """Base directory bundled resources are shipped from."""
    return Path(sys._MEIPASS) if _is_frozen() else _DEV_ROOT


def _user_data_root():
    """Base directory writable user data lives in.

    Frozen: alongside the executable. From source: the project root, so
    development and a packaged build resolve to the same relative layout.
    """
    return Path(sys.executable).resolve().parent if _is_frozen() else _DEV_ROOT


def resource_path(relative_path):
    """
    Absolute path to a bundled, read-only resource (assets, templates,
    .processor files, defaults.json, etc). Resolves against PyInstaller's
    extraction directory when frozen, the project root otherwise.
    """
    return str(_resource_root() / relative_path).replace('\\', '/')


def user_data_path(relative_path=None):
    """
    Absolute path to writable user data (config.json, routes, generated
    capture profile templates, etc), stored next to the executable.
    """
    base = _user_data_root()
    if relative_path is None:
        return str(base).replace('\\', '/')
    return str(base / relative_path).replace('\\', '/')


def abs_to_rel(p):
    # Convert to relative path, if possible
    rel_path = p.replace(user_data_path(), "")

    # Store Path
    if rel_path != p:
        return rel_path[1:]
    else:
        return p


def rel_to_abs(p):
    if not Path(p).is_absolute():
        return user_data_path(p)
    else:
        return p
