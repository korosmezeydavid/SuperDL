"""Diagnosztikai csomag: titok-mentes hibajelentés-szöveg (Tibi-audit 3.7/11.5).

A vak felhasználó gyakran pontosan el tudja mondani, mit hallott – ez a modul a
MELLÉ teszi a tényeket: verziók, telepítés típusa, modulok, beállítás-kivonat és
az utolsó napló-sorok, EGYETLEN vágólapra tehető szövegben. SZIGORÚ szabály:
titok (AI/TTS-kulcs, süti-fájl tartalma) NEM kerülhet bele – a tárolt kulcsok
minden előfordulását kimaszkoljuk, a felhasználónevet ~-re cseréljük.
"""

import json
import platform
import sys
import time
from pathlib import Path

# a beállításokból CSAK ez a fehérlista kerül a jelentésbe (értékkel);
# minden más kimarad (a city és a cookies_file csak "megadva/nincs" jelzést kap)
_SETTINGS_WHITELIST = (
    "connections", "parallel", "limit", "audio_only", "audio_format",
    "video_format", "audio_bitrate", "audio_samplerate", "playlist_folders",
    "voice_mode", "tts", "sounds", "beep_enabled", "beep_volume",
    "selfvoice_enabled", "selfvoice_off", "selfvoice_rate", "selfvoice_volume",
    "hide_url_row", "startup_signal", "cookies", "update_last_check",
)


def _mask_secrets(text: str) -> str:
    """A TÁROLT (dekódolt) kulcsok minden előfordulásának kimaszkolása, plusz a
    felhasználói mappa (~) anonimizálása. Ugyanaz az elv, mint a keyscan-é."""
    secrets: set[str] = set()
    try:
        from . import store

        def walk(o):
            if isinstance(o, str):
                s = o.strip()
                if len(s) >= 12:          # csak érdemi hosszú titkok (zaj ki)
                    secrets.add(s)
            elif isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, (list, tuple)):
                for v in o:
                    walk(v)

        for loader in ("load_ai_config", "load_tts_keys"):
            try:
                walk(getattr(store, loader)())
            except Exception:
                pass
    except Exception:
        pass
    for s in sorted(secrets, key=len, reverse=True):
        text = text.replace(s, "•••KULCS-MASZKOLVA•••")
    home = str(Path.home())
    if home:
        text = text.replace(home, "~")
        text = text.replace(home.replace("\\", "/"), "~")
    return text


def install_kind() -> str:
    """Hogyan fut a program: forrásból / hordozható (onefile) / telepített
    vagy kicsomagolt mappás (onedir)."""
    if not getattr(sys, "frozen", False):
        return "forrásból futtatva (python)"
    exe_dir = Path(sys.executable).resolve().parent
    mei = getattr(sys, "_MEIPASS", "")
    onefile = bool(mei) and Path(mei).resolve() != exe_dir
    if onefile:
        return "hordozható (onefile exe)"
    if (exe_dir / "unins000.exe").exists():
        return "telepített (mappás, telepítővel)"
    return "mappás (onedir, telepítő nélkül)"


def _modules_lines() -> list[str]:
    out = []
    try:
        from . import modkit
        root = modkit.modules_root()
        if root.is_dir():
            for d in sorted(root.iterdir()):
                mf = d / "manifest.json"
                if not mf.is_file():
                    continue
                try:
                    m = json.loads(mf.read_text(encoding="utf-8"))
                    out.append(f"  {m.get('id', d.name)}: "
                               f"{m.get('version', '?')}  ({m.get('name', '')})")
                except (OSError, ValueError):
                    out.append(f"  {d.name}: (hibás manifest)")
    except Exception as e:
        out.append(f"  (modul-lista nem olvasható: {e})")
    return out or ["  (nincs telepített modul)"]


def _ytdlp_line() -> str:
    try:
        import yt_dlp
        origin = ("frissített (~/.superdl/bin)"
                  if ".superdl" in (yt_dlp.__file__ or "") else "beágyazott")
        return f"{yt_dlp.version.__version__} ({origin})"
    except Exception as e:
        return f"(nem tölthető be: {e})"


