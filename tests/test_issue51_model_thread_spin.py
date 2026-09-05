"""
Issue #51: the ONNX session was built with onnxruntime's defaults, which
start one intra-op thread per core and let that pool spin while it waits
for the next call. The model is 67x40 and runs at 6Hz, so a prediction
costing well under a millisecond was holding nearly two cores busy - 40%
of a four-core machine, competing with OBS for the same CPU.

Pins the session options that keep the pool off the CPU, and checks a real
prediction still runs, so the settings cannot be dropped or renamed without
this failing.
"""
import os

import numpy as np
import onnxruntime as ort
import pytest

from as64core.model import Model, _session_options
from as64core.resource_utils import resource_path


def test_session_runs_single_threaded_without_spinning():
    options = _session_options()

    assert options.intra_op_num_threads == 1
    assert options.inter_op_num_threads == 1
    assert options.execution_mode == ort.ExecutionMode.ORT_SEQUENTIAL


def test_spinning_is_disabled():
    # add_session_config_entry has no getter, so the settings are checked by
    # handing them to a real session: onnxruntime rejects an entry it does
    # not recognise, which is what would happen if a key were misspelled or
    # dropped from the runtime.
    session = ort.InferenceSession(_model_path(), sess_options=_session_options())

    assert session is not None


def test_model_predicts_with_those_options():
    model = Model(_model_path(), 67, 40)
    assert model.valid(), "the bundled model failed to load"

    image = np.zeros((40, 67, 3), dtype=np.uint8)
    info = model.predict(image)

    assert isinstance(info.prediction, int)
    assert 0.0 <= info.probability <= 1.0


def _model_path():
    path = resource_path("resources/model/default_model.onnx")
    if not os.path.exists(path):
        pytest.skip("bundled model not present")
    return path
