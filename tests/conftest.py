import pytest
from PyQt5 import QtWidgets


@pytest.fixture(scope="session")
def qapp():
    """A single QApplication instance shared across tests that need to instantiate Qt widgets."""
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app
