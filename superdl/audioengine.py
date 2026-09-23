"""Streaming hangmotor: az ffmpeg dekódolja a forrást (élő stream vagy
fájl), a sounddevice pedig megszólaltatja. Sample-szintű hangerő- és
szünet-vezérlés. Ezzel az élő internetes rádió is megbízhatóan szól, amit a
beépített wx.media lejátszó nem tudott.

A hangerőt menet közben, a hangmintákra alkalmazzuk (numpy), így nincs
szükség a stream újraindítására.
"""

import os
import re
import subprocess
import threading
import time

from . import proc as procutil
from .ffmpeg import ensure_ffmpeg, find_ffmpeg

RATE = 44100
CHANNELS = 2

# a „hagyd a rendszerre" választás azonosítója a beállításokban
RENDSZER_ESZKOZ = ""


def eszkoz_nev(nyers: str) -> str:
    """A hangeszköz nevének FELOLVASHATÓ alakja.

    ⚠️ NEM szépészet. A Windows a bluetooth kihangosítókat így nevezi:

        Fejbeszélő (@System32\\drivers\\bthhfenum.sys,#2;%1 Hands-Free%0
        ;(WI-C100))

    Ezt a képernyőolvasó karakterenként mondaná ki – egy ilyen listából
    vakon választani lehetetlen. A lényeg a zárójeles VÉGE: a készülék
    neve. Azt emeljük ki, a többit eldobjuk."""
    n = " ".join((nyers or "").replace("\r", " ").replace("\n", " ").split())
    m = re.search(r";\(([^()]+)\)\)\s*$", n)
    if m:
        return "%s (kihangosító)" % m.group(1).strip()
    m = re.search(r"@System32.*?;\(?([^();]+)\)?\)?\s*$", n)
    if m and m.group(1).strip():
        return "%s (kihangosító)" % m.group(1).strip()
    return n


def eszkozok() -> list:
    """A gép HANGKIMENETEI: [(azonosító, felolvasható név), …].

    Az első elem mindig a rendszer alapértelmezettje. Az azonosító a
    sounddevice eszköz NYERS neve (nem az indexe!), mert az index eszköz
    ki-be dugásakor elcsúszik – a név viszont megmarad. A megjelenített
    név viszont a megtisztított alak.

    ⚠️ MIÉRT KELL (Stolmár Barbi, 2026-09-21): „A zene lejátszóban
    bluetooth fejhallgatóra váltáskor nincs átváltás, továbbra is az
    alapértelmezetten marad." A lejátszó eddig mindig a rendszer
    alapértelmezettjén szólt, és nem is tudott róla, hogy van hová váltani."""
    ki = [(RENDSZER_ESZKOZ, "Rendszer alapértelmezett kimenete")]
    latott = set()
    try:
        import sounddevice as sd
        for e in sd.query_devices():
            if int(e.get("max_output_channels") or 0) <= 0:
                continue
            nyers = (e.get("name") or "").strip()
            if not nyers:
                continue
            szep = eszkoz_nev(nyers)
            # ⚠️ ugyanaz az eszköz több hang-API alatt is megjelenik
            # (MME, DirectSound, WASAPI). Vakon egy háromszorosan
            # felsorolt lista használhatatlan – egyszer soroljuk fel.
            kulcs = szep.lower()
            if kulcs in latott:
                continue
            latott.add(kulcs)
            ki.append((nyers, szep))
    except Exception:
        pass
    return ki


def alapertelmezett_kimenet() -> str:
    """A rendszer JELENLEGI alapértelmezett kimenetének NYERS neve, vagy üres.
    Ebből vesszük észre, ha a felhasználó bluetooth fülesre vált."""
    try:
        import sounddevice as sd
        idx = None
        azon = sd.default.device
        if isinstance(azon, (list, tuple)) and len(azon) > 1:
            idx = azon[1]
        elif isinstance(azon, int):
            idx = azon
        if idx is None or idx < 0:
            # a `sd.default.device` nincs mindig beállítva – a hang-API
            # saját alapértelmezettje viszont igen
            for api in sd.query_hostapis():
                j = api.get("default_output_device", -1)
                if j is not None and j >= 0:
                    idx = j
                    break
        if idx is None or idx < 0:
            return ""
        return (sd.query_devices(idx).get("name") or "").strip()
    except Exception:
        return ""


