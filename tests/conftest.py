# AutoSplit64.py imports onnxruntime before PyQt5 because of a Windows
# DLL-loading order requirement (loading Qt first makes onnxruntime's DLL
# load fail). The test process has to honour the same order, or any test
# that imports onnxruntime - directly or via the entry point - after Qt
# has been loaded will fail.
import onnxruntime  # noqa: F401  (must be imported before PyQt5)

import pytest
from PyQt5 import QtWidgets


@pytest.fixture(scope="session")
def qapp():
    """A single QApplication instance shared across tests that need to instantiate Qt widgets."""
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app
