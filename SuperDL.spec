# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = [('bin\\aria2c.exe', '.'),
            ('bin\\ffmpeg.exe', '.'),
            ('bin\\ffprobe.exe', '.'),
            ('bin\\espeak-ng.exe', '.'),
            ('bin\\libespeak-ng.dll', '.'),
            ('bin\\bass.dll', '.'),
            ('bin\\bassmix.dll', '.'),
            ('bin\\bassenc.dll', '.'),
            ('bin\\bassenc_mp3.dll', '.')]
# eSpeak-NG hangadatok (magyar hang a self-voice-hoz) – a teljes mappa
datas += [('bin\\espeak-ng-data', 'espeak-ng-data')]
hiddenimports = ['win32com.client', 'pythoncom', 'pywintypes', 'win32crypt']
datas += collect_data_files('docx')
hiddenimports += collect_submodules('yt_dlp')
hiddenimports += collect_submodules('feedparser')
hiddenimports += collect_submodules('ebooklib')
hiddenimports += collect_submodules('pypdf')
tmp_ret = collect_all('sounddevice')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('edge_tts')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
# magic-wormhole (P2P fájlküldés) – Twisted-alapú, sok rejtett importtal
for _pkg in ('wormhole', 'twisted', 'autobahn', 'automat', 'incremental',
             'constantly', 'hyperlink', 'txaio', 'zope', 'nacl', 'spake2',
             'hkdf', 'cbor2', 'click', 'humanize', 'iterable_io',
             'zipstream', 'attr', 'attrs'):
    try:
        tmp_ret = collect_all(_pkg)
        datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
    except Exception:
        pass


a = Analysis(
    ['superdl_gui.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SuperDL',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
