# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Escape Room Master.

Build with:
    .venv\Scripts\pyinstaller.exe EscapeRoomMaster.spec
"""

block_cipher = None

import os, glob as _glob
from PyInstaller.utils.hooks import collect_all

# Find python3xx.dll next to the Python interpreter used to run PyInstaller
_py_dir = os.path.dirname(os.__file__)          # …/Lib inside the Python install
_py_root = os.path.dirname(_py_dir)             # the Python install root
_dll_hits = _glob.glob(os.path.join(_py_root, "python3*.dll"))
_extra_bins = [(_dll, ".") for _dll in _dll_hits]

# Collect httpx and its runtime dependencies (data files + hidden imports)
_httpx_d, _httpx_b, _httpx_h = collect_all("httpx")
_httpcore_d, _httpcore_b, _httpcore_h = collect_all("httpcore")
_certifi_d, _certifi_b, _certifi_h = collect_all("certifi")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=_extra_bins + _httpx_b + _httpcore_b + _certifi_b,
    datas=_httpx_d + _httpcore_d + _certifi_d + [("assets/fonts", "assets/fonts")],
    hiddenimports=[
        # PyQt6 multimedia backend (Windows Media Foundation)
        "PyQt6.QtMultimedia",
        "PyQt6.QtMultimediaWidgets",
        # Ensure all Qt plugins land in the bundle
        "PyQt6.sip",
        # httpx and its deps for Turso/booking sync
        *_httpx_h,
        *_httpcore_h,
        *_certifi_h,
        "h11",
        "h11._readers",
        "h11._writers",
        "h11._events",
        "h11._connection",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Things we definitely don't need
        "tkinter",
        "unittest",
        "xmlrpc",
    ],
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
    exclude_binaries=True,   # onedir mode
    name="EscapeRoomMaster",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # no black terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="EscapeRoomMaster",
)
