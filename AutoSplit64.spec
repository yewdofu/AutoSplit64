# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['AutoSplit64.py'],
    pathex=[],
    binaries=[
        ('.venv/Lib/site-packages/onnxruntime/capi/onnxruntime.dll', '.'),
        ('.venv/Lib/site-packages/onnxruntime/capi/onnxruntime_providers_shared.dll', '.'),
    ],
    datas=[
        ('resources', 'resources'),
        ('logic', 'logic'),
        ('templates', 'templates'),
        ('defaults.json', '.'),
        ('.version', '.'),
    ],
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtWidgets',
        'PyQt5.QtGui',
        'onnxruntime',
        'onnxruntime.capi',
        'cv2',
        'numpy',
        'win32api',
        'win32gui',
        'win32ui',
        'win32process',
        'win32con',
        'psutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rthook_onnxruntime.py'],
    excludes=['tensorflow', 'keras', 'torch'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutoSplit64',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/gui/icons/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AutoSplit64',
)
