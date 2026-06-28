"""Internetes TV (IPTV) – akadálymentes, KIZÁRÓLAG LEGÁLIS forrásokhoz.

A felhasználó a SAJÁT, jogtiszta hozzáférését hozza:
  • m3u / m3u8 lejátszási lista (fájlból vagy URL-ből), vagy
  • hitelesítős IPTV (Xtream Codes: cím + felhasználónév + jelszó),
és/vagy ingyenes, nyílt közszolgálati streamek.

A modul a NYÍLT protokollokat teszi akadálymentessé (csatornalista, EPG/műsorújság,
lejátszás, felvétel). NEM kerül meg DRM-et, és NEM tartalmaz semmilyen
csatornalistát – a tartalom mindig a felhasználó saját, legális forrásából jön.
"""

import datetime as _dt
import json
import os
import re
import subprocess
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from superdl import ffmpeg as ffmpeg_mod   # megosztott ffmpeg a Core-ból

UA = {"User-Agent": "SuperDL-IPTV"}
_NOWIN = 0x08000000 if os.name == "nt" else 0


def _ff() -> str | None:
    f = ffmpeg_mod.find_ffmpeg()
    if not f:
        d = ffmpeg_mod.ensure_ffmpeg()
        f = ffmpeg_mod.find_ffmpeg() if d else None
    return f


def _ffprobe() -> str | None:
    f = _ff()
    return str(Path(f).with_name("ffprobe.exe")) if f else None


@dataclass
class Channel:
    name: str
    url: str
    group: str = ""
    tvg_id: str = ""
    logo: str = ""

    def to_record(self) -> dict:
        return {"name": self.name, "url": self.url, "group": self.group,
                "tvg_id": self.tvg_id, "logo": self.logo}

    @classmethod
    def from_record(cls, r: dict) -> "Channel":
        return cls(name=r.get("name", ""), url=r.get("url", ""),
                   group=r.get("group", ""), tvg_id=r.get("tvg_id", ""),
                   logo=r.get("logo", ""))


@dataclass
class Programme:
    start: _dt.datetime
    stop: _dt.datetime
    title: str
    desc: str = ""


# ---- m3u / m3u8 betöltés és értelmezés --------------------------------

_ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def parse_m3u(text: str) -> list[Channel]:
    """Egy #EXTM3U lista értelmezése csatornákká (tvg-id, group-title, logó)."""
    channels: list[Channel] = []
    name = group = tvg = logo = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.upper().startswith("#EXTINF"):
            attrs = dict(_ATTR.findall(line))
            tvg = attrs.get("tvg-id", "")
            logo = attrs.get("tvg-logo", "")
            group = attrs.get("group-title", "")
            name = line.rsplit(",", 1)[-1].strip() if "," in line else \
                attrs.get("tvg-name", "")
        elif line.startswith("#"):
            continue
        else:
            if name or line:
                channels.append(Channel(name=name or line, url=line,
                                        group=group, tvg_id=tvg, logo=logo))
            name = group = tvg = logo = ""
    return channels


