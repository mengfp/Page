# -*- mode: python ; coding: utf-8 -*-
# PyInstaller onedir：dist/Page/Page.exe + _internal（勿用 onefile）
# 打包前：age.exe、age-plugin-batchpass.exe；图标在 ui/page.ico（可选 ui/password.ico）

import os
import sys

block_cipher = None

_datas = [("ui/page.ico", ".")]
if os.path.isfile(os.path.join("ui", "password.ico")):
    _datas.append((os.path.join("ui", "password.ico"), "."))

# 纯 Widgets，不用的 Qt 子模块排除掉，常能少几十 MB（若启动报错再去掉对应项）
_EXCLUDE = [
    "matplotlib",
    "numpy",
    "pandas",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQuick3D",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtSql",
    "PySide6.QtNetworkAuth",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtLocation",
    "PySide6.QtSerialPort",
    "PySide6.QtWebSockets",
    "PySide6.QtHttpServer",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
]

binaries = [
    ("age.exe", "."),
    ("age-plugin-batchpass.exe", "."),
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    # password.ico 可选：存在则打进包，供 PassphraseDialog 标题栏
    datas=_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUDE,
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
    name="Page",
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
    icon=os.path.join("ui", "page.ico") if sys.platform == "win32" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Page",
)
