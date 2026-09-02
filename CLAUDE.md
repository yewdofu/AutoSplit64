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

# テスト（CIでもPRごとに実行される）
uv run --no-sync pytest -q

# リリースzipの検証（zip作成後。CIでも公開直前に実行される）
python tools/verify_release_zip.py AutoSplit64-<version>.zip
```

lintは設定されていない。

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
- **実行ファイル名は `AS64Updater.exe`（`Updater.exe` から改名済み、#48）**。Windowsでは実行中のexeを書き込みオープンできず、リリースzipの最終エントリだった `Updater.exe` 自身の展開に失敗して更新が中断していた。改名によりzipから同名エントリが消えるため、配布済みの旧 `Updater.exe` でも展開が最後まで通る。改名前の `Updater.exe` は旧インストールに残るが、参照されないので無害
- **名前の整合性**: updaterの名前は `as64core/updater.py`（起動する側）と `.github/workflows/release.yml`（ビルドする側）の2箇所、アプリ本体の名前は `AutoSplit64.spec`（生成する側）と `updater/main.go`（再起動する側）の2箇所にある。`tests/test_issue48_updater_binary_name.py` が相互に固定しており、`tools/verify_release_zip.py` がリリースzipの実物を同じ名前で検証する（release.ymlの公開直前ステップ）

### Model

- Format: ONNX (`resources/model/default_model.onnx`)
- Input: float32 array `(1, 40, 67, 3)` normalized to [0, 1]
- Output: class probabilities (star counts 0–120+)
- Original format was Keras HDF5 (`default_model.hdf5`). Convert with `tools/convert_to_onnx.py`.

### Key Design Patterns

- **Thread-based processing**: `as64core/base.py` runs as a `threading.Thread`; GUI communicates via PyQt signals
- **ProcessorSwitch**: State machine that dispatches to registered `Process` objects based on split type
- **Resource vs. user-data paths**: `as64core/resource_utils.py` exposes two APIs — `resource_path()` for bundled, read-only assets (resolves against `sys._MEIPASS` when frozen, the project root otherwise) and `user_data_path()` for writable data like `config.json` and routes (resolves next to the executable when frozen, the project root otherwise)

## リリース前の確認

アップデートを実行するのは**ひとつ前のリリースに同梱された updater** なので、リリースzipの不備は後続のリリースでは直せない。タグを打つ前に以下を通すこと。

```bash
# 1. 名前の整合性 + 既存のテスト
uv run --no-sync pytest -q

# 2. updaterの更新処理（Windows必須）
cd updater
go test ./...

# 3. リリースzipの中身（zipを作った後。CIでも公開直前に自動実行される）
python tools/verify_release_zip.py AutoSplit64-<version>.zip
```

`updater/main_test.go` は**実際に起動したプロセス**として更新処理を走らせる。テストバイナリを一時的なインストール先に `AS64Updater.exe` としてコピーし、自分自身を含むzipを、インストール先とは別のカレントディレクトリから適用させる。これにより以下が同時に検証される。

- 実行中のexeは書き込みオープンできない（`os.Create` が失敗すること自体をテストで固定）
- リネームによる自己すり替えが成立する
- 展開先がカレントディレクトリではなく実行ファイルの位置を基準にしている
- zipエントリがインストール先の外を指す場合は展開を中断し、インストール先を書き換えない

CI（`.github/workflows/test.yml`）で pytest と go test の両方が全PRに対して走る。
