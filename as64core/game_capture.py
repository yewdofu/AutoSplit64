import cv2
from . import capture_window

from .constants import (
    GAME_US,
    GAME_REGION_BASE,
    GAME_REGION_RATIO,
    STAR_REGION_US_RATIO,
    STAR_REGION_JP_RATIO,
    LIFE_REGION_US_RATIO,
    LIFE_REGION_JP_RATIO,
    FADEOUT_REGION_RATIO,
    FADEIN_REGION_RATIO,
    RESET_REGION_RATIO,
    NO_HUD_REGION_RATIO,
    POWER_REGION_RATIO,
    XCAM_REGION_RATIO,
    GAME_REGION,
    STAR_REGION,
    LIFE_REGION,
    FADEOUT_REGION,
    FADEIN_REGION,
    RESET_REGION,
    NO_HUD_REGION,
    POWER_REGION,
    XCAM_REGION
)


class _BaseCaptureSource:
    def __init__(self, game_region, version):
        self._game_region: list = game_region
        self._version = version
        self._regions: dict = {}
        self._window_image = None
        self._region_images: dict = {}
        self._add_default_regions()

    def _add_default_regions(self):
        def calc_ratio(c, b):
            return [c[0] / b[0], c[1] / b[1], c[2] / b[0], c[3] / b[1]]

        def calc_region(ratio):
            return [int(round(self._game_region[0] + (self._game_region[2] * ratio[0]))),
                    int(round(self._game_region[1] + (self._game_region[3] * ratio[1]))),
                    int(round(self._game_region[2] * ratio[2])),
                    int(round(self._game_region[3] * ratio[3]))]

        if self._version == GAME_US:
            self._regions[STAR_REGION] = calc_region(calc_ratio(STAR_REGION_US_RATIO, GAME_REGION_BASE))
            self._regions[LIFE_REGION] = calc_region(calc_ratio(LIFE_REGION_US_RATIO, GAME_REGION_BASE))
        else:
            self._regions[STAR_REGION] = calc_region(calc_ratio(STAR_REGION_JP_RATIO, GAME_REGION_BASE))
            self._regions[LIFE_REGION] = calc_region(calc_ratio(LIFE_REGION_JP_RATIO, GAME_REGION_BASE))

        self._regions[GAME_REGION] = calc_region(calc_ratio(GAME_REGION_RATIO, GAME_REGION_BASE))
        self._regions[FADEOUT_REGION] = calc_region(calc_ratio(FADEOUT_REGION_RATIO, GAME_REGION_BASE))
        self._regions[FADEIN_REGION] = calc_region(calc_ratio(FADEIN_REGION_RATIO, GAME_REGION_BASE))
        self._regions[RESET_REGION] = calc_region(calc_ratio(RESET_REGION_RATIO, GAME_REGION_BASE))
        self._regions[NO_HUD_REGION] = calc_region(calc_ratio(NO_HUD_REGION_RATIO, GAME_REGION_BASE))
        self._regions[POWER_REGION] = calc_region(calc_ratio(POWER_REGION_RATIO, GAME_REGION_BASE))
        self._regions[XCAM_REGION] = calc_region(calc_ratio(XCAM_REGION_RATIO, GAME_REGION_BASE))

    def is_valid(self) -> bool:
        raise NotImplementedError

    def capture(self) -> None:
        raise NotImplementedError

    def get_capture_size(self):
        raise NotImplementedError

    def get_region(self, region):
        if self._window_image is None:
            self.capture()

        try:
            return self._region_images[region]
        except KeyError:
            try:
                self._region_images[region] = self._crop(*self._regions[region])
                return self._region_images[region]
            except KeyError:
                return None

    def get_region_rect(self, region):
        try:
            return self._regions[region]
        except KeyError:
            return None

    def _crop(self, x, y, width, height):
        return self._window_image[y:y + height, x:x + width]


class GameCapture(_BaseCaptureSource):
    def __init__(self, process_name, game_region, version):
        self._hwnd: int = capture_window.get_hwnd_from_list(process_name, capture_window.get_visible_processes())
        super().__init__(game_region, version)

    def is_valid(self) -> bool:
        return bool(self._hwnd)

    def capture(self) -> None:
        self._window_image = capture_window.capture(self._hwnd)
        self._region_images = {}

    def get_capture_size(self):
        return capture_window.get_capture_size(self._hwnd)


class DeviceCapture(_BaseCaptureSource):
    def __init__(self, device_index, game_region, version):
        self._cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
        super().__init__(game_region, version)

    def is_valid(self) -> bool:
        return self._cap.isOpened()

    def capture(self) -> None:
        ret, frame = self._cap.read()
        if ret:
            self._window_image = frame
        self._region_images = {}

    def get_capture_size(self):
        return [int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))]

    def release(self):
        self._cap.release()


def get_available_devices():
    """Returns list of (index, name) for available video capture devices.

    Uses pygrabber to get DirectShow device names, falls back to index-only on error.
    """
    try:
        from pygrabber.dshow_graph import FilterGraph
        names = FilterGraph().get_input_devices()
        devices = []
        for i, name in enumerate(names):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                devices.append((i, name))
                cap.release()
        return devices
    except Exception:
        devices = []
        for i in range(10):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                devices.append((i, f"Device {i}"))
                cap.release()
        return devices