def _sor_allapot(manager) -> list[str]:
    """A LETÖLTÉSI SOR állapota (Karcsi, 2026-09-09).

    ⚠️ Eddig a jelentésben EGYETLEN SZÓ SEM volt a letöltésekről — holott a
    hibajelentések nagy része róluk szól. A felhasználó elküldte a
    diagnosztikát, mi meg megtudtuk belőle a wxPython verzióját, azt viszont
    nem, hogy melyik letöltés hibás és miért.

    Az `utolso_hiba` azért van itt, mert az TÚLÉLI a program bezárását: a
    felhasználó másnap is el tudja küldeni azt, ami tegnap történt."""
    if manager is None:
        return ["  (a letöltéskezelő nem érhető el)"]
    try:
        jobs = list(manager.jobs)
    except Exception as e:
        return ["  (a sor nem olvasható: %s)" % e]
    if not jobs:
        return ["  (a sor üres)"]
    out = []
    for j in jobs:
        p = j.progress
        nev = p.filename or j.url
        jelzok = ["állapot: %s" % p.status]
        if p.total:
            jelzok.append("%d%%" % round(p.percent))
        if getattr(p, "elakadt", False):
            jelzok.append("ELAKADT")
        if getattr(p, "conflict", False):
            jelzok.append("ütközés (döntésre vár)")
        if getattr(j, "retries", 0):
            jelzok.append("%d sikertelen próba" % j.retries)
        out.append("  [%s] %s" % (j.kind, nev))
        out.append("      " + " · ".join(jelzok))
        # a NYERS hibaszövegek – ezekért készül az egész jelentés
        if p.error:
            out.append("      élő hiba: %s" % p.error)
        korabbi = getattr(j, "utolso_hiba", "")
        if korabbi and korabbi != p.error:
            mikor = getattr(j, "utolso_hiba_ideje", None)
            ido = ""
            if mikor:
                try:
                    ido = time.strftime(" (%Y-%m-%d %H:%M)",
                                        time.localtime(float(mikor)))
                except Exception:
                    ido = ""
            out.append("      korábbi hiba%s: %s" % (ido, korabbi))
    return out


def _motor_sorok() -> list[str]:
    """A torrent-motor tényei. Hibánál sem dobunk kivételt: egy hibajelentés
    összeállítása nem hasalhat el azon, amiről jelentést írna."""
    try:
        from . import torrent
        adat = torrent.motor_allapot()
    except Exception as e:
        return ["  (a motor állapota nem lekérdezhető: %s)" % e]
    out = ["  aria2c: %s" % adat.get("aria2c", "?"),
           "  fut: %s" % ("igen" if adat.get("fut") else "NEM")]
    for kulcs, cimke in (("verzio", "aria2 verzió"), ("port", "vezérlő port"),
                         ("aktiv", "aktív letöltés"),
                         ("varakozo", "várakozó"), ("leallt", "leállt"),
                         # MŰSZER (4.6.6) – ezek zárják le a „miért némult el
                         # a motor" kérdést, hipotézis helyett méréssel
                         ("rpc_hivasok", "vezérlő hívások"),
                         ("rpc_hibak", "ebből hibás"),
                         ("rpc_lassu", "1 mp-nél lassabb"),
                         ("rpc_leglassabb", "leglassabb válasz"),
                         ("figyelo_utolso_valasz", "a figyelő utolsó válasza"),
                         ("figyelo_utolso_hiba", "a figyelő utolsó hibája")):
        if kulcs in adat:
            out.append("  %s: %s" % (cimke, adat[kulcs]))
    if adat.get("megjegyzes"):
        out.append("  megjegyzés: %s" % adat["megjegyzes"])
    for h in adat.get("hibak", []):
        out.append("  MOTOR-HIBAÜZENET: %s" % h)
    return out


