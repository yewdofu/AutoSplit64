import onnxruntime as ort
import numpy as np

from .image_utils import convert_to_np


class PredictionInfo(object):
    def __init__(self, prediction, probability):
        self.prediction = prediction
        self.probability = probability


class Model(object):
    def __init__(self, model_path, width, height):
        try:
            self.session = ort.InferenceSession(model_path)
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

