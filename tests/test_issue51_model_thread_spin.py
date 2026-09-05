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


@pytest.mark.parametrize("key", [
    "session.intra_op.allow_spinning",
    "session.inter_op.allow_spinning",
])
def test_spinning_is_disabled(key):
    # The keys are spelled out here rather than read back from the module:
    # onnxruntime accepts any string as a config entry and silently falls
    # back to the default for one it does not know, so a typo in the
    # implementation has to fail as a missing entry against these names.
    assert _session_options().get_session_config_entry(key) == "0"


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
