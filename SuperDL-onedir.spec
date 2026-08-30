# -*- mode: python ; coding: utf-8 -*-
# ONEDIR build a moduláris rendszerhez + Inno Setup telepítőhöz.
# (A onefile SuperDL.spec érintetlen marad; ez a kettő egymás mellett él, amíg
#  a moduláris/onedir átállás véglegesedik.)
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
            ('bin\\bassenc_mp3.dll', '.'),
            ('bin\\bass_fx.dll', '.')]
# eSpeak-NG hangadatok (magyar hang a self-voice-hoz) – a teljes mappa
datas += [('bin\\espeak-ng-data', 'espeak-ng-data')]
datas += [('superdl\\startup.wav', 'superdl')]     # induló szignál (Farkas kérése)
datas += [('superdl\\tolk\\nvdaControllerClient64.dll', 'superdl\\tolk')]  # képernyőolvasó-kimenet (NVDA)
hiddenimports = ['win32com.client', 'pythoncom', 'pywintypes', 'win32crypt']
# A Super Mail modul e-mail-protokolljai. A Core sehol nem importálja ezeket,
# ezért a PyInstaller egyébként KIHAGYNÁ őket a fagyasztott exe-ből, és a mail
# modul betöltése csendben elbukna (nincs Kommunikáció menü). Kényszerítve
# begyűjtjük. (Az `email`/`html.parser` transzitívan már bekerül az urllib-en át.)
hiddenimports += ['imaplib', 'poplib', 'smtplib', 'email.mime.multipart',
                  'email.mime.text', 'mailbox']
datas += collect_data_files('docx')
# IANA időzónák (ICS TZID) – Windowson nincs rendszer-tzdata
datas += collect_data_files('tzdata')
hiddenimports += collect_submodules('yt_dlp')
hiddenimports += collect_submodules('feedparser')
hiddenimports += collect_submodules('ebooklib')
hiddenimports += collect_submodules('pypdf')
hiddenimports += collect_submodules('fpdf')      # beépített PDF (dok.-konverter)
# A TELJES superdl csomag (a megosztott runtime: videocompose, audioengine,
# booktext, ocr, extratools…) – a kiemelt MODULOK `from superdl import …`-zal
# hívják, ezért akkor is bundle-ölni kell, ha a built-in gui már nem importálja.
hiddenimports += collect_submodules('superdl')
# A Super Media modul „Super Recorder" vokóder/harmonizer-e numpy-t használ.
hiddenimports += collect_submodules('numpy')
# OFFLINE FORDÍTÁS (superdl/offlineford.py): a CTranslate2 futtatókörnyezet és
# a két szövegdaraboló. Ezért nem lehetett modul-frissítés: fordított (bináris)
# csomagok, amiket egy modul-ZIP nem tud a fagyasztott programba telepíteni.
# A NYELVI MODELLEKET nem csomagoljuk – azokat a felhasználó tölti le
# nyelvenként egyszer (~80 MB), és utána offline mennek.
# CSAK a FUTTATÁSHOZ kellő rész: a `collect_all('ctranslate2')` az
# ÁTALAKÍTÓ almodulokon át behúzta a torch-ot (+365 MB!), ami a fordításhoz
# nem kell – ezért kézzel vesszük a DLL-eket és a bővítményt.
from PyInstaller.utils.hooks import collect_dynamic_libs
binaries += collect_dynamic_libs('ctranslate2')
hiddenimports += ['ctranslate2', 'ctranslate2._ext']
# A `converters` alcsomagot kihagyjuk (lásd az `excludes`-t), viszont a csomag
# __init__.py-ja a MODELS és SPECS alcsomagot is importálja – ezeket kézzel
# kérjük, mert a converters kizárása után az elemző nem jut el hozzájuk.
# Enélkül a kész programban `import ctranslate2` elszáll, és a helyben futó
# fordítás csendben eltűnik az F9 listájából. (A kódoldali biztosíték az
# `superdl/offlineford.ct2()`.) [2026-08-30]
hiddenimports += collect_submodules('ctranslate2.models')
hiddenimports += collect_submodules('ctranslate2.specs')
hiddenimports += ['ctranslate2.logging', 'ctranslate2.version',
                  'ctranslate2.extensions']
tmp_ret = collect_all('sacremoses')     # tokenizáló + a hozzá tartozó adatfájlok
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
hiddenimports += collect_submodules('subword_nmt')
hiddenimports += ['sentencepiece', 'sentencepiece._sentencepiece']
binaries += collect_dynamic_libs('sentencepiece')

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
    excludes=['torch', 'transformers', 'ctranslate2.converters', ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# ONEDIR: az EXE NEM tartalmazza a binárisokat/adatokat (exclude_binaries),
# azokat a COLLECT gyűjti a dist/SuperDL/ mappába – nincs minden indításkori
# temp-kicsomagolás (ez szüntette meg az SSL/ffmpeg double-click hibák melegágyát
# és teszi azonnal indíthatóvá az appot).
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SuperDL',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
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
    name='SuperDL',
)
