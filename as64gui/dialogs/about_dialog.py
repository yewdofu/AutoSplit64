from PyQt5 import QtCore, QtGui, QtWidgets

from ..constants import VERSION, AUTHOR, ICON_PATH
from as64core import resource_utils


class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedSize(420, 280)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.SplashScreen)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("About AutoSplit64")

        # Icon (left)
        icon_lb = QtWidgets.QLabel(self)
        pixmap = QtGui.QPixmap(resource_utils.resource_path(ICON_PATH))
        icon_lb.setPixmap(pixmap.scaled(260, 260, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        icon_lb.move(0, 10)

        # Info panel (right) - dark rounded rectangle
        panel = QtWidgets.QFrame(self)
        panel.setStyleSheet("QFrame { background-color: rgba(20, 20, 20, 210); border-radius: 10px; }")
        panel.setGeometry(242, 190, 148, 60)

        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        label_style = "color: #c8cbcf; background: transparent; border: none;"
        ver_lb = QtWidgets.QLabel("Version:  " + VERSION)
        author_lb = QtWidgets.QLabel("Author:  " + AUTHOR)

        for lb in (ver_lb, author_lb):
            lb.setAlignment(QtCore.Qt.AlignCenter)
            lb.setStyleSheet(label_style)
            layout.addWidget(lb)

    def mousePressEvent(self, e):
        self.close()
