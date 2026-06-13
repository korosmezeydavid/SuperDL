"""SuperDL - többfunkciós, több szálú letöltő."""

__version__ = "2.0.2"

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
