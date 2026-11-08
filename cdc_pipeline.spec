# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import sys
from pathlib import Path

block_cipher = None

# Collect all customtkinter assets (themes, json, fonts)
ctk_datas = collect_data_files('customtkinter')

added_files = [
    *ctk_datas,
]

hidden_imports = [
    'customtkinter',
    'darkdetect',
    'matplotlib',
    'matplotlib.backends.backend_tkagg',
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',
    'sqlite3',
    'psutil',
    'pandas',
    'uuid',
    'json',
    'csv',
]

a = Analysis(
    ['main.py'],
    pathex=['.', 'src', 'gui'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['IPython', 'jupyter', 'notebook', 'torch', 'torchaudio', 'torchvision', 'spacy'],
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
    name='CDC_Data_Pipeline_Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
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
    name='CDC_Data_Pipeline_Manager',
)

