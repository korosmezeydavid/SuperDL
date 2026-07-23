"""Hangoskönyv-építő: a könyv szövegét a választott TTS-motorral MP3-zá
alakítja, fix hangos bevezetővel és záró jogi nyilatkozattal.

Folyamat: a szöveget a motor karakterkorlátja szerint darabolja, minden
darabot felolvastat, az eredményt egységes MP3-ra normalizálja (ffmpeg),
majd összefűzi: bevezető + tartalom + nyilatkozat. A végeredmény egyetlen
MP3, vagy a felhasználó által megadott percenként darabolva.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path

from . import tts
from .ffmpeg import ensure_ffmpeg, find_ffmpeg

# A program által beállított, FIX bevezető és záró szöveg (nem szerkeszthető).
INTRO = ("{title}. Ezt a hangoskönyvet a SuperDL program készítette, "
         "kizárólag egyéni, személyes használatra.")
OUTRO = ("A hangoskönyv vége. Ezt a felvételt a SuperDL program olvasta fel, "
         "kizárólag egyéni célú hallgatásra. A felvétel terjesztése vagy "
         "megosztása a szerző engedélye nélkül tilos.")

DEFAULT_CHUNK = 6000

# Önálló oldalszám-sor (csak számjegy, körülötte legföljebb pont/kötőjel/szóköz),
# pl. „42", „- 42 -", „. 42 .". A betűt tartalmazó sorokat NEM érinti.
_PAGE_NUM = re.compile(r"^[\s.\-—–]*\d{1,4}[\s.\-—–]*$")


def clean_for_speech(text: str) -> str:
    """A könyvszöveget FELOLVASÁSRA/hangoskönyvre tisztítja: a „felesleges"
    sorokat és sortöréseket távolítja el, a tartalmat megtartva.

    Mit csinál (saját, konzervatív logika – SZÁNDÉKOSAN nem szűr betűket, az
    nyelvfüggő és kockázatos; csak a SOR-SZERKEZETET rendezi):
      1) a sorvégi elválasztójellel kettévágott szót összevonja
         („elválasz-\\ntás" → „elválasztás"; a lágy kötőjelet, U+00AD, is);
      2) bekezdésekre bont (üres sor = bekezdéshatár, ezt MEGTARTJA), és a
         bekezdésen BELÜLI kemény sortöréseket szóközzé alakítja – a TTS az
         írásjelekből szünetel, nem a sortörésekből, így a felolvasás folyamatos;
      3) kidobja a TARTALOM NÉLKÜLI sorokat: üres sorok és önálló oldalszámok.
    Üres bemenetre üreset ad."""
    if not text:
        return text
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    # 1) sorvégi elválasztás összevonása (rendes és lágy kötőjel is)
    t = re.sub(r"(\w)[-­]\n(\w)", r"\1\2", t)
    # 2-3) bekezdésenként: oldalszám/üres sorok ki, a többit egy sorba olvasztjuk
    out = []
    for para in re.split(r"\n[ \t]*\n", t):
        lines = []
        for ln in para.split("\n"):
            s = ln.strip()
            if not s or _PAGE_NUM.match(s):
                continue
            lines.append(s)
        joined = re.sub(r"[ \t]+", " ", " ".join(lines)).strip()
        if joined:
            out.append(joined)
    return "\n\n".join(out)


def clean_book(book):
    """Egy `booktext.Book` minden szakaszát felolvasásra tisztítja (a Book
    típusától függetlenül, klónozással – nincs import-kör)."""
    import copy
    sections = [clean_for_speech(s) for s in book.sections]
    sections = [s for s in sections if s.strip()] or [""]
    nb = copy.copy(book)
    nb.sections = sections
    return nb


_CLAUSE_SEPS = (", ", "; ", ": ", " – ", " — ", ") ")


def _byte_window(s: str, limit: int) -> int:
    """Hány KARAKTER fér bele `limit` UTF-8 BÁJTBA? (bájt-alapú daraboláshoz)"""
    if len(s.encode("utf-8")) <= limit:
        return len(s)
    lo, hi = 0, len(s)
    while lo < hi:                       # bináris keresés a leghosszabb prefixre
        mid = (lo + hi + 1) // 2
        if len(s[:mid].encode("utf-8")) <= limit:
            lo = mid
        else:
            hi = mid - 1
    return max(1, lo)


def _wrap_long(s: str, limit: int, by_bytes: bool = False) -> list[str]:
    """Egy `limit`-nél HOSSZABB szöveg feldarabolása legfeljebb `limit` hosszú
    részekre, LEHETŐLEG TAGMONDAT-HATÁRON (vessző, pontosvessző, kettőspont,
    gondolatjel), különben szóhatáron – SEMMIT EL NEM DOBVA. Így a darabok közti
    (elkerülhetetlen) rövid szünet természetes helyre, a vesszőhöz esik, nem a
    mondat közepére. A limitnél is hosszabb egyetlen szót (pl. URL) keményen vágja.
    Ez váltja a régi, HIBÁS `sent[:limit]` csonkolást (ami a mondatvégeket
    elhagyta), a szaggatottság elkerülésével."""
    out: list[str] = []
    s = s.strip()
    size = _utf8_len if by_bytes else len
    while size(s) > limit:
        # bájt-módban a limit BÁJT, ezért a karakter-ablakot ki kell számolni
        win = _byte_window(s, limit) if by_bytes else limit
        window = s[:win]
        cut = -1
        for sep in _CLAUSE_SEPS:                 # utolsó tagmondat-határ a limiten belül
            p = window.rfind(sep)
            if p >= 0:
                cut = max(cut, p + len(sep.rstrip()))   # a vessző/jel UTÁN vágunk
        if cut < win // 2:                       # nincs jó tagmondat-határ a 2. felében
            sp = window.rfind(" ")
            cut = sp if sp > 0 else win          # szóhatár, végső esetben kemény vágás
        out.append(s[:cut].strip())
        s = s[cut:].strip()
    if s:
        out.append(s)
    return out


def _utf8_len(s: str) -> int:
    return len(s.encode("utf-8"))


def chunk_text(text: str, limit: int, by_bytes: bool = False) -> list[str]:
    """A szöveget legfeljebb `limit` méretű darabokra bontja, lehetőleg
    bekezdés- és mondathatáron. A limitnél hosszabb mondatot TÖBB darabra bontja
    (szóhatáron) – SOHA nem csonkolja, hogy a felolvasás teljes legyen.

    `by_bytes=True` esetén a méret UTF-8 BÁJTBAN értendő. A Google Cloud TTS
    korlátja bájtalapú, a magyar ékezetek pedig 2 bájtosak – karakterben mérve
    egy „5000 alatti” darab is 400/413 hibát adhatna. [Herman Tibi AB-P1-10]"""
    limit = limit if limit and limit > 0 else DEFAULT_CHUNK
    size = _utf8_len if by_bytes else len
    chunks: list[str] = []
    cur = ""

    def flush():
        nonlocal cur
        if cur.strip():
            chunks.append(cur.strip())
        cur = ""

    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        if size(cur) + size(para) + 1 <= limit:
            cur = (cur + "\n" + para) if cur else para
        elif size(para) <= limit:
            flush()
            cur = para
        else:
            flush()
            for sent in re.split(r"(?<=[.!?])\s+", para):
                if size(cur) + size(sent) + 1 <= limit:
                    cur = (cur + " " + sent) if cur else sent
                elif size(sent) <= limit:
                    flush()
                    cur = sent
                else:
                    # a limitnél HOSSZABB mondat: több darabra bontjuk, SEMMIT
                    # el nem dobva (a régi sent[:limit] itt vágta le a végét)
                    flush()
                    pieces = _wrap_long(sent, limit, by_bytes)
                    chunks.extend(pieces[:-1])
                    cur = pieces[-1] if pieces else ""
    flush()
    return chunks


def _ffmpeg_exe(progress=None) -> str:
    p = find_ffmpeg()
    if not p:
        d = ensure_ffmpeg(progress)
        p = find_ffmpeg() if d else None
    if not p:
        raise RuntimeError("Az ffmpeg nem érhető el.")
    if p.lower().endswith("ffmpeg.exe"):
        return p
    return os.path.join(p, "ffmpeg.exe")


def build(book, engine_key, voice_id, out_path, *, pitch=0, rate=0,
          api_key="", split_minutes=0, progress=None) -> list[str]:
    """Elkészíti a hangoskönyvet. Visszaadja a létrejött fájl(ok) listáját.
    `progress(kész, összes, állapot)` hívható a folyamatjelzéshez."""
    eng = tts.ENGINES[engine_key]
    ff = _ffmpeg_exe()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    # Ha a motor BÁJT-alapú korlátot deklarál (Google Cloud), akkor UTF-8
    # bájtban darabolunk – különben a magyar ékezetes szöveg túllépné a limitet.
    _blimit = int(getattr(eng, "byte_limit", 0) or 0)
    parts = ([INTRO.format(title=book.title)]
             + chunk_text(book.text, _blimit or eng.char_limit,
                          by_bytes=bool(_blimit))
             + [OUTRO])
    total = len(parts)
    work = Path(tempfile.mkdtemp(prefix="sdl_book_"))
    norm_files: list[Path] = []
    try:
        for i, text in enumerate(parts):
            if progress:
                progress(i, total, "felolvasás")
            raw = eng.synth(text, voice_id, str(work / f"p{i:04d}"),
                            pitch=pitch, rate=rate, api_key=api_key)
            norm = work / f"n{i:04d}.mp3"
            subprocess.run(
                [ff, "-y", "-i", raw, "-ar", "44100", "-ac", "2",
                 "-c:a", "libmp3lame", "-qscale:a", "4", str(norm),
                 "-loglevel", "quiet"], stdin=subprocess.DEVNULL,
                creationflags=flags, check=True)
            norm_files.append(norm)
            try:
                os.remove(raw)
            except OSError:
                pass

        if progress:
            progress(total, total, "összefűzés")
        listfile = work / "list.txt"
        listfile.write_text(
            "".join(f"file '{n.as_posix()}'\n" for n in norm_files),
            encoding="utf-8")

        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if split_minutes and split_minutes > 0:
            pattern = str(out.with_name(out.stem + "_%03d" + out.suffix))
            subprocess.run(
                [ff, "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
                 "-f", "segment", "-segment_time", str(int(split_minutes * 60)),
                 "-c", "copy", pattern, "-loglevel", "quiet"],
                stdin=subprocess.DEVNULL, creationflags=flags, check=True)
            import glob
            results = sorted(glob.glob(
                str(out.with_name(out.stem + "_*" + out.suffix))))
        else:
            subprocess.run(
                [ff, "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
                 "-c", "copy", str(out), "-loglevel", "quiet"],
                stdin=subprocess.DEVNULL, creationflags=flags, check=True)
            results = [str(out)]
        if progress:
            progress(total, total, "kész")
        return results
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)
