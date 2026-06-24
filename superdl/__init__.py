"""SuperDL - többfunkciós, több szálú letöltő."""

__version__ = "3.25.1"

# --- HTTPS-tanúsítvány: megbízható CA-csomag mindenhol ----------------
# Egyes Windows-gépeken a rendszer CA-tára hiányos/elavult, és a urllib SSL-
# ellenőrzése elbukik („unable to get local issuer certificate"), ezért a
# self-update és a motor-frissítés nem működik. A beágyazott certifi CA-
# csomagra állítjuk az alapértelmezett HTTPS-kontextust, hogy az összes
# urllib-alapú hálózati hívás (frissítő, IPTV, Pandoc-letöltés) mindenhol,
# a Windows-tártól függetlenül megbízhatóan ellenőrizzen.
try:                                       # noqa: E402
    import ssl as _ssl
    import certifi as _certifi
    _ssl._create_default_https_context = (
        lambda *a, **k: _ssl.create_default_context(cafile=_certifi.where()))
except Exception:
    pass

# --- frissített yt-dlp betöltése -------------------------------------
# Ha a felhasználó frissítette a yt-dlp-t (~/.superdl/bin/ytdlp), onnan
# kell betölteni a beágyazott helyett. PyInstaller-csomagban a beágyazott
# (frozen) importáló megelőzné a sys.path-ot, ezért egy saját, kizárólag a
# yt_dlp csomagra szabott betöltőt teszünk a sys.meta_path elejére.
import sys as _sys
from importlib.machinery import PathFinder as _PathFinder
from pathlib import Path as _Path

_ytdlp_base = _Path.home() / ".superdl" / "bin" / "ytdlp"


class _ExternalYtdlpFinder:
    """A yt_dlp csomagot és almoduljait a frissített mappából tölti be.
    Minden más névnél azonnal None-t ad vissza (nem nyúl az importhoz)."""

    def __init__(self, base):
        self.base = str(base)

    def find_spec(self, name, path, target=None):
        if name == "yt_dlp":
            return _PathFinder.find_spec(name, [self.base])
        if name.startswith("yt_dlp."):
            return _PathFinder.find_spec(name, path)
        return None


if (_ytdlp_base / "yt_dlp" / "__init__.py").is_file():
    if not any(isinstance(f, _ExternalYtdlpFinder) for f in _sys.meta_path):
        _sys.meta_path.insert(0, _ExternalYtdlpFinder(_ytdlp_base))