def _ffmpeg_exe(progress=None) -> str | None:
    p = find_ffmpeg()
    if not p:
        d = ensure_ffmpeg(progress)
        p = find_ffmpeg() if d else None
    if not p:
        return None
    if p.lower().endswith("ffmpeg.exe"):
        return p
    return os.path.join(p, "ffmpeg.exe")


class Player:
    """Egy időben egy forrást játszik. A `on_state(szöveg)` visszahívás az
    állapotváltozásokat jelzi (lejátszás / vége / hiba)."""

    def __init__(self):
        self._proc = None
        self._thread = None
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._volume = 0.7
        self._lock = threading.Lock()
        self.on_state = None
        self.title = ""
        self._played = 0           # eddig megszólaltatott PCM-bájtok száma
        self._url = ""             # az aktuális forrás (a seek-hez)
        self._start_offset = 0.0   # a lejátszás kezdő-időpontja (seek után)
        # LEJÁTSZÁS-GENERÁCIÓ: minden play() új generációt kap; a régi _feed szál
        # a SAJÁT stop_eventjét és generációját figyeli, és csak akkor küld
        # állapotot, ha a generációja még az aktuális. Enélkül a gyors stop+play
        # (pl. seek) után a régi szál a KÖZÖS self._stop új, üres eseményét látná,
        # és HAMIS „vége"/„hiba"-t küldene az ÚJ lejátszásra (a felolvasóban ez
        # állította le a felirat-narrációt tekeréskor). [Herman Tibor: AUDIO-03]
        self._generation = 0
        # HANGKIMENET. Üres = a rendszer alapértelmezettje. A `_alap_nev` az
        # a rendszer-alapértelmezett, amivel a jelenlegi stream elindult –
        # ha ez menet közben megváltozik (bluetooth fejhallgató), a `_feed`
        # szál észreveszi és ÁTÁLL rá. [Stolmár Barbi + Nagy Károly]
        self._device = RENDSZER_ESZKOZ
        self._alap_nev = ""
        self._device_valt = False
        # fn(régi_név, új_név) – a felület ebből mondhatja be a váltást.
        # ⚠️ Vakon a NÉMA átváltás is zavaró: ha a zene egyszer csak a másik
        # fülön szól, tudni kell, miért.
        self.on_device_change = None

    # ---- hangkimenet --------------------------------------------------

    @property
    def device(self) -> str:
        return self._device

    def set_device(self, azonosito: str) -> None:
        """A kívánt kimenet NEVE, vagy üres a rendszer alapértelmezettjéhez.
        A változás a KÖVETKEZŐ pufferrel érvényesül (a `_feed` újranyitja a
        streamet) – nem kell megállítani és újraindítani a zenét."""
        self._device = (azonosito or "").strip()
        self._device_valt = True

    def _stream_nyit(self, sd):
        """Kimeneti stream nyitása a kívánt eszközre, HIBATŰRŐEN.

        ⚠️ Ha a választott eszköz épp nincs jelen (kihúzott fejhallgató), NEM
        némulunk el: visszaesünk a rendszer alapértelmezettjére, és ezt a
        `on_device_change`-en keresztül meg is mondjuk. A néma elnémulás vakon
        megkülönböztethetetlen attól, hogy a program lefagyott."""
        kivant = self._device or None
        try:
            s = sd.RawOutputStream(samplerate=RATE, channels=CHANNELS,
                                   dtype="int16", blocksize=2048,
                                   device=kivant)
            s.start()
            self._alap_nev = alapertelmezett_kimenet()
            self._device_valt = False
            return s, ""
        except Exception as e:
            if not kivant:
                raise
            s = sd.RawOutputStream(samplerate=RATE, channels=CHANNELS,
                                   dtype="int16", blocksize=2048)
            s.start()
            self._alap_nev = alapertelmezett_kimenet()
            self._device = RENDSZER_ESZKOZ
            self._device_valt = False
            self._device_hiba(kivant, str(e))
            return s, kivant

    def _device_hiba(self, kivant: str, ok: str) -> None:
        if self.on_device_change:
            try:
                self.on_device_change(kivant, "")
            except Exception:
                pass

    # ---- állapot ------------------------------------------------------

    @property
    def volume(self) -> float:
        return self._volume

    def set_volume(self, v: float) -> None:
        self._volume = max(0.0, min(1.0, v))

    def is_active(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def is_paused(self) -> bool:
        return self._paused.is_set()

    def position(self) -> float:
        """A pillanatnyi lejátszási pozíció másodpercben (a ténylegesen
        megszólaltatott hangminták + a seek-kezdőpont alapján; szünetben
        nem nő)."""
        return self._start_offset + self._played / (RATE * CHANNELS * 2)

    # ---- vezérlés -----------------------------------------------------

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def toggle_pause(self) -> bool:
        """Visszaadja: True, ha most szünetel."""
        if self._paused.is_set():
            self._paused.clear()
        else:
            self._paused.set()
        return self._paused.is_set()

    def seek(self, pos: float) -> None:
        """Ugrás a megadott időpontra (a forrást a `-ss`-szel újraindítja)."""
        if self._url:
            self.play(self._url, self.title, start=max(0.0, pos))

    def relative_seek(self, delta: float) -> None:
        """Léptetés az aktuális pozícióhoz képest (finomhangoláshoz)."""
        self.seek(max(0.0, self.position() + delta))

    def stop(self) -> None:
        self._stop.set()
        self._paused.clear()
        with self._lock:
            p, self._proc = self._proc, None
        if p:
            # terminate→wait→kill→wait + csövek bezárása (MK4: nincs leíró-szivárgás
            # ismételt stop/play mellett)
            procutil.stop_proc(p)

    def play(self, url: str, title: str = "", progress=None,
             start: float = 0.0, audio_track: int | None = None) -> None:
        """A megadott forrás lejátszása (az előzőt leállítja). `start`>0 esetén
        onnan kezd (seek, az ffmpeg `-ss`-ével). `audio_track` megadva a több
        hangsávos adásból azt a sávot játssza (pl. hangalámondás)."""
        self.stop()
        self.title = title or url
        self._url = url
        ff = _ffmpeg_exe(progress)
        if not ff:
            self._emit("hiba: az ffmpeg nem érhető el")
            return
        self._stop = threading.Event()
        self._generation += 1
        gen = self._generation
        self._paused.clear()
        self._played = 0
        self._start_offset = max(0.0, float(start))
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        cmd = [ff, "-nostdin"]
        if self._start_offset > 0:
            cmd += ["-ss", f"{self._start_offset:.3f}"]
        cmd += ["-i", url]
        if audio_track is not None:
            cmd += ["-map", f"0:a:{int(audio_track)}"]
        cmd += ["-f", "s16le", "-ar", str(RATE),
                "-ac", str(CHANNELS), "-loglevel", "quiet", "-"]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    creationflags=flags)
        except Exception as e:
            self._emit(f"hiba: {e}")
            return
        with self._lock:
            self._proc = proc
        self._thread = threading.Thread(
            target=self._feed, args=(proc, self._stop, gen), daemon=True)
        self._thread.start()

    # ---- belső --------------------------------------------------------

    def _emit_gen(self, gen: int, text: str) -> None:
        """Állapot kiadása CSAK akkor, ha a hívó szál generációja még az aktuális
        – így a régi (leváltott) lejátszószál nem küld HAMIS állapotot az újra."""
        if gen == self._generation:
            self._emit(text)

    def _emit(self, text: str) -> None:
        if self.on_state:
            try:
                self.on_state(text)
            except Exception:
                pass

    def _feed(self, proc, stop_event, gen) -> None:
        # FONTOS: a szál KIZÁRÓLAG a saját `stop_event`-jét figyeli (nem a közös
        # self._stop-ot), és `gen`-en át küld állapotot – így egy leváltott régi
        # szál nem küld HAMIS állapotot az új lejátszásra. [Herman Tibor AUDIO-03]
        import numpy as np
        import sounddevice as sd
        # ⚠️ Ezt a szál INDULÁSAKOR kell elkapni: egy újabb `play()` közben
        # átírhatja. Azt jelzi, hogy ez a lejátszás TEKERÉSSEL indult.
        kezdo_pozicio = self._start_offset
        try:
            stream, _visszaesett = self._stream_nyit(sd)
        except Exception as e:
            self._emit_gen(gen, f"hiba: nincs hangkimenet ({e})")
            return
        self._emit_gen(gen, "lejátszás")
        started = False
        failed = False
        err_msg = ""
        kov_eszkoz_nezes = time.monotonic() + 2.0
        try:
            while not stop_event.is_set():
                if self._paused.is_set():
                    time.sleep(0.05)
                    continue
                # ⚠️ ESZKÖZVÁLTÁS MENET KÖZBEN (Barbi + Karcsi, 2026-09-21).
                # Két ok van rá: (1) a felhasználó választott másik kimenetet;
                # (2) a WINDOWS váltott alapértelmezettet – ilyenkor kapcsolt
                # be a bluetooth fejhallgató. A régi kód egyiket sem vette
                # észre: a stream a lejátszás elején nyílt meg, és ott maradt.
                most = time.monotonic()
                uj_alap = ""
                if most >= kov_eszkoz_nezes:
                    kov_eszkoz_nezes = most + 2.0
                    if not self._device:          # a rendszerre bízta
                        uj_alap = alapertelmezett_kimenet()
                        if uj_alap == self._alap_nev:
                            uj_alap = ""
                if self._device_valt or uj_alap:
                    regi = self._alap_nev
                    try:
                        stream.stop()
                        stream.close()
                    except Exception:
                        pass
                    try:
                        stream, _v = self._stream_nyit(sd)
                    except Exception as e:
                        failed, err_msg = True, str(e)
                        break
                    if self.on_device_change:
                        try:
                            self.on_device_change(regi, self._alap_nev
                                                  if not self._device
                                                  else self._device)
                        except Exception:
                            pass
                raw = proc.stdout.read(4096)
                if not raw:
                    break
                started = True
                if gen == self._generation:      # a pozíciót csak az AKTUÁLIS
                    self._played += len(raw)      # lejátszás számolja
                v = self._volume
                if v >= 0.999:
                    stream.write(raw)
                else:
                    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                    stream.write((a * v).astype(np.int16).tobytes())
        except Exception as exc:
            failed = True
            err_msg = str(exc)
        finally:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
            # a lejátszó ffmpeg learatása a szál végén: stdout bezárása + wait,
            # hogy a normál („vége") lefutáskor se maradjon nyitott leíró (MK4)
            procutil.reap(proc)
        if not stop_event.is_set():
            if failed and started:
                self._emit_gen(gen, f"hiba: lejátszás megszakadt – {err_msg}")
            elif failed:
                self._emit_gen(gen, "hiba: a forrás nem játszható le")
            elif started:
                self._emit_gen(gen, "vége")
            elif kezdo_pozicio > 0:
                # ⚠️ TEKERÉS A VÉGÉRE, NEM HIBA. Ha a lejátszás `-ss`-szel
                # indult, és onnantól már nincs hang, az azt jelenti, hogy a
                # kért időpont a felvétel VÉGÉN (vagy azon túl) van – nem
                # azt, hogy a fájl hibás. A régi kód itt „a forrás nem
                # játszható le"-t küldött, és emiatt a hangoskönyv NEM lépett
                # a következő sávra. [Turai László, 2026-09-23:
                # „Ha egy fájlt a végére tekerek, nem megy tovább a
                # következőre a lejátszás, de ha hagyom végig menni, akkor
                # igen."]
                self._emit_gen(gen, "vége")
            else:
                self._emit_gen(gen, "hiba: a forrás nem játszható le")