def _fetch(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def load_playlist(source: str) -> list[Channel]:
    """m3u/m3u8 betöltése fájlból VAGY URL-ből → csatornalista."""
    if re.match(r"^https?://", source, re.I):
        text = _fetch(source)
    else:
        text = Path(source).read_text(encoding="utf-8", errors="replace")
    return parse_m3u(text)


# ---- Xtream Codes (hitelesítős IPTV) ----------------------------------

def _xtream_base(host: str) -> str:
    host = host.strip()
    if not re.match(r"^https?://", host, re.I):
        host = "http://" + host
    return host.rstrip("/")


def xtream_m3u_url(host: str, user: str, pwd: str) -> str:
    """A teljes csatornalista m3u-ként (a szerver állítja elő a kész URL-ekkel)."""
    return (f"{_xtream_base(host)}/get.php?username={user}&password={pwd}"
            "&type=m3u_plus&output=ts")


def xtream_epg_url(host: str, user: str, pwd: str) -> str:
    """A teljes EPG (műsorújság) XMLTV formátumban."""
    return f"{_xtream_base(host)}/xmltv.php?username={user}&password={pwd}"


def xtream_channels(host: str, user: str, pwd: str) -> list[Channel]:
    """Bejelentkezés egy LEGÁLIS Xtream-szolgáltatóba → csatornalista. A szerver
    által generált m3u-t kérjük le (kész stream-URL-ekkel) és értelmezzük."""
    return load_playlist(xtream_m3u_url(host, user, pwd))


# ---- EPG (XMLTV műsorújság) -------------------------------------------

def _xmltv_time(s: str) -> _dt.datetime | None:
    """XMLTV időbélyeg: '20260624080000 +0100' → helyi idő (naiv)."""
    m = re.match(r"\s*(\d{14})(?:\s*([+-]\d{4}))?", s or "")
    if not m:
        return None
    try:
        t = _dt.datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    if m.group(2):
        sign = 1 if m.group(2)[0] == "+" else -1
        off = _dt.timedelta(hours=int(m.group(2)[1:3]),
                            minutes=int(m.group(2)[3:5])) * sign
        t = (t - off) + _local_offset()      # a helyi időre igazítjuk
    return t


def _local_offset() -> _dt.timedelta:
    now = _dt.datetime.now()
    return now - _dt.datetime.utcnow()


class EPG:
    """Egy XMLTV-műsorújság: csatornánként (tvg-id) a műsorok időrendben."""

    def __init__(self):
        self.by_channel: dict[str, list[Programme]] = {}

    @classmethod
    def parse(cls, xml_text: str) -> "EPG":
        import xml.etree.ElementTree as ET
        epg = cls()
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return epg
        for prog in root.findall("programme"):
            ch = prog.get("channel", "")
            start = _xmltv_time(prog.get("start", ""))
            stop = _xmltv_time(prog.get("stop", "")) or (
                start + _dt.timedelta(hours=1) if start else None)
            if not (ch and start and stop):
                continue
            title_el = prog.find("title")
            desc_el = prog.find("desc")
            epg.by_channel.setdefault(ch, []).append(Programme(
                start=start, stop=stop,
                title=(title_el.text or "").strip() if title_el is not None
                else "",
                desc=(desc_el.text or "").strip() if desc_el is not None
                else ""))
        for lst in epg.by_channel.values():
            lst.sort(key=lambda p: p.start)
        return epg

    @classmethod
    def load(cls, source: str) -> "EPG":
        if re.match(r"^https?://", source, re.I):
            return cls.parse(_fetch(source, timeout=120))
        return cls.parse(Path(source).read_text(encoding="utf-8",
                                                errors="replace"))

    def now_next(self, tvg_id: str, when: _dt.datetime | None = None):
        """(épp futó műsor, következő műsor) az adott csatornán, vagy (None, None)."""
        when = when or _dt.datetime.now()
        progs = self.by_channel.get(tvg_id) or []
        cur = nxt = None
        for i, pr in enumerate(progs):
            if pr.start <= when < pr.stop:
                cur = pr
                nxt = progs[i + 1] if i + 1 < len(progs) else None
                break
            if pr.start > when:
                nxt = pr
                break
        return cur, nxt

    def schedule(self, tvg_id: str, when: _dt.datetime | None = None,
                 count: int = 12) -> list[Programme]:
        """Az adott csatorna következő `count` műsora a megadott időtől."""
        when = when or _dt.datetime.now()
        progs = self.by_channel.get(tvg_id) or []
        return [p for p in progs if p.stop > when][:count]


def groups(channels: list[Channel]) -> list[str]:
    """A csatornák csoportjai (kategóriái), ábécé-sorrendben, az „összes"-sel az élen."""
    gs = sorted({c.group for c in channels if c.group})
    return ["Összes csatorna"] + gs


# ---- felvétel / időeltolás (D) ----------------------------------------

def start_recording(url: str, out_path: str):
    """A LEGÁLIS, nyílt stream rögzítése fájlba (átkódolás nélkül, -c copy). A
    .ts konténer abbahagyásra is robusztus. Visszaad: a futó folyamat."""
    ff = _ff()
    if not ff:
        raise RuntimeError("Az ffmpeg nem érhető el a felvételhez.")
    cmd = [ff, "-y", "-i", url, "-c", "copy", str(out_path)]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, creationflags=_NOWIN)


