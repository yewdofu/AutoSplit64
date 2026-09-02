# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoSplit64 is a Windows desktop application for automating LiveSplit during Super Mario 64 speedruns. It captures the game screen in real time, analyzes game state via an ONNX model, and sends split commands to LiveSplit.

- Version: 0.4.0
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

# AS64Updater.exe ビルド（Go製、updater/ ディレクトリで実行）
cd updater
go mod download
go install github.com/akavel/rsrc@latest
rsrc -manifest app.manifest -o rsrc.syso
go build -ldflags="-H windowsgui" -o ..\dist\AutoSplit64\AS64Updater.exe .

# モデル変換（HDF5 → ONNX）
uv run --group convert python tools/convert_to_onnx.py
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
        config.py      # defaults.json + user config
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
| `as64core/config.py` | Config read/write (defaults.json/config.json) |
| `as64core/resource_utils.py` | Path resolution (dev + PyInstaller MEIPASS) |
| `as64gui/` | All PyQt5 UI code |
| `as64processes/` | Split processor implementations (standard, xcam, ddd, final) |
| `logic/` | `.processor` files defining state machine graphs |

### Configuration

- `defaults.json` — Default config. Includes capture profiles, model paths, capture regions, LiveSplit host/port, and thresholds.
- User config is written as `config.json` alongside the executable. Legacy `config.ini` files are migrated automatically.

### Build Pipeline

`uv run --group dev pyinstaller AutoSplit64.spec` bundles:
- All Python modules
- `resources/` (GUI assets, ONNX model, icons)
- `logic/` (`.processor` state machine files)
- `templates/` (reset detection templates)
- `defaults.json`, `.version`

Output: `dist/AutoSplit64/AutoSplit64.exe` (onedir形式, ~270MB)

`AS64Updater.exe` は Go で別途ビルドし、`dist/AutoSplit64/` に配置する（上記コマンド参照）。CI（GitHub Actions）では自動でビルドされる。

### Updater

- `updater/main.go` — Go製アップデーター。`lxn/walk` でネイティブWindowsウィンドウを表示
- GitHub API (`/repos/yewdofu/AutoSplit64/releases/latest`) からzipをダウンロード・展開後、AutoSplit64.exeを再起動
- `updater/app.manifest` — `requestedExecutionLevel asInvoker` でUAC自動昇格を防止（重要）
- `rsrc.syso` はビルド時に `rsrc` ツールで生成（gitignoreに含まれる）
- バージョンチェックは `as64updater/update_core.py` (QtCore.QThread) で実行
- **実行ファイル名は `AS64Updater.exe`（`Updater.exe` から改名済み、#48）**。Windowsでは実行中のexeを書き込みオープンできないため、リリースzipに自分自身と同名のエントリがあると展開がそこで止まり、再起動まで到達しない。zip内にUpdater自身と同名のファイルを含めないことが前提条件になっている。改名前の `Updater.exe` は旧インストールに残るが、参照されないので無害

### Model

- Format: ONNX (`resources/model/default_model.onnx`)
- Input: float32 array `(1, 40, 67, 3)` normalized to [0, 1]
- Output: class probabilities (star counts 0–120+)
- Original format was Keras HDF5 (`default_model.hdf5`). Convert with `tools/convert_to_onnx.py`.

### Key Design Patterns

- **Thread-based processing**: `as64core/base.py` runs as a `threading.Thread`; GUI communicates via PyQt signals
- **ProcessorSwitch**: State machine that dispatches to registered `Process` objects based on split type
- **Resource vs. user-data paths**: `as64core/resource_utils.py` exposes two APIs — `resource_path()` for bundled, read-only assets (resolves against `sys._MEIPASS` when frozen, the project root otherwise) and `user_data_path()` for writable data like `config.json` and routes (resolves next to the executable when frozen, the project root otherwise)
