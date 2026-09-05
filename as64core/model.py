import onnxruntime as ort
import numpy as np

from .image_utils import convert_to_np


class PredictionInfo(object):
    def __init__(self, prediction, probability):
        self.prediction = prediction
        self.probability = probability


def _session_options() -> ort.SessionOptions:
    """Keep onnxruntime off the CPU between predictions.

    The model is tiny (67x40) and runs at a handful of frames per second, so the
    default thread pool - one thread per core, spinning while it waits for the
    next call - burns whole cores without making inference any faster.
    """
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.add_session_config_entry("session.intra_op.allow_spinning", "0")
    options.add_session_config_entry("session.inter_op.allow_spinning", "0")

    return options


class Model(object):
    def __init__(self, model_path, width, height):
        try:
            self.session = ort.InferenceSession(model_path, sess_options=_session_options())
            self.input_name = self.session.get_inputs()[0].name
        except Exception:
            self.session = None
            self.input_name = None

        self.width = width
        self.height = height

    def valid(self):
        return self.session is not None

    def predict(self, image) -> PredictionInfo:
        np_img = convert_to_np([image]).astype(np.float32)
        output = self.session.run(None, {self.input_name: np_img})[0]
        prediction = int(np.argmax(output))
        probability = float(np.max(output))

        return PredictionInfo(prediction, probability)