def stop_recording(proc) -> None:
    """A felvétel rendezett leállítása (az ffmpeg-nek 'q'-t küldünk, hogy a
    fájlt szabályosan lezárja)."""
    if not proc:
        return
    try:
        proc.stdin.write(b"q")
        proc.stdin.flush()
        proc.wait(timeout=8)
    except Exception:
        try:
            proc.terminate()
        except OSError:
            pass


# ---- hang- és feliratsávok (E) ----------------------------------------

_AD_HINT = re.compile(r"(audio.?descr|descri|narrat|narr[aá]tor|hangal[aá]"
                      r"mond|vak|\bad\b|visual)", re.I)
_TEXT_SUB = {"subrip", "srt", "webvtt", "vtt", "ass", "ssa", "mov_text",
             "text", "eia_608", "subviewer"}


def _probe_streams(url: str, kind: str) -> list[dict]:
    pb = _ffprobe()
    if not pb:
        return []
    try:
        r = subprocess.run(
            [pb, "-v", "error", "-select_streams", kind, "-show_entries",
             "stream=index,codec_name:stream_tags=language,title",
             "-of", "json", url], capture_output=True, text=True,
            encoding="utf-8", errors="replace", creationflags=_NOWIN,
            timeout=30)
        data = json.loads(r.stdout or "{}")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []
    return data.get("streams", []) or []


def audio_tracks(url: str) -> list[dict]:
    """A stream hangsávjai: [{type_index, label, is_ad}]. A hangalámondás-sávot
    (audio description) megjelöljük."""
    out = []
    for i, s in enumerate(_probe_streams(url, "a")):
        tags = s.get("tags", {}) or {}
        lang = tags.get("language", "")
        title = tags.get("title", "")
        label = " ".join(x for x in (lang, title) if x) or f"{i + 1}. hangsáv"
        is_ad = bool(_AD_HINT.search(f"{lang} {title}"))
        if is_ad:
            label += "  ★ hangalámondás"
        out.append({"index": i, "label": label, "is_ad": is_ad})
    return out


def subtitle_tracks(url: str) -> list[dict]:
    """A stream feliratsávjai: [{type_index, label, is_text}]. A SZÖVEGES
    feliratokat olvashatjuk fel; a képi (DVB/PGS) feliratokhoz OCR kellene."""
    out = []
    for i, s in enumerate(_probe_streams(url, "s")):
        tags = s.get("tags", {}) or {}
        lang = tags.get("language", "")
        title = tags.get("title", "")
        codec = (s.get("codec_name", "") or "").lower()
        label = " ".join(x for x in (lang, title) if x) or f"{i + 1}. felirat"
        is_text = codec in _TEXT_SUB
        if not is_text:
            label += "  (képi – OCR kellene)"
        out.append({"index": i, "label": label, "is_text": is_text})
    return out


class SubtitleReader:
    """Élő felirat-felolvasás SZÖVEGES feliratsávból: az ffmpeg a feliratot
    SRT-ként a kimenetre folyatja, mi pedig minden új feliratot felolvastatunk.
    (Képi feliratokhoz OCR kellene – az egy későbbi iteráció.)"""

    def __init__(self, url: str, sub_index: int, speak):
        self.url = url
        self.idx = int(sub_index)
        self.speak = speak                  # speak(szöveg) – a felolvasó
        self._proc = None
        self._stop = threading.Event()

    def start(self) -> bool:
        ff = _ff()
        if not ff:
            return False
        cmd = [ff, "-nostdin", "-loglevel", "quiet", "-i", self.url,
               "-map", f"0:s:{self.idx}", "-f", "srt", "-"]
        try:
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                          creationflags=_NOWIN)
        except OSError:
            return False
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _run(self):
        buf = []
        for raw in self._proc.stdout:
            if self._stop.is_set():
                break
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if line.strip() == "":
                text = " ".join(x for x in buf
                                if x and not x.isdigit() and "-->" not in x)
                text = text.strip()
                if text and not self._stop.is_set():
                    try:
                        self.speak(text)
                    except Exception:
                        pass
                buf = []
            else:
                buf.append(line)

    def stop(self):
        self._stop.set()
        if self._proc:
            try:
                self._proc.terminate()
            except OSError:
                pass
            self._proc = None
