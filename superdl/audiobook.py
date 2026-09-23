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
class AudiobookCancelled(RuntimeError):
    """A felhasználó megszakította a hangoskönyv készítését. [AB-P0-02]"""


INTRO = ("{title}. Ezt a hangoskönyvet a SuperDL program készítette, "
         "kizárólag egyéni, személyes használatra.")
OUTRO = ("A hangoskönyv végéhez értünk. Ezt a felvételt a SuperDL program "
         "olvasta fel, "
         "kizárólag egyéni célú hallgatásra. A felvétel terjesztése vagy "
         "megosztása a szerző engedélye nélkül tilos.")

DEFAULT_CHUNK = 6000

# Önálló oldalszám-sor (csak számjegy, körülötte legföljebb pont/kötőjel/szóköz),
# pl. „42", „- 42 -", „. 42 .". A betűt tartalmazó sorokat NEM érinti.
_PAGE_NUM = re.compile(r"^[\s.\-—–]*\d{1,4}[\s.\-—–]*$")


def mondhato(szoveg: str) -> bool:
    """Van-e a darabban KIMONDHATÓ jel (betű vagy számjegy)?

    ⚠️ MÉRVE 2026-09-22, Dr. Kiss István hangoskönyve nyomán: az Edge-TTS
    `NoAudioReceived`-et dob arra a darabra, amiben csak írásjel van —

        „.”          -> NoAudioReceived
        „—————”      -> NoAudioReceived
        „* * *”      -> NoAudioReceived
        „1 2 3”      -> OK
        „A”          -> OK

    Regényekben a jelenetválasztó `* * *` és a hosszú gondolatjel-sor
    teljesen szokásos. Egyetlen ilyen darab eddig az EGÉSZ, akár több órás
    hangoskönyv-készítést elbuktatta, egy érthetetlen angol üzenettel."""
    return any(ch.isalpha() or ch.isdigit() for ch in (szoveg or ""))


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
    from . import fejezet as _fej
    out = []

    def _zar(lines):
        joined = re.sub(r"[ \t]+", " ", " ".join(lines)).strip()
        if joined:
            out.append(joined)

    for para in re.split(r"\n[ \t]*\n", t):
        lines = []
        for ln in para.split("\n"):
            s = ln.strip()
            if not s or _PAGE_NUM.match(s):
                continue
            # ⚠️ A FEJEZETJELÖLŐ MARADJON SAJÁT SORBAN. Ez a tisztító a
            # bekezdésen belüli sortöréseket szóközzé olvasztja – ami a
            # felolvasásnak jó, de a jelölőt BEOLVASZTANÁ a szomszédos
            # mondatba, és a fejezetenkénti darabolás NÉMÁN elromlana:
            # a hangoskönyv egyben maradna, és a felhasználó csak a kész,
            # órákig készülő fájlon venné észre.
            if _fej.jelolo_e(s):
                _zar(lines)
                lines = []
                out.append(s)
                continue
            lines.append(s)
        _zar(lines)
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


def fejezet_szamlal(book) -> int:
    """Hány fejezetjelölő van a könyvben? 0 = nincs fejezetenkénti darabolás.

    A hívó felület ebből tudja, hogy felajánlhatja-e a fejezetenkénti
    darabolást – felajánlani olyat, ami nem megy, rosszabb a hallgatásnál.
    """
    from . import fejezet
    return fejezet.szamlal(getattr(book, "text", "") or "")


def _ffmpeg(parancs: list, flags: int, mit: str) -> None:
    """ffmpeg-hívás ÉRTELMES hibaüzenettel.

    ⚠️ MIÉRT KELLETT. Eddig minden hívás `-loglevel quiet` + `check=True`
    volt. Ha az ffmpeg elhasalt, a felhasználó ezt kapta:

        Command '[...]' returned non-zero exit status 1.

    Ebből se ő, se én nem tudtam meg semmit — pedig az ffmpeg PONTOSAN
    megmondja, mi a baja (nincs hely, túl hosszú az út, rossz a bemenet),
    csak épp elnémítottuk. Dr. Kiss István 2026-09-16-i jelentése ezért
    nem volt megfejthető: „hibaüzenettel megszakadt", és kész.

    Mostantól `-loglevel error`: a szokásos fecsegés marad néma, de a
    HIBA megszólal, és bekerül a kivétel szövegébe — tehát a képernyőre
    és a naplóba is."""
    p = subprocess.run(parancs, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       creationflags=flags)
    if p.returncode == 0:
        return
    reszlet = (p.stderr or b"").decode("utf-8", "replace").strip()
    # az ffmpeg sokszor több sort ír; az UTOLSÓ néhány a lényeg
    sorok = [s for s in reszlet.splitlines() if s.strip()][-3:]
    raise RuntimeError(
        "%s nem sikerült (ffmpeg, kód %s).%s"
        % (mit, p.returncode,
           ("\n" + "\n".join(sorok)) if sorok else
           " Az ffmpeg nem mondta meg, miért."))


