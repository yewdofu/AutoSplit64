from . import constants

from . import config


#
# Constants
#

DEFAULT_FRAME_RATE = constants.DEFAULT_FRAME_RATE
DEFAULT_LS_HOST = constants.DEFAULT_LS_HOST
DEFAULT_LS_PORT = constants.DEFAULT_LS_PORT
GAME_JP = constants.GAME_JP
GAME_US = constants.GAME_US
TIMING_RTA = constants.TIMING_RTA
TIMING_UP_RTA = constants.TIMING_UP_RTA
TIMING_FILE_SELECT = constants.TIMING_FILE_SELECT
PREDICTION_MODE = constants.PREDICTION_MODE
CONFIRMATION_MODE = constants.CONFIRMATION_MODE
SPLIT_INITIAL = constants.SPLIT_INITIAL
SPLIT_NORMAL = constants.SPLIT_NORMAL
SPLIT_FADE_ONLY = constants.SPLIT_FADE_ONLY
SPLIT_FINAL = constants.SPLIT_FINAL
SPLIT_MIPS = constants.SPLIT_MIPS
SPLIT_MIPS_X = constants.SPLIT_MIPS_X
SPLIT_XCAM = constants.SPLIT_XCAM
NO_FADE = constants.NO_FADE
FADEOUT_PARTIAL = constants.FADEOUT_PARTIAL
FADEOUT_COMPLETE = constants.FADEOUT_COMPLETE
FADEIN_PARTIAL = constants.FADEIN_PARTIAL
FADEIN_COMPLETE = constants.FADEIN_COMPLETE
GAME_REGION = constants.GAME_REGION
STAR_REGION = constants.STAR_REGION
LIFE_REGION = constants.LIFE_REGION
NO_HUD_REGION = constants.NO_HUD_REGION
RESET_REGION = constants.RESET_REGION
FADEOUT_REGION = constants.FADEOUT_REGION
FADEIN_REGION = constants.FADEIN_REGION
POWER_REGION = constants.POWER_REGION
XCAM_REGION = constants.XCAM_REGION


#
# Route Class
#

class Route(object):
    def insert_split(self, index) -> None:
        pass

    def remove_split(self, index) -> None:
        pass


#
# Split Class
#

class Split(object):
    pass


#
# Base
#
ls_host: str = DEFAULT_LS_HOST
ls_port: int = DEFAULT_LS_PORT

fps: float = DEFAULT_FRAME_RATE
current_time: float = 0.0
game_version: str = GAME_JP
route = Route()
route_length: int = 0
star_count: int = 0
previous_split_initial_star: int = 0
next_split_split_star: int = 0
last_split: int = 0
collection_time: int = 0
xcam_count: int = 0
xcam_percent: float = 0.0
in_xcam: bool = False
fadeout_count: int = 0
fadein_count: int = 0
fade_status: str = NO_FADE
prediction_info = None
execution_time: float = 0.0
start_on_reset: bool = True

# Set by Base.__init__ once init() has run; None means "not initialized yet".
_base = None


class NotInitializedError(RuntimeError):
    """Raised when as64core functionality is used before init() has run."""


def _require_init():
    raise NotInitializedError("as64core.init() must be called before using this function")


def init() -> None:
    import sys
    from .base import Base

    module = sys.modules[__name__]

    Base(module)


def start() -> None:
    _require_init()


def stop() -> None:
    # Safe no-op before init: the GUI calls this unconditionally on shutdown,
    # including when the app is closed without ever pressing Start.
    pass


def set_star_count(p_int: int) -> None:
    _require_init()


def enable_predictions(enable: bool) -> None:
    _require_init()


def enable_fade_count(enable: bool) -> None:
    _require_init()


def enable_xcam_count(enable: bool) -> None:
    _require_init()


def set_in_game(ended: bool) -> None:
    _require_init()

def get_region(region):
    _require_init()


def get_region_rect(region) -> list:
    _require_init()


def register_split_processor(split_type, processor) -> None:
    _require_init()


#
# Split Functions
#

def split() -> None:
    _require_init()


def reset() -> None:
    _require_init()


def skip() -> None:
    _require_init()


def undo() -> None:
    _require_init()


#
# Tracking Functions
#
# fadeout()/fadein()/increment_star() are never wired up by Base - they are
# unreachable regardless of init state, so they're left as no-ops here
# rather than turned into a fail-fast trap (see issue #12).

def fadeout() -> None:
    pass


def fadein() -> None:
    pass


def increment_star() -> None:
    pass


def incoming_split(star_count: bool = True, fadeout: bool = True, fadein: bool = True) -> bool:
    _require_init()


def current_split():
    _require_init()


def split_index() -> int:
    _require_init()


#
# Route
#
# load()/save() are likewise never wired up by Base - left as no-ops for the
# same reason as the tracking functions above.

def load() -> Route:
    pass


def save() -> None:
    pass


#
# Listeners
#

def set_update_listener(listener) -> None:
    _require_init()


def set_error_listener(listener) -> None:
    _require_init()


def set_started_listener(listener) -> None:
    _require_init()


def force_update() -> None:
    _require_init()