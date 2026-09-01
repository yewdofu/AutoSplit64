from PyQt5 import QtWidgets
from PyQt5 import QtGui as QtGui
from PyQt5 import QtCore as QtCore

import cv2
import os
import shutil

from as64core import capture_window, config
from as64core import resource_utils
from as64core.game_capture import get_available_devices, open_video_device
from ..widgets import HLine
from ..graphics import RectangleSelector
from ..constants import (
    ICON_PATH
)

CAPTURE_SOURCE_WINDOW = "window"
CAPTURE_SOURCE_DEVICE = "device"
DEVICE_RESOLUTIONS = [(1920, 1080), (1280, 720), (720, 576), (720, 480), (640, 480), (320, 240)]


class _DeviceEnumerationWorker(QtCore.QThread):
    devices_found = QtCore.pyqtSignal(list)

    def run(self):
        self.devices_found.emit(get_available_devices())


class CaptureEditor(QtWidgets.QDialog):

    applied = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        QtWidgets.QDialog.__init__(self, parent, QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowCloseButtonHint)

        self._loading = True
        self._device_worker = None
        self._preview_size = None
        self._reset_region_on_next_frame = False
        self._draft = None
        self._pending_template_copies = []

        self.window_title = "Capture Setup"
        self.setWindowIcon(QtGui.QIcon(resource_utils.resource_path(ICON_PATH)))

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
        self.profile_lb = QtWidgets.QLabel("Profile:")
        self.profile_combo = QtWidgets.QComboBox()
        self.profile_new_btn = QtWidgets.QPushButton("New")
        self.profile_duplicate_btn = QtWidgets.QPushButton("Duplicate")
        self.profile_rename_btn = QtWidgets.QPushButton("Rename")
        self.profile_delete_btn = QtWidgets.QPushButton("Delete")

        self.source_lb = QtWidgets.QLabel("Source:")
        self.source_combo = QtWidgets.QComboBox()
        self.source_combo.addItems(["Window", "Video Device"])

        self.process_lb = QtWidgets.QLabel("Process:")
        self.process_combo = QtWidgets.QComboBox()

        self.device_lb = QtWidgets.QLabel("Device:")
        self.device_combo = QtWidgets.QComboBox()
        self.device_refresh_btn = QtWidgets.QPushButton("Refresh")
        self.resolution_lb = QtWidgets.QLabel("Resolution:")
        self.resolution_combo = QtWidgets.QComboBox()
        for width, height in DEVICE_RESOLUTIONS:
            self.resolution_combo.addItem(f"{width} x {height}", (width, height))

        self.capture_btn = QtWidgets.QPushButton("Capture")

        # Graphics View
        self.graphics_scene = CaptureGraphicsScene()
        self.graphics_view = QtWidgets.QGraphicsView(self.graphics_scene)

        # Graphics Scene Items
        self.game_region_selector = RectangleSelector(0, 0, 50, 50)

        self.preview_pixmap = QtGui.QPixmap()

        self.initialize()
        self._loading = False

    def initialize(self):
        self.setWindowTitle(self.window_title)
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.resize(1200, 700)

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
        self.profile_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.process_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.device_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.resolution_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.device_refresh_btn.setMaximumWidth(80)
        self.graphics_view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.graphics_view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self._refresh_process_list()

        profile_buttons = QtWidgets.QGridLayout()
        profile_buttons.setContentsMargins(0, 0, 0, 0)
        profile_buttons.addWidget(self.profile_new_btn, 0, 0)
        profile_buttons.addWidget(self.profile_duplicate_btn, 0, 1)
        profile_buttons.addWidget(self.profile_rename_btn, 1, 0)
        profile_buttons.addWidget(self.profile_delete_btn, 1, 1)

        self.left_layout.addWidget(self.profile_lb, 0, 0)
        self.left_layout.addWidget(self.profile_combo, 0, 1, 1, 2)
        self.left_layout.addLayout(profile_buttons, 1, 0, 1, 3)
        self.left_layout.addWidget(HLine(), 2, 0, 1, 3)
        self.left_layout.addWidget(self.source_lb, 3, 0)
        self.left_layout.addWidget(self.source_combo, 3, 1, 1, 2)
        self.left_layout.addWidget(self.process_lb, 4, 0)
        self.left_layout.addWidget(self.process_combo, 4, 1, 1, 2)
        self.left_layout.addWidget(self.device_lb, 5, 0)
        self.left_layout.addWidget(self.device_combo, 5, 1)
        self.left_layout.addWidget(self.device_refresh_btn, 5, 2)
        self.left_layout.addWidget(self.resolution_lb, 6, 0)
        self.left_layout.addWidget(self.resolution_combo, 6, 1, 1, 2)
        self.left_layout.addWidget(self.capture_btn, 7, 0, 1, 3)
        self.left_layout.addItem(QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding), 8, 0)

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
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        self.profile_new_btn.clicked.connect(self._create_profile)
        self.profile_duplicate_btn.clicked.connect(self._duplicate_profile)
        self.profile_rename_btn.clicked.connect(self._rename_profile)
        self.profile_delete_btn.clicked.connect(self._delete_profile)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.capture_btn.clicked.connect(self.refresh_graphics_scene)
        self.apply_btn.clicked.connect(self.apply_clicked)
        self.cancel_btn.clicked.connect(self.cancel_clicked)
        self.game_region_panel.updated.connect(self.on_game_region_panel_update)
        self.process_combo.currentIndexChanged.connect(self._on_process_changed)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        self.resolution_combo.currentIndexChanged.connect(self._on_resolution_changed)
        self.device_refresh_btn.clicked.connect(self._refresh_device_list)

        self.refresh_graphics_scene()

    def _is_device_mode(self):
        return self.source_combo.currentIndex() == 1

    def _populate_profiles(self, selected_profile_id=None):
        profile_id = selected_profile_id or config.get_active_capture_profile_id(self._draft)
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for item_id, name in config.get_capture_profiles(self._draft):
            self.profile_combo.addItem(name, item_id)
        index = self.profile_combo.findData(profile_id)
        self.profile_combo.setCurrentIndex(max(index, 0))
        self.profile_combo.blockSignals(False)
        self.profile_delete_btn.setEnabled(self.profile_combo.count() > 1)

    def _profile_name_input(self, title, initial_name=""):
        name, accepted = QtWidgets.QInputDialog.getText(self, title, "Profile name:", text=initial_name)
        return name.strip() if accepted else None

    def _show_profile_error(self, error):
        QtWidgets.QMessageBox.warning(self, "Capture Profile", str(error))

    def _create_profile(self):
        name = self._profile_name_input("New Capture Profile")
        if name is None:
            return
        try:
            self._store_active_profile()
            reset_templates = self._active_reset_templates()
            profile_id = config.create_capture_profile(
                name, config.get_active_capture_profile_id(self._draft), self._draft
            )
            self._populate_profiles(profile_id)
            self._activate_selected_profile()
            self._copy_reset_templates(profile_id, reset_templates)
        except (KeyError, ValueError) as error:
            self._show_profile_error(error)

    def _duplicate_profile(self):
        current_name = self.profile_combo.currentText()
        name = self._profile_name_input("Duplicate Capture Profile", current_name + " Copy")
        if name is None:
            return
        try:
            self._store_active_profile()
            reset_templates = self._active_reset_templates()
            profile_id = config.create_capture_profile(
                name, config.get_active_capture_profile_id(self._draft), self._draft
            )
            self._populate_profiles(profile_id)
            self._activate_selected_profile()
            self._copy_reset_templates(profile_id, reset_templates)
        except (KeyError, ValueError) as error:
            self._show_profile_error(error)

    def _rename_profile(self):
        profile_id = self.profile_combo.currentData()
        name = self._profile_name_input("Rename Capture Profile", self.profile_combo.currentText())
        if name is None:
            return
        try:
            config.rename_capture_profile(profile_id, name, self._draft)
            self._populate_profiles(profile_id)
        except (KeyError, ValueError) as error:
            self._show_profile_error(error)

    def _active_reset_templates(self):
        return (
            config.get("advanced", "reset_frame_one", self._draft),
            config.get("advanced", "reset_frame_two", self._draft)
        )

    def _copy_reset_templates(self, profile_id, source_paths):
        keys = ("reset_frame_one", "reset_frame_two")
        names = ("reset_one.jpg", "reset_two.jpg")
        destination_dir = resource_utils.base_path(os.path.join("templates", "profiles", profile_id))

        for key, name, source_path in zip(keys, names, source_paths):
            if source_path == config.get_default("advanced", key):
                continue
            for _, pending_source, pending_destination in reversed(self._pending_template_copies):
                if source_path == pending_destination:
                    source_path = pending_source
            resolved_source = source_path if os.path.isabs(source_path) else resource_utils.resource_path(source_path)
            if not os.path.isfile(resolved_source):
                continue
            destination = os.path.join(destination_dir, name).replace("\\", "/")
            self._pending_template_copies.append((profile_id, resolved_source, destination))
            config.set_key("advanced", key, destination, self._draft)

    def _apply_pending_template_copies(self):
        profile_ids = {profile_id for profile_id, _ in config.get_capture_profiles(self._draft)}
        for profile_id, source, destination in self._pending_template_copies:
            if profile_id not in profile_ids:
                continue
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copyfile(source, destination)

    def _delete_profile(self):
        profile_id = self.profile_combo.currentData()
        name = self.profile_combo.currentText()
        answer = QtWidgets.QMessageBox.question(
            self,
            "Delete Capture Profile",
            f'Delete the capture profile "{name}"? Generated reset templates will be kept.',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return
        try:
            active_id = config.delete_capture_profile(profile_id, self._draft)
            self._populate_profiles(active_id)
            self._load_active_profile()
        except (KeyError, ValueError) as error:
            self._show_profile_error(error)

    def _on_profile_changed(self, index):
        if self._loading or index < 0:
            return
        self._store_active_profile()
        self._activate_selected_profile()

    def _activate_selected_profile(self):
        profile_id = self.profile_combo.currentData()
        if profile_id is None:
            return
        config.set_active_capture_profile(profile_id, self._draft)
        self._load_active_profile()

    def _widget_state(self):
        """
        Collect the current widget values into a plain dict, with no config
        access - this is the only place UI values are read, and it can be
        exercised without a config object or a running QApplication event
        loop by constructing/mutating a stand-in object with the same
        attributes.
        """
        state = {
            "capture_source": CAPTURE_SOURCE_DEVICE if self._is_device_mode() else CAPTURE_SOURCE_WINDOW,
        }
        try:
            state["game_region"] = self.game_region_panel.get_data()
        except (TypeError, ValueError):
            pass
        if self._preview_size:
            state["capture_size"] = list(self._preview_size)

        if self._is_device_mode():
            device_index = self.device_combo.currentData()
            if device_index is not None:
                state["device_index"] = device_index
                state["device_name"] = self.device_combo.currentText()
            resolution = self.resolution_combo.currentData()
            if resolution:
                state["device_resolution"] = list(resolution)
        elif self.process_combo.currentIndex() >= 0:
            state["process_name"] = self.process_combo.currentText()

        return state

    def _store_active_profile(self):
        for key, value in self._widget_state().items():
            config.set_key("game", key, value, self._draft)

    def _load_active_profile(self):
        self._loading = True
        game_region = config.get("game", "game_region", self._draft)
        self._set_game_region(*game_region)
        self._preview_size = tuple(config.get("game", "capture_size", self._draft))

        resolution = tuple(config.get("game", "device_resolution", self._draft))
        resolution_index = self.resolution_combo.findData(resolution)
        if resolution_index >= 0:
            self.resolution_combo.setCurrentIndex(resolution_index)

        process_name = config.get("game", "process_name", self._draft)
        self._refresh_process_list(process_name)

        source = config.get("game", "capture_source", self._draft)
        self.source_combo.setCurrentIndex(0 if source == CAPTURE_SOURCE_WINDOW else 1)
        self._on_source_changed(self.source_combo.currentIndex())

        if source == CAPTURE_SOURCE_WINDOW:
            process_index = self.process_combo.findText(process_name)
            if process_index >= 0:
                self.process_combo.setCurrentIndex(process_index)
        else:
            self.device_combo.clear()
            self._refresh_device_list()

        self._loading = False
        self.refresh_graphics_scene()

    def _on_source_changed(self, index):
        is_device = (index == 1)
        self.process_lb.setVisible(not is_device)
        self.process_combo.setVisible(not is_device)
        self.device_lb.setVisible(is_device)
        self.device_combo.setVisible(is_device)
        self.device_refresh_btn.setVisible(is_device)
        self.resolution_lb.setVisible(is_device)
        self.resolution_combo.setVisible(is_device)
        if is_device and not self._loading:
            self._refresh_device_list()
        if not self._loading:
            self.refresh_graphics_scene(reset_region=True)

    def _on_device_changed(self, index):
        if not self._loading and index >= 0:
            self.refresh_graphics_scene(reset_region=True)

    def _on_process_changed(self, index):
        if not self._loading and index >= 0:
            self.refresh_graphics_scene(reset_region=True)

    def _on_resolution_changed(self, index):
        if not self._loading and index >= 0:
            self.refresh_graphics_scene(reset_region=True)

    def _refresh_process_list(self, saved_process_name=None):
        self.process_combo.clear()
        self._process_list = capture_window.get_visible_processes()
        for process, hwnd in self._process_list:
            self.process_combo.addItem(process.name(), hwnd)
        if saved_process_name and self.process_combo.findText(saved_process_name) < 0:
            self.process_combo.addItem(saved_process_name, 0)
        if saved_process_name:
            self.process_combo.setCurrentIndex(self.process_combo.findText(saved_process_name))

    def _refresh_device_list(self):
        if self._device_worker is not None and self._device_worker.isRunning():
            return
        self.device_refresh_btn.setEnabled(False)
        self.device_refresh_btn.setText("Searching...")
        self.device_combo.clear()
        self._device_worker = _DeviceEnumerationWorker(self)
        self._device_worker.devices_found.connect(self._on_devices_found)
        self._device_worker.start()

    def _on_devices_found(self, devices):
        saved_index = config.get("game", "device_index", self._draft)
        saved_name = config.get("game", "device_name", self._draft)
        self._device_list = devices
        self.device_combo.blockSignals(True)
        for i, name in devices:
            self.device_combo.addItem(name, i)
        idx = self.device_combo.findText(saved_name) if saved_name else -1
        if idx < 0:
            idx = self.device_combo.findData(saved_index)
        if idx < 0:
            unavailable_name = saved_name or f"Device {saved_index}"
            self.device_combo.addItem(unavailable_name, saved_index)
            idx = self.device_combo.count() - 1
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)
        self.device_combo.blockSignals(False)
        self.device_refresh_btn.setEnabled(True)
        self.device_refresh_btn.setText("Refresh")
        if self._is_device_mode():
            self.refresh_graphics_scene()

    def show(self):
        self._draft = config.copy_config()
        self._pending_template_copies = []
        self._populate_profiles()
        self._load_active_profile()
        super().show()

    def _measure_capture_size(self):
        """
        Actually open the selected capture source to read its real frame
        size. Used only at Apply time - the profile's normal capture_size
        (used everywhere else) tracks the last previewed frame instead.
        """
        if self._is_device_mode():
            device_data = self.device_combo.currentData()
            if device_data is None:
                return None
            cap = None
            try:
                cap = open_video_device(device_data, self.resolution_combo.currentData())
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        h, w = frame.shape[:2]
                    else:
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    return [w, h]
            except Exception:
                pass
            finally:
                if cap is not None:
                    cap.release()
            return None
        else:
            try:
                return capture_window.get_capture_size(self.process_combo.currentData())
            except Exception:
                return None

    def apply_clicked(self):
        if not self._is_minimum_size():
            if self.display_warning("The selected region is below the game's native resolution (320, 240). You may experience sub-optimal performance."):
                return

        self._store_active_profile()

        measured_size = self._measure_capture_size()
        if measured_size is not None:
            config.set_key("game", "capture_size", measured_size, self._draft)

        try:
            self._apply_pending_template_copies()
        except OSError as error:
            self._show_profile_error(error)
            return

        config.replace_config(self._draft)
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

    def refresh_graphics_scene(self, reset_region=False):
        if reset_region:
            self._reset_region_on_next_frame = True

        if self.game_region_selector.scene() is self.graphics_scene:
            self.graphics_scene.removeItem(self.game_region_selector)
        self.graphics_scene.clear()
        self.graphics_view.update()

        if self._is_device_mode():
            frame = self._capture_device_frame()
        else:
            frame = self._capture_window_frame()

        if frame is None:
            self.preview_pixmap = QtGui.QPixmap()
            self.graphics_scene.setSceneRect(QtCore.QRectF())
            return

        height, width = frame.shape[:2]
        if self._preview_size != (width, height):
            self._reset_region_on_next_frame = True
        self._preview_size = (width, height)

        if self._reset_region_on_next_frame:
            self._set_game_region(0, 0, width, height)
            self._reset_region_on_next_frame = False

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        bytes_per_line = rgb_frame.strides[0]
        image = QtGui.QImage(rgb_frame.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888).copy()
        self.preview_pixmap = QtGui.QPixmap.fromImage(image)
        self.graphics_scene.addPixmap(self.preview_pixmap)
        self.graphics_scene.addItem(self.game_region_selector)
        self.graphics_scene.setSceneRect(QtCore.QRectF(self.preview_pixmap.rect()))
        self.graphics_view.fitInView(self.graphics_scene.sceneRect(), QtCore.Qt.KeepAspectRatio)

    def _set_game_region(self, x, y, width, height):
        self.game_region_selector.resize(width, height)
        self.game_region_selector.setPos(x, y)
        self.game_region_panel.update_text(str(x), str(y), str(width), str(height))

    def _capture_window_frame(self):
        selected_hwnd = self.process_combo.currentData() or 0

        if selected_hwnd:
            try:
                return capture_window.capture(selected_hwnd)
            except Exception:
                pass
        return None

    def _capture_device_frame(self):
        device_data = self.device_combo.currentData()
        if device_data is None:
            return None
        cap = None
        try:
            cap = open_video_device(device_data, self.resolution_combo.currentData())
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    return frame
        except Exception:
            pass
        finally:
            if cap is not None:
                cap.release()
        return None

    def _is_minimum_size(self):
        region_data = self.game_region_panel.get_data()
        return region_data[2] >= 320 and region_data[3] >= 240

    def closeEvent(self, e):
        self._draft = None
        self._pending_template_copies = []
        super().closeEvent(e)

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
        if x_offset is not None:
            self.xoffset_le.setText(x_offset)
        if y_offset is not None:
            self.yoffset_le.setText(y_offset)
        if width is not None:
            self.width_le.setText(width)
        if height is not None:
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