def build_report(settings: dict | None = None,
                 log_lines: list[str] | None = None,
                 manager=None) -> str:
    """A teljes, titok-mentes diagnosztikai jelentés összeállítása.

    `settings`: a futó program beállítás-szótára (ha None, a mentett fájlból
    olvassuk); `log_lines`: az ablak utolsó napló-sorai (a GUI adja át);
    `manager`: a futó letöltéskezelő, a sor állapotához."""
    from superdl import __version__
    try:
        from .modkit import CORE_API
    except Exception:
        CORE_API = "?"

    if settings is None:
        try:
            settings = json.loads((Path.home() / ".superdl.json")
                                  .read_text(encoding="utf-8"))
        except (OSError, ValueError):
            settings = {}

    lines = [
        "SuperDL – diagnosztikai jelentés (titkok maszkolva)",
        "=" * 52,
        f"SuperDL verzió:   {__version__}   (modul-API: {CORE_API})",
        f"Telepítés:        {install_kind()}",
        f"Windows:          {platform.platform()}",
        f"Python:           {platform.python_version()} "
        f"({'64' if sys.maxsize > 2**32 else '32'} bit)",
        f"yt-dlp motor:     {_ytdlp_line()}",
    ]
    try:
        import wx
        lines.append(f"wxPython:         {wx.version()}")
    except Exception:
        pass
    pend = Path.home() / ".superdl" / "update_pending.json"
    lines.append(f"Függő önfrissítés-jelző: {'VAN' if pend.exists() else 'nincs'}")
    # NUMPY (Tóth Zoltán, 2026-09-24): régi processzoron nem tölthető be –
    # ilyenkor a retró hang és a helyben fordító nem megy. A jelentésből első ránézésre látsszon.
    try:
        from . import numpyor
        if numpyor.elerheto():
            lines.append("Számolókönyvtár:  numpy rendben")
        else:
            lines.append("Számolókönyvtár:  NEM TÖLTHETŐ BE – "
                         + (numpyor.hiba() or "ismeretlen ok"))
    except Exception as e:
        lines.append(f"Számolókönyvtár:  nem ellenőrizhető ({e})")
    # OFFLINE FORDÍTÁS: hibajelentésnél az első kérdés, hogy a gépen egyáltalán
    # elérhető-e a motor, és melyik nyelvi csomagok vannak letöltve.
    try:
        from . import offlineford
        if offlineford.elerheto():
            parok = ", ".join("%s→%s" % p for p in offlineford.telepitett_parok())
            lines.append("Offline fordítás:  elérhető; nyelvi csomagok: "
                         + (parok or "még egy sincs letöltve"))
        else:
            # ⚠️ NE csak azt írjuk, hogy „nincs" – írjuk meg, MI hiányzik
            # (Farkas István, 2026-09-19). Egy hibajelentésben a „nincs"
            # semmit nem ér: pont az a kérdés, miért.
            reszek = "; ".join(offlineford.hianyzo_reszek())
            lines.append("Offline fordítás:  NINCS – " +
                         (reszek or "a fordítómotor hiányzik ebből a "
                                    "verzióból"))
    except Exception as e:
        lines.append(f"Offline fordítás:  nem ellenőrizhető ({e})")

    lines += ["", "Telepített modulok:"]
    lines += _modules_lines()

    lines += ["", "Beállítás-kivonat (csak nem-bizalmas):"]
    for k in _SETTINGS_WHITELIST:
        if k in settings:
            lines.append(f"  {k} = {settings[k]!r}")
    # bizalmas/személyes mezőknél csak a TÉNY, nem az érték
    for k, label in (("city", "város (napi időjárás)"),
                     ("cookies_file", "cookies.txt fájl")):
        if settings.get(k):
            lines.append(f"  {label}: megadva (értéke nem része a jelentésnek)")

    # ---- AMIÉRT AZ EGÉSZ JELENTÉS KÉSZÜL (Karcsi, 2026-09-09) -----------
    # A sorrend szándékos: a LETÖLTÉSEK állapota elöl. Aki hibát jelent, az
    # szinte mindig egy letöltésről beszél – eddig viszont a jelentésben
    # ebből semmi nem volt benne, és a wxPython-verzió után kellett volna
    # kitalálnunk, mi történt.
    lines += ["", "Letöltési sor:"]
    lines += _sor_allapot(manager)

    lines += ["", "Torrent-motor:"]
    lines += _motor_sorok()

    if log_lines:
        lines += ["", f"Utolsó események az ablakban ({len(log_lines)}):"]
        lines += ["  " + ln for ln in log_lines]

    # ---- A NAPLÓFÁJL VÉGE ------------------------------------------------
    # Ez az, ami eddig egyáltalán nem létezett: a `logging`-hoz nem tartozott
    # kezelő, tehát minden `_log.exception(...)` a semmibe ment. Az ablak
    # eseménynaplója CSAK a kimondott mondatokat tartalmazza; itt viszont ott
    # a nyers motorüzenet és a teljes hibaverem is.
    try:
        from . import naplo
        vege = naplo.utolso_sorok(200)
        if vege.strip():
            lines += ["", "Naplófájl vége (%s, %d bájt):"
                          % (naplo.FAJL.name, naplo.meret())]
            lines += ["  " + ln for ln in vege.splitlines()]
        else:
            lines += ["", "Naplófájl: még üres (ebben a munkamenetben nem "
                          "történt naplózandó esemény)"]
    except Exception as e:
        lines += ["", "Naplófájl: nem olvasható (%s)" % e]

    # ---- NATÍV ÖSSZEOMLÁS -------------------------------------------------
    # Az `osszeomlas.py` évek óta megvan, és a saját dokumentációja szerint
    # „a diagnosztikai ablakhoz és a hibajelentéshez" készült – de SOHA nem
    # volt bekötve ide. Ugyanaz a minta, mint az MK6-nál: egy jó szolgáltatás,
    # amit senki nem hív.
    try:
        from . import osszeomlas
        if osszeomlas.volt_osszeomlas():
            # A TELJES utolsó nyomot csatoljuk, a fejlécével együtt – abban
            # van a hiba KÓDJA. A korábbi 80 soros sorfark a nyom közepét
            # vágta ki, és pont az ok maradt le róla.
            nyom = (osszeomlas.utolso_osszeomlas()
                    or osszeomlas.naplo_szoveg(120))
            # A BEFAGYÁS nyoma ugyanebbe a naplóba kerül, de nem ugyanaz:
            # ott a program ÉLT, csak nem válaszolt. Rossz címke alatt a
            # fejlesztő is rossz irányba indul. [Tóth László, 2026-09-14]
            fejlec = ("⚠️ MEGAKADÁS-NAPLÓ (a program nem válaszolt; "
                      "minden szál verme):"
                      if osszeomlas.MEGAKADAS_FEJLEC in nyom
                      else "⚠️ ÖSSZEOMLÁS-NAPLÓ (natív hiba nyoma):")
            lines += ["", fejlec]
            # MIKOR és MI TÖRTÉNT AZÓTA. Dr. Kiss István 2026-09-16-i
            # jelentésében a nyom NÉGY NAPOS volt, egy azóta javított hibáról,
            # és utána huszonöt indulás következett zavartalanul — a jelentés
            # élén viszont csak egy dátumtalan ⚠️ állt. Így az is beküldi, akit
            # épp nem ér baj, és a fejlesztő is rossz irányba indul. A nyom
            # marad, a KÖRÜLMÉNYE kerül mellé.
            lines += ["  " + s for s in _nyom_kora_sorok(osszeomlas)]
            lines += ["  " + ln for ln in nyom.splitlines()]
    except Exception:
        pass

    lines += ["", "(A jelentés nem tartalmaz API-kulcsot, jelszót vagy "
                  "süti-tartalmat; a felhasználói mappa ~ jellel szerepel.)"]
    return _mask_secrets("\n".join(lines))


def _nyom_kora_sorok(osszeomlas) -> list:
    """A nyom KÖRÜLMÉNYE: mikor, melyik verzióban, és mi volt azóta.

    Külön függvény, hogy tesztelhető legyen a jelentés egésze nélkül."""
    try:
        info = osszeomlas.nyom_kora()
    except Exception:
        return []
    if not info:
        return []
    ki = []
    if info.get("ido"):
        ki.append("MIKOR: %s, a(z) %s verzióban."
                  % (info["ido"], info.get("verzio") or "ismeretlen"))
    ota = int(info.get("ota") or 0)
    if ota:
        ki.append("AZÓTA: %d indulás, újabb nyom nélkül." % ota)
    else:
        ki.append("AZÓTA: ez volt a LEGUTÓBBI indulás — a nyom friss.")
    regi = info.get("verzio")
    most = info.get("most")
    if ota and regi and most and regi != most:
        ki.append("FIGYELEM: a nyom egy KORÁBBI verzióból való (%s), "
                  "a program azóta %s. Lehet, hogy a hibát már javítottuk."
                  % (regi, most))
    return ki
