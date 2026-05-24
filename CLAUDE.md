# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoSplit64 is a Windows desktop application for automating LiveSplit during Super Mario 64 speedruns. It captures the game screen in real time, analyzes game state via an ONNX model, and sends split commands to LiveSplit.

- Version: 0.3.0
- GUI: PyQt5
- Python: 3.11+
- Package manager: uv

## Commands

```bash
# 環境構築（初回 or pyproject.toml変更後）
uv sync

# アプリ起動（開発）
uv run AutoSplit64.py

# exe化
uv run --group dev pyinstaller AutoSplit64.spec

# モデル変換（HDF5 → ONNX）
uv run --group dev python tools/convert_to_onnx.py
```

There are no configured test or lint commands.

## Architecture

Entry point is `AutoSplit64.py` (PyQt5 application).

**Data flow:** GameCapture (win32 API) → ONNX model inference → state machine (ProcessorSwitch) → LiveSplit socket

```
AutoSplit64.py          # QApplication entry point
  └── as64gui/app.py   # Main window (PyQt5)
  └── as64core/        # Core logic (thread-based)
        base.py        # Main loop thread
        model.py       # ONNX inference (onnxruntime)
        game_capture.py # Screen capture
        processing.py  # Processor/state machine
        route.py / route_loader.py
        livesplit.py   # TCP socket to LiveSplit Server
        config.py      # defaults.ini + user config
```

### Key Modules

| Module | Role |
|---|---|
| `as64core/base.py` | Main loop; orchestrates capture → inference → processor |
| `as64core/model.py` | ONNX model loading and inference (onnxruntime) |
| `as64core/game_capture.py` | Screen region extraction via Windows API |
| `as64core/processing.py` | ProcessorSwitch state machine |
| `as64core/route.py` | Split data structure |
| `as64core/route_loader.py` | Route file parsing |
| `as64core/livesplit.py` | TCP socket commands to LiveSplit Server |
| `as64core/config.py` | Config read/write (defaults.ini) |
| `as64core/resource_utils.py` | Path resolution (dev + PyInstaller MEIPASS) |
| `as64gui/` | All PyQt5 UI code |
| `as64processes/` | Split processor implementations (standard, xcam, ddd, final) |
| `logic/` | `.processor` files defining state machine graphs |

### Configuration

- `defaults.ini` — Default config (JSON). Includes model path, capture region, LiveSplit host/port, thresholds.
- User config is written alongside `defaults.ini` at runtime.

### Build Pipeline

`uv run --group dev pyinstaller AutoSplit64.spec` bundles:
- All Python modules
- `resources/` (GUI assets, ONNX model, icons)
- `logic/` (`.processor` state machine files)
- `templates/` (reset detection templates)
- `defaults.ini`, `.version`

Output: `dist/AutoSplit64/AutoSplit64.exe` (onedir形式, ~270MB)

### Model

- Format: ONNX (`resources/model/default_model.onnx`)
- Input: float32 array `(1, 40, 67, 3)` normalized to [0, 1]
- Output: class probabilities (star counts 0–120+)
- Original format was Keras HDF5 (`default_model.hdf5`). Convert with `tools/convert_to_onnx.py`.

### Key Design Patterns

- **Thread-based processing**: `as64core/base.py` runs as a `threading.Thread`; GUI communicates via PyQt signals
- **ProcessorSwitch**: State machine that dispatches to registered `Process` objects based on split type
- **resource_path()**: All asset paths go through `as64core.resource_utils.resource_path()`, which resolves against `sys._MEIPASS` when frozen by PyInstaller and `os.path.abspath(".")` otherwise
