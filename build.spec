# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

mediapipe_data = collect_data_files('mediapipe')
cv2_data = collect_data_files('cv2')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets/*', 'assets'),
        ('ui/styles.qss', 'ui'),
    ] + mediapipe_data + cv2_data,
    hiddenimports=[
        'cv2', 'numpy', 'mediapipe',
        'mediapipe.python.solutions.face_mesh',
        'config', 'config.settings', 'config.profiles',
        'core', 'core.engine', 'core.logger', 'core.state_machine',
        'vision', 'vision.mediapipe_detector', 'vision.calibrator',
        'vision.user_profiles', 'vision.gaze_estimator',
        'ui', 'ui.main_window', 'ui.mini_window', 'ui.overlay',
        'ui.calibration_dialog', 'ui.widgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'pandas', 'tkinter'],
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
    name='ScreenGuard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # SET TO False FOR RELEASE
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ScreenGuard',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='ScreenGuard.app',
        icon='assets/icon.ico',
        bundle_identifier='com.screenguard.app',
    )
