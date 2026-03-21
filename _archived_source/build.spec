# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None
base_dir = os.path.dirname(os.path.abspath(SPEC))

datas_list = [
    (os.path.join(base_dir, 'data', 'import_sample.json'), 'data'),
]
adb_dir = os.path.join(base_dir, 'adb')
if os.path.isdir(adb_dir):
    datas_list.append((adb_dir, 'adb'))

a = Analysis(
    [os.path.join(base_dir, 'main.py')],
    pathex=[base_dir],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'core.profile_manager',
        'core.config_manager',
        'core.adb_manager',
        'core.device_service',
        'core.push_policy_service',
        'ui.main_window',
        'ui.save_dialog',
        'ui.device_popup',
        'ui.settings_menu',
        'ui.push_policy_tab',
        'ui.game_perf_tab',
        'ui.styles',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt6.QtWebEngine',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'PyQt6.Qt3DCore',
        'PyQt6.Qt3DRender',
        'PyQt6.Qt3DInput',
        'PyQt6.Qt3DExtras',
        'PyQt6.QtBluetooth',
        'PyQt6.QtNfc',
        'PyQt6.QtSensors',
        'PyQt6.QtSerialPort',
        'PyQt6.QtSvg',
        'PyQt6.QtSvgWidgets',
        'PyQt6.QtTest',
        'PyQt6.QtXml',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Toolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Toolkit',
)
