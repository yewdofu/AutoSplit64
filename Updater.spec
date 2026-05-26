# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['as64updater/updater.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources/gui/icons', 'resources/gui/icons'),
        ('defaults.ini', '.'),
        ('.version', '.'),
    ],
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtWidgets',
        'PyQt5.QtGui',
        'win32api',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tensorflow', 'keras', 'torch', 'cv2', 'numpy', 'onnxruntime'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Updater',
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
    runtime_tmpdir=None,
)
