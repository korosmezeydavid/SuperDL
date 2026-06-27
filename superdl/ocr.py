"""OCR – kép (TIF, PNG, JPG…) szövegének kinyerése, TÖBB motorral:

  • „ai"        – felhős AI-vízió (OpenAI/Gemini/Claude/Grok); pontos, magyarul
                   is jól olvas, kulcs kell hozzá, de nem kell külön telepítés.
  • „tesseract" – offline Tesseract OCR (ha telepítve van / a PATH-on / a
                   ~/.superdl/bin/tesseract mappában).

Bővíthető további motorokkal (a TENGINES dict-be).
"""

import os
import subprocess
from pathlib import Path

from . import extratools

_NOWIN = 0x08000000 if os.name == "nt" else 0
IMAGE_EXTS = (".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")

# motor-kulcs -> (megjelenített név, kell-e telepítés/kulcs)
ENGINES = {
    "ai": "AI-vízió (felhő, AI-kulcs kell)",
    "tesseract": "Tesseract (offline, első használatkor letölthető)",
}

_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
         ".tif": "image/tiff", ".tiff": "image/tiff"}

_PROMPT = ("Olvasd ki PONTOSAN a képen látható összes szöveget, az eredeti "
           "sorrendben. Csak magát a szöveget add vissza – semmi magyarázatot, "
           "bevezetőt vagy formázást. Ha a kép több hasábos, fentről lefelé, "
           "balról jobbra haladj.")


def available_engines() -> dict:
    """A ténylegesen használható motorok (megjelenített nevükkel)."""
    out = {"ai": ENGINES["ai"]}
    if extratools.find_tesseract():
        out["tesseract"] = ENGINES["tesseract"]
    return out


def ai_ocr(path: str) -> str:
    from . import aiclient
    with open(path, "rb") as f:
        data = f.read()
    mime = _MIME.get(Path(path).suffix.lower(), "image/png")
    return (aiclient.vision(_PROMPT, data, mime=mime) or "").strip()


def tesseract_ocr(path: str, lang: str = "hun+eng") -> str:
    # ha nincs telepítve, megpróbáljuk IGÉNY SZERINT letölteni (saját kiadásból)
    exe = extratools.find_tesseract() or extratools.ensure_tesseract()
    if not exe:
        raise RuntimeError(
            "A Tesseract OCR nem érhető el (a letölthető csomag még nem "
            "elérhető, vagy a letöltés nem sikerült). Addig válaszd az "
            "„AI-vízió” OCR-motort, vagy telepítsd a Tesseractot.")
    try:
        r = subprocess.run([exe, str(path), "stdout", "-l", lang],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", creationflags=_NOWIN, timeout=300)
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f"Tesseract hiba: {e}")
    if r.returncode != 0:
        # ha a magyar nyelvi adat hiányzik, próbáljuk angollal
        if "hun" in lang and "Failed loading language" in (r.stderr or ""):
            return tesseract_ocr(path, "eng")
        raise RuntimeError("Tesseract hiba: "
                           + (r.stderr or "ismeretlen")[:160])
    return (r.stdout or "").strip()


def ocr(path: str, engine: str = "ai") -> str:
    if engine == "tesseract":
        return tesseract_ocr(path)
    return ai_ocr(path)
