import ctypes
import os
import sys

if hasattr(sys, "_MEIPASS"):
    capi_dir = os.path.join(sys._MEIPASS, "onnxruntime", "capi")
    if os.path.isdir(capi_dir):
        os.add_dll_directory(capi_dir)
    os.add_dll_directory(sys._MEIPASS)

    # Explicitly preload onnxruntime DLLs so that onnxruntime_pybind11_state.pyd
    # can find them via LoadLibrary inside its DllMain (os.add_dll_directory alone
    # is not sufficient when the DLL is loaded inside DllMain initialization).
    for _dll_name in ["onnxruntime_providers_shared.dll", "onnxruntime.dll"]:
        for _search_dir in [capi_dir, sys._MEIPASS]:
            _dll_path = os.path.join(_search_dir, _dll_name)
            if os.path.isfile(_dll_path):
                try:
                    ctypes.CDLL(_dll_path)
                except OSError:
                    pass
                break
