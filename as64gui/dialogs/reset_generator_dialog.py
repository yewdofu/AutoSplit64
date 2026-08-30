import time
import os
import shutil

from PyQt5 import QtCore, QtGui, QtWidgets
import cv2

from ..constants import (
    ICON_PATH
)
from as64core import resource_utils

from as64core.game_capture import GameCapture, DeviceCapture
from as64core.image_utils import is_black
from as64core import (
    GAME_JP,
    RESET_REGION,
    FADEOUT_REGION,
    config
)


class ResetGeneratorHelpDialog(QtWidgets.QDialog):
    line1 = """AutoSplit64's reset feature works based on matching the second and third frame of the Super Mario 64 logo that appears when launching the game."""
    line2 = """If the colours or capture size of your particular game feed differ from the default standard it may be required to generate custom templates from your game capture."""
    line3 = """While in-game, press generate, then RESET your console. Ensure the generated images look similar to the examples. """

    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowCloseButtonHint)
        self.window_title = "Reset Template Generator Help"
        self.setWindowIcon(QtGui.QIcon(resource_utils.resource_path(ICON_PATH)))

        # Layouts
        self.menu_layout = QtWidgets.QVBoxLayout()
        self.button_layout = QtWidgets.QHBoxLayout()

        # Widgets
        self.text_edit = QtWidgets.QTextEdit()
        self.text_edit.append(self.line1)
        self.text_edit.append("\n")
        self.text_edit.append(self.line2)
        self.text_edit.append("\n")
        self.text_edit.append(self.line3)

        self.ok_btn = QtWidgets.QPushButton("OK")

        # Font
        self.title_font = QtGui.QFont()
        self.title_font.setPointSize(16)

        self.initialize_window()

    def initialize_window(self):
        self.setWindowTitle(self.window_title)
        self.resize(400, 225)

        # Create Layout
        self.setLayout(self.menu_layout)

        # Configure Widgets
        self.text_edit.setEnabled(False)

        # Child Layouts
        self.button_layout.addItem(QtWidgets.QSpacerItem(10, 10, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
        self.button_layout.addWidget(self.ok_btn)

        # Configure Layout
        self.menu_layout.addWidget(self.text_edit)
        self.menu_layout.addLayout(self.button_layout)

        self.ok_btn.clicked.connect(self.hide)


class ResetGeneratorDialog(QtWidgets.QDialog):
    TEMPLATE_DIR = "templates/"
    applied = QtCore.pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowCloseButtonHint)
        self.window_title = "Reset Template Generator"
        self.setWindowIcon(QtGui.QIcon(resource_utils.resource_path(ICON_PATH)))

        # Layouts
        self.menu_layout = QtWidgets.QGridLayout()
        self.button_layout = QtWidgets.QHBoxLayout()

        # Widgets
        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.generate_btn = QtWidgets.QPushButton("Generate")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.help_btn = QtWidgets.QPushButton("Help")

        self.gen_1_px = QtWidgets.QLabel()
        self.gen_2_px = QtWidgets.QLabel()
        self.def_1_px = QtWidgets.QLabel()
        self.def_2_px = QtWidgets.QLabel()

        self.gen_1_sb = QtWidgets.QSpinBox()
        self.gen_2_sb = QtWidgets.QSpinBox()

        self._reset_generator = None
        self._profile_template_dir = None
        self._profile_id = None
        self._pending_cleanup_dirs = set()
        self._reopen_after_stop = False

        self.help_dialog = ResetGeneratorHelpDialog(self)

        self.initialize_window()

    def initialize_window(self):
        self.setWindowTitle(self.window_title)
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.resize(400, 200)

        # Create Layout
        self.setLayout(self.menu_layout)

        # Configure Widgets
        self.gen_1_px.setFixedSize(251, 137)
        self.gen_2_px.setFixedSize(251, 137)
        self.def_1_px.setFixedSize(251, 137)
        self.def_2_px.setFixedSize(251, 137)

        self.def_1_px.setPixmap(QtGui.QPixmap(resource_utils.resource_path(ResetGeneratorDialog.TEMPLATE_DIR + "default_reset_one.jpg")))
        self.def_2_px.setPixmap(QtGui.QPixmap(resource_utils.resource_path(ResetGeneratorDialog.TEMPLATE_DIR + "default_reset_two.jpg")))

        self.button_layout.addItem(
            QtWidgets.QSpacerItem(10, 10, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
        self.button_layout.addWidget(self.help_btn)
        self.button_layout.addWidget(self.cancel_btn)
        self.button_layout.addWidget(self.generate_btn)
        self.button_layout.addWidget(self.apply_btn)

        gen_1_lb = QtWidgets.QLabel("Generated Frame Two:")
        gen_2_lb = QtWidgets.QLabel("Generated Frame Three:")
        self.gen_1_sb.setMaximumWidth(40)
        self.gen_2_sb.setMaximumWidth(40)
        self.gen_1_sb.setRange(1, ResetGenerator.CAPTURE_COUNT)
        self.gen_2_sb.setRange(1, ResetGenerator.CAPTURE_COUNT)
        self.gen_1_sb.setValue(2)
        self.gen_2_sb.setValue(3)

        gen_1_top_layout = QtWidgets.QHBoxLayout()
        gen_1_top_layout.addWidget(self.gen_1_sb)
        gen_1_top_layout.addWidget(gen_1_lb)

        gen_2_top_layout = QtWidgets.QHBoxLayout()
        gen_2_top_layout.addWidget(self.gen_2_sb)
        gen_2_top_layout.addWidget(gen_2_lb)

        def_1_lb = QtWidgets.QLabel("Desired Frame Two:")
        def_2_lb = QtWidgets.QLabel("Desired Frame Three:")

        # Configure Layout
        self.menu_layout.addLayout(gen_1_top_layout, 1, 0)
        self.menu_layout.addLayout(gen_2_top_layout, 1, 1)
        self.menu_layout.addWidget(self.gen_1_px, 2, 0)
        self.menu_layout.addWidget(self.gen_2_px, 2, 1)
        self.menu_layout.addWidget(def_1_lb, 3, 0)
        self.menu_layout.addWidget(def_2_lb, 3, 1)
        self.menu_layout.addWidget(self.def_1_px, 4, 0)
        self.menu_layout.addWidget(self.def_2_px, 4, 1)
        self.menu_layout.addLayout(self.button_layout, 5, 0, 1, 2)

        self.generate_btn.clicked.connect(self.generate_clicked)
        self.apply_btn.clicked.connect(self.apply_clicked)
        self.cancel_btn.clicked.connect(self.cancel_clicked)
        self.help_btn.clicked.connect(self.help_dialog.show)
        self.gen_1_sb.valueChanged.connect(self.gen_1_changed)
        self.gen_2_sb.valueChanged.connect(self.gen_2_changed)

    def show(self):
        if self._reset_generator is not None and self._reset_generator.isRunning():
            self._reopen_after_stop = True
            self._stop_generator()
            self.generate_btn.setText("Stopping...")
            self.generate_btn.setEnabled(False)
            self.apply_btn.setEnabled(False)
            super().show()
            return

        self._prepare_dialog()
        super().show()

    def _prepare_dialog(self):
        self._profile_id = config.get_active_capture_profile_id()
        self._profile_template_dir = resource_utils.base_path(
            os.path.join(self.TEMPLATE_DIR, "profiles", self._profile_id)
        )
        self._reset_generator = None

        self.gen_1_px.clear()
        self.gen_2_px.clear()
        self.generate_btn.setText("Generate")
        self.generate_btn.setEnabled(True)
        self.apply_btn.setEnabled(False)
        self.gen_1_sb.setEnabled(False)
        self.gen_2_sb.setEnabled(False)

    def hide(self):
        self._reopen_after_stop = False
        self._stop_generator(cleanup=True)
        super().hide()

    def _stop_generator(self, cleanup=False):
        if cleanup and self._profile_template_dir:
            self._pending_cleanup_dirs.add(self._profile_template_dir)
        if self._reset_generator is not None:
            worker = self._reset_generator
            worker.stop()
            if not worker.isRunning():
                self._on_generator_finished(worker)
                return
        self._cleanup_finished_templates()

    def _create_generator(self):
        worker = ResetGenerator(self._profile_template_dir)
        self._reset_generator = worker
        worker.generated.connect(self.on_generate)
        worker.error.connect(self.on_error)
        worker.finished.connect(lambda: self._on_generator_finished(worker))

    def _temporary_template_path(self, frame, template_dir=None):
        return os.path.join(template_dir or self._profile_template_dir, f"temp_{frame}.jpg")

    def _cleanup_temporary_templates(self, template_dir=None):
        template_dir = template_dir or self._profile_template_dir
        if not template_dir:
            return
        for frame in range(1, ResetGenerator.CAPTURE_COUNT + 1):
            try:
                os.remove(self._temporary_template_path(frame, template_dir))
            except FileNotFoundError:
                pass

    def _cleanup_finished_templates(self):
        active_template_dir = None
        if self._reset_generator is not None and self._reset_generator.isRunning():
            active_template_dir = self._reset_generator.template_dir
        finished_dirs = {
            template_dir for template_dir in self._pending_cleanup_dirs
            if template_dir != active_template_dir
        }
        for template_dir in finished_dirs:
            self._cleanup_temporary_templates(template_dir)
        self._pending_cleanup_dirs.difference_update(finished_dirs)

    def _on_generator_finished(self, worker):
        if self._reset_generator is not worker:
            self._cleanup_finished_templates()
            return
        self._reset_generator = None
        self._cleanup_finished_templates()
        if self._reopen_after_stop and self.isVisible():
            self._reopen_after_stop = False
            self._prepare_dialog()
        elif self.isVisible() and self.generate_btn.text() == "Stopping...":
            self.generate_btn.setText("Generate")
            self.generate_btn.setEnabled(True)

    def generate_clicked(self):
        if self._reset_generator is not None and self._reset_generator.isRunning():
            return
        self._create_generator()
        self.generate_btn.setText("Waiting..")
        self.generate_btn.setEnabled(False)
        self._reset_generator.start()

    def apply_clicked(self):
        if config.get_active_capture_profile_id() != self._profile_id:
            self.display_error_message("The active capture profile changed. Reopen the generator and try again.")
            return
        os.makedirs(self._profile_template_dir, exist_ok=True)
        reset_one = os.path.join(self._profile_template_dir, "reset_one.jpg").replace("\\", "/")
        reset_two = os.path.join(self._profile_template_dir, "reset_two.jpg").replace("\\", "/")
        try:
            shutil.copyfile(self._temporary_template_path(self.gen_1_sb.value()), reset_one)
            shutil.copyfile(self._temporary_template_path(self.gen_2_sb.value()), reset_two)
        except FileNotFoundError:
            self.display_error_message("Generated reset frames could not be found.")
            return

        self._cleanup_temporary_templates()
        config.set_key("advanced", "reset_frame_one", reset_one)
        config.set_key("advanced", "reset_frame_two", reset_two)
        config.save_config()
        self.applied.emit()

        self.hide()

    def cancel_clicked(self):
        self.hide()

    def on_generate(self):
        self.gen_1_px.setPixmap(QtGui.QPixmap(self._temporary_template_path(2)).scaledToWidth(251).scaledToHeight(137))
        self.gen_2_px.setPixmap(QtGui.QPixmap(self._temporary_template_path(3)).scaledToWidth(251).scaledToHeight(137))
        self.gen_1_sb.setValue(2)
        self.gen_2_sb.setValue(3)
        self.generate_btn.setText("Generate")
        self.generate_btn.setEnabled(True)
        self.apply_btn.setEnabled(True)
        self.gen_1_sb.setEnabled(True)
        self.gen_2_sb.setEnabled(True)

    def gen_1_changed(self, value):
        self.gen_1_px.setPixmap(QtGui.QPixmap(self._temporary_template_path(value)).scaledToWidth(251).scaledToHeight(137))

    def gen_2_changed(self, value):
        self.gen_2_px.setPixmap(QtGui.QPixmap(self._temporary_template_path(value)).scaledToWidth(251).scaledToHeight(137))

    def closeEvent(self, event):
        self._reopen_after_stop = False
        self._stop_generator(cleanup=True)
        super().closeEvent(event)

    def on_error(self, error):
        self._stop_generator()
        self.generate_btn.setText("Generate")
        self.generate_btn.setEnabled(True)
        self.apply_btn.setEnabled(False)
        self.display_error_message(error)

    def display_error_message(self, message, title="Error"):
        """
        Display a warning dialog with given title and message
        :param title: Window title
        :param message: Warning/error message
        :return:
        """
        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.show()


class ResetGenerator(QtCore.QThread):
    CAPTURE_COUNT = 5

    generated = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)

    def __init__(self, template_dir):
        super().__init__()
        self._running = False
        self._capture_released = False
        self._template_dir = template_dir
        if config.get("game", "capture_source") == "device":
            self._game_capture = DeviceCapture(config.get("game", "device_index"), config.get("game", "game_region"),
                                               GAME_JP, config.get("game", "device_resolution"))
            self._capture_name = f"Device {config.get('game', 'device_index')}"
        else:
            self._game_capture = GameCapture(config.get("game", "process_name"), config.get("game", "game_region"), GAME_JP)
            self._capture_name = config.get("game", "process_name")

    @property
    def template_dir(self):
        return self._template_dir

    def run(self):
        self._running = True
        reset_occurred = False
        frame = 0

        generated_frames = []

        while self._running:
            c_time = time.time()
            try:
                self._game_capture.capture()
            except Exception:
                if self._running:
                    self.error.emit("Unable to capture " + self._capture_name)
                self._running = False
                break

            reset_region = self._game_capture.get_region(RESET_REGION)
            fadeout_region = self._game_capture.get_region(FADEOUT_REGION)

            if is_black(fadeout_region, 0.1, 0.97):
                reset_occurred = True

            if reset_occurred:
                if not is_black(fadeout_region, config.get("thresholds", "black_threshold"), 0.99):
                    frame += 1

                    if frame <= self.CAPTURE_COUNT:
                        generated_frames.append(reset_region)
                    else:
                        self._running = False

            try:
                time.sleep((1 / 29.97) - (time.time() - c_time))
            except ValueError:
                pass

        self._release_capture()

        if len(generated_frames) != self.CAPTURE_COUNT:
            return
        os.makedirs(self._template_dir, exist_ok=True)
        for i, frame in enumerate(generated_frames):
            cv2.imwrite(os.path.join(self._template_dir, f"temp_{i + 1}.jpg"), frame)

        self.generated.emit()

    def stop(self):
        self._running = False
        self._release_capture()

    def _release_capture(self):
        if isinstance(self._game_capture, DeviceCapture) and not self._capture_released:
            self._capture_released = True
            self._game_capture.release()
