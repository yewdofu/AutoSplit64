from PyQt5 import QtWidgets
from PyQt5 import QtGui as QtGui
from PyQt5 import QtCore as QtCore

import cv2

from as64core import capture_window, config
from as64core import resource_utils
from as64core.game_capture import get_available_devices
from ..widgets import HLine
from ..graphics import RectangleSelector
from ..constants import (
    ICON_PATH
)

CAPTURE_SOURCE_WINDOW = "window"
CAPTURE_SOURCE_DEVICE = "device"


class CaptureEditor(QtWidgets.QDialog):

    applied = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        QtWidgets.QDialog.__init__(self, parent, QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowCloseButtonHint)

        self.window_title = "Game Capture Editor"
        self.setWindowIcon(QtGui.QIcon(resource_utils.resource_path(ICON_PATH)))

        self.preview_image_path = r'resources/game_preview.png'
        self.preview_not_found_image_path = r'resources/game_preview_not_found.png'

        # Layouts
        self.main_layout = QtWidgets.QHBoxLayout()
        self.left_layout = QtWidgets.QGridLayout()
        self.right_layout = QtWidgets.QGridLayout()

        # Primary Widgets
        self.left_widget = QtWidgets.QWidget(self)
        self.right_widget = QtWidgets.QWidget(self)

        # Right Panel Widgets
        self.game_region_panel = RectangleCapturePanel("Game Region")
        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")

        # Left Panel Widgets
        self.source_lb = QtWidgets.QLabel("Source:")
        self.source_combo = QtWidgets.QComboBox()
        self.source_combo.addItems(["Window", "Video Device"])

        self.process_lb = QtWidgets.QLabel("Process:")
        self.process_combo = QtWidgets.QComboBox()

        self.device_lb = QtWidgets.QLabel("Device:")
        self.device_combo = QtWidgets.QComboBox()
        self.device_refresh_btn = QtWidgets.QPushButton("Refresh")

        self.capture_btn = QtWidgets.QPushButton("Capture")

        # Graphics View
        self.graphics_scene = CaptureGraphicsScene()
        self.graphics_view = QtWidgets.QGraphicsView(self.graphics_scene)

        # Graphics Scene Items
        self.game_region_selector = RectangleSelector(0, 0, 50, 50)

        self.preview_pixmap = QtGui.QPixmap()

        self.initialize()

    def initialize(self):
        self.setWindowTitle(self.window_title)

        self.setLayout(self.main_layout)
        self.left_widget.setLayout(self.left_layout)
        self.right_widget.setLayout(self.right_layout)

        self.right_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.left_widget.setFixedWidth(220)
        self.right_widget.setFixedWidth(220)

        self.main_layout.addWidget(self.left_widget)
        self.main_layout.addWidget(self.graphics_view)
        self.main_layout.addWidget(self.right_widget)

        # Left Widget
        self.capture_btn.setDefault(False)
        self.capture_btn.setAutoDefault(False)
        self.source_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.process_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.device_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.device_refresh_btn.setMaximumWidth(60)

        self._refresh_process_list()

        self.left_layout.addWidget(self.source_lb, 0, 0)
        self.left_layout.addWidget(self.source_combo, 0, 1, 1, 2)
        self.left_layout.addWidget(self.process_lb, 1, 0)
        self.left_layout.addWidget(self.process_combo, 1, 1, 1, 2)
        self.left_layout.addWidget(self.device_lb, 2, 0)
        self.left_layout.addWidget(self.device_combo, 2, 1)
        self.left_layout.addWidget(self.device_refresh_btn, 2, 2)
        self.left_layout.addWidget(self.capture_btn, 3, 0, 1, 3)
        self.left_layout.addItem(QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding), 4, 0)

        # Right Widget
        self.apply_btn.setDefault(False)
        self.apply_btn.setAutoDefault(False)
        self.cancel_btn.setDefault(False)
        self.cancel_btn.setAutoDefault(False)

        self.right_layout.addWidget(self.game_region_panel, 5, 0, 1, 2)
        self.right_layout.addItem(QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding), 9, 0)
        self.right_layout.addWidget(HLine(), 10, 0, 1, 2)
        self.right_layout.addWidget(self.apply_btn, 15, 0)
        self.right_layout.addWidget(self.cancel_btn, 15, 1)

        self.refresh_graphics_scene()

        # Connections
        self.graphics_scene.item_update.connect(self.on_graphics_item_update)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.capture_btn.clicked.connect(self.refresh_graphics_scene)
        self.apply_btn.clicked.connect(self.apply_clicked)
        self.cancel_btn.clicked.connect(self.cancel_clicked)
        self.game_region_panel.updated.connect(self.on_game_region_panel_update)
        self.process_combo.currentIndexChanged.connect(self.refresh_graphics_scene)
        self.device_refresh_btn.clicked.connect(self._refresh_device_list)

        self.refresh_graphics_scene()

    def _is_device_mode(self):
        return self.source_combo.currentIndex() == 1

    def _on_source_changed(self, index):
        is_device = (index == 1)
        self.process_lb.setVisible(not is_device)
        self.process_combo.setVisible(not is_device)
        self.device_lb.setVisible(is_device)
        self.device_combo.setVisible(is_device)
        self.device_refresh_btn.setVisible(is_device)
        self.refresh_graphics_scene()

    def _refresh_process_list(self):
        self.process_combo.clear()
        self._process_list = capture_window.get_visible_processes()
        self.process_combo.addItems([proc[0].name() for proc in self._process_list])

    def _refresh_device_list(self):
        saved_index = config.get("game", "device_index")
        self.device_combo.clear()
        self._device_list = get_available_devices()
        for i, name in self._device_list:
            self.device_combo.addItem(name, i)
        idx = self.device_combo.findData(saved_index)
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)

    def show(self):
        game_region = config.get('game', 'game_region')
        self.game_region_selector.resize(game_region[2], game_region[3])
        self.game_region_selector.setPos(game_region[0], game_region[1])
        self.game_region_panel.update_text(*[str(v) for v in game_region])

        # Set source from config
        source = config.get("game", "capture_source")
        self.source_combo.setCurrentIndex(0 if source == CAPTURE_SOURCE_WINDOW else 1)
        self._on_source_changed(self.source_combo.currentIndex())

        if source == CAPTURE_SOURCE_WINDOW:
            self._refresh_process_list()
            p_name = config.get("game", "process_name")
            for i in range(len(self._process_list)):
                if self._process_list[i][0].name() == p_name:
                    self.process_combo.setCurrentIndex(i)
        else:
            self._refresh_device_list()

        self.refresh_graphics_scene()
        config.create_rollback()
        super().show()

    def apply_clicked(self):
        if not self._is_correct_ratio():
            self.display_info("The selected region is not 4:3. It will be automatically corrected at runtime.")

        if not self._is_minimum_size():
            if self.display_warning("Game width and height are below the recommended minimum (614, 448). You may experience sub-optimal performance."):
                return

        config.set_key("game", "game_region", self.game_region_panel.get_data())

        if self._is_device_mode():
            device_data = self.device_combo.currentData()
            if device_data is not None:
                config.set_key("game", "device_index", device_data)
                config.set_key("game", "capture_source", CAPTURE_SOURCE_DEVICE)
                cap = cv2.VideoCapture(device_data, cv2.CAP_DSHOW)
                if cap.isOpened():
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    config.set_key("game", "capture_size", [w, h])
                    cap.release()
        else:
            config.set_key("game", "process_name", self.process_combo.currentText())
            config.set_key("game", "capture_source", CAPTURE_SOURCE_WINDOW)
            try:
                config.set_key("game", "capture_size", capture_window.get_capture_size(self._process_list[self.process_combo.currentIndex()][1]))
            except Exception:
                pass

        config.save_config()
        self.applied.emit()
        self.close()

    def cancel_clicked(self):
        self.close()

    def on_graphics_item_update(self, e):
        if e.object_name == self.game_region_selector.object_name:
            rect = e.get_view_space_rect()
            self.game_region_panel.update_text(*[str(v) for v in rect])

    def on_game_region_panel_update(self, e):
        self.game_region_selector.resize(e[2], e[3])
        self.game_region_selector.setPos(e[0], e[1])

    def refresh_graphics_scene(self):
        self.graphics_scene.removeItem(self.game_region_selector)
        self.graphics_scene.clear()
        self.graphics_view.update()

        if self._is_device_mode():
            self._capture_device_frame()
        else:
            self._capture_window_frame()

        self.preview_pixmap.load(resource_utils.resource_path(self.preview_image_path))
        self.graphics_scene.addPixmap(self.preview_pixmap)
        self.graphics_scene.addItem(self.game_region_selector)

    def _capture_window_frame(self):
        selected_hwnd = 0
        try:
            selected_hwnd = self._process_list[self.process_combo.currentIndex()][1]
        except (IndexError, AttributeError):
            pass

        if selected_hwnd:
            try:
                preview_image = capture_window.capture(selected_hwnd)
                cv2.imwrite(resource_utils.resource_path(self.preview_image_path), preview_image)
            except Exception:
                pass

    def _capture_device_frame(self):
        device_data = self.device_combo.currentData()
        if device_data is None:
            return
        try:
            cap = cv2.VideoCapture(device_data, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    cv2.imwrite(resource_utils.resource_path(self.preview_image_path), frame)
                cap.release()
        except Exception:
            pass

    def _is_correct_ratio(self):
        ideal_ratio = 4 / 3
        threshold = 0.093
        region_data = self.game_region_panel.get_data()
        return ideal_ratio - threshold <= region_data[2] / region_data[3] <= ideal_ratio + threshold

    def _is_minimum_size(self):
        region_data = self.game_region_panel.get_data()
        return region_data[2] >= 612 and region_data[3] >= 448

    def closeEvent(self, e):
        config.rollback()
        super().closeEvent(e)

    def display_info(self, message, title="Info"):
        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.exec_()

    def display_warning(self, message, title="Warning"):
        ignore_btn = QtWidgets.QPushButton(r'Ignore Warning and Apply')
        back_btn = QtWidgets.QPushButton("Continue Editing")
        ignore_btn.setFixedSize(150, 30)
        back_btn.setFixedSize(150, 30)

        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.addButton(ignore_btn, QtWidgets.QMessageBox.NoRole)
        msg.addButton(back_btn, QtWidgets.QMessageBox.YesRole)

        return msg.exec_()


class RectangleCapturePanel(QtWidgets.QWidget):
    updated = QtCore.pyqtSignal(list)

    def __init__(self, title, parent=None):
        super().__init__(parent)

        self.main_layout = QtWidgets.QGridLayout(self)

        self.title_lb = QtWidgets.QLabel(title)
        self.xoffset_lb = QtWidgets.QLabel("X Offset:")
        self.yoffset_lb = QtWidgets.QLabel("Y Offset:")
        self.width_lb = QtWidgets.QLabel("Width:")
        self.height_lb = QtWidgets.QLabel("Height:")
        self.xoffset_le = QtWidgets.QLineEdit()
        self.yoffset_le = QtWidgets.QLineEdit()
        self.width_le = QtWidgets.QLineEdit()
        self.height_le = QtWidgets.QLineEdit()

        self.int_validator = QtGui.QIntValidator()

        self.initialize()

    def initialize(self):
        self.setLayout(self.main_layout)

        self.xoffset_lb.setFixedWidth(70)
        self.yoffset_lb.setFixedWidth(70)
        self.width_lb.setFixedWidth(70)
        self.height_lb.setFixedWidth(70)

        self.xoffset_lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.yoffset_lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.width_lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.height_lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.xoffset_le.setMinimumWidth(80)
        self.yoffset_le.setMinimumWidth(80)
        self.width_le.setMinimumWidth(80)
        self.height_le.setMinimumWidth(80)

        self.xoffset_le.setValidator(self.int_validator)
        self.yoffset_le.setValidator(self.int_validator)
        self.width_le.setValidator(self.int_validator)
        self.height_le.setValidator(self.int_validator)

        line = HLine()

        self.main_layout.addWidget(self.title_lb, 0, 0, 1, 2)
        self.main_layout.addWidget(line, 1, 0, 1, 2)
        self.main_layout.addWidget(self.xoffset_lb, 2, 0)
        self.main_layout.addWidget(self.yoffset_lb, 3, 0)
        self.main_layout.addWidget(self.width_lb, 4, 0)
        self.main_layout.addWidget(self.height_lb, 5, 0)
        self.main_layout.addWidget(self.xoffset_le, 2, 1)
        self.main_layout.addWidget(self.yoffset_le, 3, 1)
        self.main_layout.addWidget(self.width_le, 4, 1)
        self.main_layout.addWidget(self.height_le, 5, 1)

        self.xoffset_le.editingFinished.connect(self.text_changed)
        self.yoffset_le.editingFinished.connect(self.text_changed)
        self.width_le.editingFinished.connect(self.text_changed)
        self.height_le.editingFinished.connect(self.text_changed)

    def update_text(self, x_offset=None, y_offset=None, width=None, height=None):
        if x_offset:
            self.xoffset_le.setText(x_offset)
        if y_offset:
            self.yoffset_le.setText(y_offset)
        if width:
            self.width_le.setText(width)
        if height:
            self.height_le.setText(height)

    def text_changed(self):
        try:
            self.updated.emit(self.get_data())
        except Exception:
            pass

    def get_data(self):
        return [int(float(self.xoffset_le.text())), int(float(self.yoffset_le.text())),
                int(float(self.width_le.text())), int(float(self.height_le.text()))]


class CaptureGraphicsScene(QtWidgets.QGraphicsScene):
    item_update = QtCore.pyqtSignal(object)