def _fejezet_cim_fajlnev(cim: str, sorszam: int) -> str:
    """A fejezetcímből biztonságos fájlnév-részlet."""
    tiszta = re.sub(r'[\\/:*?"<>|]+', " ", cim or "").strip()
    tiszta = re.sub(r"\s+", " ", tiszta)[:60].strip()
    return "%02d%s" % (sorszam, (" " + tiszta) if tiszta else "")


def build(book, engine_key, voice_id, out_path, *, pitch=0, rate=0,
          api_key="", split_minutes=0, fejezetenkent=False,
          progress=None, cancel=None) -> list[str]:
    """Elkészíti a hangoskönyvet. Visszaadja a létrejött fájl(ok) listáját.
    `progress(kész, összes, állapot)` hívható a folyamatjelzéshez.

    `fejezetenkent=True`: percek helyett a FEJEZETJELÖLŐK mentén darabol
    (`superdl/fejezet.py`; a Super Editben a Ctrl+Shift+J szúrja be őket).
    Ilyenkor a `split_minutes` figyelmen kívül marad. Ha nincs jelölő a
    szövegben, egyben marad – NEM esünk vissza némán percekre.

    `cancel`: opcionális threading.Event – ha beállítják, a munka a LEGKÖZELEBBI
    biztonságos ponton MEGSZAKAD (`AudiobookCancelled`), és a félkész fájlok
    törlődnek. Enélkül egy többórás, felhő-TTS-nél FIZETŐS munkát nem lehetett
    leállítani, és ablakbezárás után is tovább futott. [Herman Tibi AB-P0-02]"""
    def _megszakitva() -> bool:
        return bool(cancel is not None and cancel.is_set())

    def _ellenoriz():
        if _megszakitva():
            raise AudiobookCancelled(
                "A hangoskönyv készítését megszakítottad.")

    # Ha eleve megszakították, semmilyen előkészületet ne végezzünk (ffmpeg-
    # keresés, motor-betöltés) – azonnal, dolgavégezetlenül lépjünk ki.
    _ellenoriz()
    eng = tts.ENGINES[engine_key]
    ff = _ffmpeg_exe()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    # Ha a motor BÁJT-alapú korlátot deklarál (Google Cloud), akkor UTF-8
    # bájtban darabolunk – különben a magyar ékezetes szöveg túllépné a limitet.
    _blimit = int(getattr(eng, "byte_limit", 0) or 0)
    _limit = _blimit or eng.char_limit

    # FEJEZETENKÉNTI DARABOLÁS: a szöveget előbb fejezetekre bontjuk, és
    # megjegyezzük, melyik hangdarab melyik fejezethez tartozik. Így a végén
    # fejezetenként fűzünk össze — nem időre vágunk, ami mondat közepén is
    # elvághatná. A jelölő-sorok maguk NEM kerülnek a felolvasandó szövegbe.
    fej_cimek: list[str] = []
    part_fej: list[int] = []
    if fejezetenkent:
        from . import fejezet as _fej
        fejezetek = _fej.fejezetek(book.text)
        if len(fejezetek) > 1:
            fej_cimek = [c for c, _t in fejezetek]
            parts = [INTRO.format(title=book.title)]
            part_fej = [0]
            for _i, (_cim, _szoveg) in enumerate(fejezetek):
                _darabok = chunk_text(_szoveg, _limit, by_bytes=bool(_blimit))
                parts.extend(_darabok)
                part_fej.extend([_i] * len(_darabok))
            parts.append(OUTRO)
            part_fej.append(len(fejezetek) - 1)
        else:
            fejezetenkent = False        # nincs mit fejezetenként vágni
    if not fejezetenkent:
        parts = ([INTRO.format(title=book.title)]
                 + chunk_text(book.text, _limit, by_bytes=bool(_blimit))
                 + [OUTRO])

    # ⚠️ A KIMONDHATATLAN DARABOK KIHAGYÁSA. Egy csupa írásjelből álló darab
    # („* * *", „—————") a beszédmotortól NEM kap hangot, és eddig az EGÉSZ
    # hangoskönyvet elbuktatta a legvégén. Nincs mit felolvasni rajtuk, tehát
    # kihagyjuk őket — a fejezet-hozzárendelést VELÜK EGYÜTT, különben a
    # fejezetenkénti összefűzés csúszna el. [Dr. Kiss István, 2026-09-22]
    if part_fej:
        _p, _f = [], []
        for _t, _fi in zip(parts, part_fej):
            if mondhato(_t):
                _p.append(_t)
                _f.append(_fi)
        parts, part_fej = _p, _f
    else:
        parts = [t for t in parts if mondhato(t)]
    if not parts:
        raise RuntimeError(
            "Ebben a szövegben nincs felolvasható tartalom – csak írásjelek "
            "vagy üres sorok. Ellenőrizd a betöltött könyvet.")
    total = len(parts)
    work = Path(tempfile.mkdtemp(prefix="sdl_book_"))
    norm_files: list[Path] = []
    stage_dirs: list[Path] = []      # a cél melletti köztes mappák (takarításhoz)
    try:
        for i, text in enumerate(parts):
            # minden darab ELŐTT: megszakították-e? Így egy felhő-TTS-nél
            # fizetős munka nem megy tovább feleslegesen. [AB-P0-02]
            _ellenoriz()
            if progress:
                progress(i, total, "felolvasás")
            try:
                raw = eng.synth(text, voice_id, str(work / f"p{i:04d}"),
                                pitch=pitch, rate=rate, api_key=api_key)
            except Exception as _ex:
                # ⚠️ A beszédmotor angol kivétele a felhasználónak semmit nem
                # mond. Megmondjuk, HÁNYADIK darabnál és MILYEN szövegnél
                # akadt el – abból a következő jelentésben meg lehet találni.
                _eleje = " ".join((text or "").split())[:60]
                raise RuntimeError(
                    "A felolvasás a(z) %d. szövegdarabnál akadt el (összesen "
                    "%d). A darab eleje: „%s…”. A beszédmotor üzenete: %s"
                    % (i + 1, total, _eleje, _ex)) from _ex
            norm = work / f"n{i:04d}.mp3"
            _ffmpeg([ff, "-y", "-i", raw, "-ar", "44100", "-ac", "2",
                     "-c:a", "libmp3lame", "-qscale:a", "4", str(norm),
                     "-loglevel", "error"],
                    flags, "A(z) %d. hangdarab átalakítása" % (i + 1))
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

        _ellenoriz()
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        # A VÉGLEGES fájlokat csak a teljes siker + ellenőrzés UTÁN hozzuk létre.
        # Korábban az ffmpeg `-y`-nal KÖZVETLENÜL a végleges névre írt, így egy
        # megszakadt munka a MEGLÉVŐ hangoskönyvet csonkára cserélte, és a régi
        # darabolt sávok is bent maradhattak. [Herman Tibi AB-P0-03]
        # A köztes mappa a CÉL MELLETT van (nem a temp-ben): csak azonos köteten
        # atomikus az `os.replace`. A finally-ág mindenképp eltakarítja.
        import uuid as _uuid
        stage = out.parent / f".superdl_kesz_{_uuid.uuid4().hex[:8]}"
        stage.mkdir(parents=True, exist_ok=True)
        stage_dirs.append(stage)
        if fejezetenkent and fej_cimek:
            # FEJEZETENKÉNT: minden fejezethez SAJÁT listafájl és saját
            # összefűzés. Nem időre vágunk, tehát a vágás sosem esik mondat
            # közepére, és a fájlnévben ott a fejezet címe.
            keszek = []
            for _i, _cim in enumerate(fej_cimek):
                _sajat = [n for n, _f in zip(norm_files, part_fej) if _f == _i]
                if not _sajat:
                    continue
                _lista = work / ("fej%03d.txt" % _i)
                _lista.write_text(
                    "".join(f"file '{n.as_posix()}'\n" for n in _sajat),
                    encoding="utf-8")
                _nev = "%s_%s%s" % (out.stem,
                                    _fejezet_cim_fajlnev(_cim, _i + 1),
                                    out.suffix)
                _cel = stage / _nev
                _ffmpeg([ff, "-y", "-f", "concat", "-safe", "0",
                         "-i", str(_lista), "-c", "copy", str(_cel),
                         "-loglevel", "error"],
                        flags, "A(z) „%s” fejezet összefűzése" % (_cim or _i))
                keszek.append(_cel)
        elif split_minutes and split_minutes > 0:
            pattern = str(stage / (out.stem + "_%03d" + out.suffix))
            _ffmpeg([ff, "-y", "-f", "concat", "-safe", "0",
                     "-i", str(listfile), "-f", "segment",
                     "-segment_time", str(int(split_minutes * 60)),
                     "-c", "copy", pattern, "-loglevel", "error"],
                    flags, "A percenkénti darabolás")
            keszek = sorted(stage.glob(out.stem + "_*" + out.suffix))
        else:
            egy = stage / out.name
            _ffmpeg([ff, "-y", "-f", "concat", "-safe", "0",
                     "-i", str(listfile), "-c", "copy", str(egy),
                     "-loglevel", "error"],
                    flags, "A hangoskönyv összefűzése")
            keszek = [egy]

        # KIMENET-ELLENŐRZÉS: eddig a puszta visszatérési kód számított sikernek,
        # így nulla hosszú, csonka vagy hiányzó sáv is „késznek" látszott.
        # [Herman Tibi AB-P0-04]
        if not keszek:
            raise RuntimeError("A hangoskönyv nem jött létre (nincs kimeneti "
                               "fájl). Próbáld újra.")
        for f in keszek:
            if not f.is_file() or f.stat().st_size < 1024:
                raise RuntimeError(
                    f"A(z) „{f.name}” sáv üres vagy csonka, ezért NEM mentem el "
                    "a hangoskönyvet. A korábbi fájljaid érintetlenek.")

        _ellenoriz()
        if progress:
            progress(total, total, "mentés")
        results = []
        for f in keszek:
            cel = out.with_name(f.name)
            os.replace(str(f), str(cel))     # atomikus, azonos köteten
            results.append(str(cel))
        if progress:
            progress(total, total, "kész")
        return results
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)
        for d in stage_dirs:         # megszakításnál/hibánál sem marad szemét
            shutil.rmtree(d, ignore_errors=True)
