# -*- mode: python ; coding: utf-8 -*-
# PyInstaller onedir：dist/Page/Page.exe + _internal（勿用 onefile）
# 打包前：age.exe、age-plugin-batchpass.exe；图标在 ui/page.ico（可选 ui/password.ico）

import os
import sys

block_cipher = None

_datas = [("ui/page.ico", ".")]
if os.path.isfile(os.path.join("ui", "password.ico")):
    _datas.append((os.path.join("ui", "password.ico"), "."))

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
    excludes=[],
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
