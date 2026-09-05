"""Letöltési sor: több feladat párhuzamos futtatása, időzítéssel,
és a sor megőrzésével program-újraindítás után is."""

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path

from . import hibaszoveg
from . import lemezhely
from . import netcheck
from . import retrypolicy
from . import savszelesseg
from . import store
from .media import MediaDownloader, is_media_url
from .segment import Progress, RateLimiter, SegmentDownloader, parse_limit
from .torrent import TorrentDownloader, is_torrent_url

_ids = count(1)
_log = logging.getLogger("superdl.manager")


def parse_when(text: str) -> float | None:
    """Időpont szövegből unix időbélyeggé.

    Elfogad: '+90' (perc múlva), '+2h' (óra múlva), 'HH:MM' (ma/holnap az
    adott órakor), 'ÉÉÉÉ-HH-NN ÓÓ:PP' (konkrét időpont). Üres/0 esetén None.
    """
    import datetime as _dt

    text = (text or "").strip().lower()
    if not text or text == "0":
        return None
    now = _dt.datetime.now()
    if text.startswith("+"):
        body = text[1:].strip()
        mult = 60
        if body and body[-1] in "hmd":
            mult = {"m": 60, "h": 3600, "d": 86400}[body[-1]]
            body = body[:-1]
        try:
            secs = float(body)
        except (ValueError, TypeError):
            return None
        if secs < 0:
            return None
        return (now + _dt.timedelta(seconds=secs * mult)).timestamp()
    for fmt in ("%Y-%m-%d %H:%M", "%Y.%m.%d %H:%M", "%m-%d %H:%M"):
        try:
            dt = _dt.datetime.strptime(text, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=now.year)
            return dt.timestamp()
        except ValueError:
            pass
    try:  # csak óra:perc -> ma, vagy ha már elmúlt, holnap
        hh, mm = (int(x) for x in text.split(":"))
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target <= now:
            target += _dt.timedelta(days=1)
        return target.timestamp()
    except (ValueError, TypeError):
        return None


@dataclass
class Job:
    url: str
    kind: str                      # "media", "file" vagy "torrent"
    progress: Progress = field(default_factory=Progress)
    id: int = field(default_factory=lambda: next(_ids))
    downloader: object = None
    out_dir: str | None = None     # ha None, a kezelő közös mappáját használja
    audio_only: bool | None = None
    start_at: float | None = None  # ütemezett indítás (unix idő), None = azonnal
    added_at: float = field(default_factory=time.time)
    submitted: bool = False        # már elindítottuk-e
    overwrite: bool = False         # torrent: meglévő fájl felülírása
    verify: bool = False            # torrent: meglévő fájl ellenőrzése + seed
    # A FELHASZNÁLÓ állította-e le (MK1). Ezt SOHA nem a státuszszóból
    # következtetjük vissza: a kilépéskori stop_all() ugyanúgy „leállítva"-t
    # ír, mint a kézi leállítás, és a kettőnek ELLENTÉTES a jelentése.
    # Enélkül a torrent vagy sosem folytatódik, vagy a kézzel leállított
    # indul el magától – és nincs az az állapotszó, amiből ez kiderülne.
    user_stopped: bool = False
    # újrapróba (MK4): hány sikertelen próba volt, és mikor jöhet a következő
    retries: int = 0
    next_retry_at: float | None = None

    def to_record(self) -> dict:
        return {"url": self.url, "kind": self.kind, "out_dir": self.out_dir,
                "audio_only": self.audio_only, "start_at": self.start_at,
                "status": self.progress.status,
                "filename": self.progress.filename,
                "overwrite": self.overwrite, "verify": self.verify,
                "user_stopped": self.user_stopped}


class DownloadManager:
    """Egyszerre legfeljebb `parallel` letöltés fut, mindegyik
    `connections` kapcsolattal."""

    # MK2: nem „hiba", hanem VÁRAKOZÁS. A kettő különbsége vakon a legnagyobb:
    # a „hiba" azt jelenti, hogy tenned kell valamit; ez azt, hogy nem kell.
    HALOZATRA_VAR = "várakozik a hálózatra"
    # milyen sűrűn nézzük, visszajött-e a net (a netcheck maga is gyorsítótáraz)
    HALO_ELLENORZES_SEC = 10

    # ezekben az állapotokban érdemes a sort menteni / újraindításkor folytatni
    # a hibára futott letöltéseket NEM ajánljuk fel folytatásra (értelmetlen)
    RESUMABLE = ("várakozik", "ütemezve", "letöltés", "leállítva",
                 HALOZATRA_VAR)

    def __init__(self, out_dir: str, parallel: int = 3, connections: int = 8,
                 audio_only: bool = False, limit_bps: int = 0,
                 seed_ratio: float = 1.0, persist: bool = True,
                 seed_forever: bool = True, upload_limit_bps: int = 0,
                 audio_format: str = "mp3", video_format: str | None = None,
                 audio_bitrate: str = "192", audio_samplerate: str = "",
                 cookies_browser: str | None = None,
                 cookies_file: str | None = None,
                 playlist_folders: bool = True):
        self.out_dir = out_dir
        self.connections = connections
        self.audio_only = audio_only
        self.audio_format = audio_format
        self.video_format = video_format
        self.audio_bitrate = audio_bitrate
        self.audio_samplerate = audio_samplerate
        self.cookies_browser = cookies_browser
        self.cookies_file = cookies_file
        self.playlist_folders = playlist_folders
        self.seed_ratio = seed_ratio
        self.seed_forever = seed_forever
        self.upload_limit_bps = upload_limit_bps
        self.persist = persist
        # a felület ide köthet be egy felolvasó visszahívást (újrapróba-jelzés)
        self.on_notice = None
        # MK2: hálózatfigyelő állapota
        self._halo_offline = False
        self._halo_ellenorizve = 0.0
        # MK9: időzített sebességkorlát (pl. „22:00-06:00=0; 06:00-22:00=500K")
        self.savszelesseg_rend = ""
        self._savszelesseg_elozo = None
        # közös korlát: az összes letöltés együtt sem lépi túl
        self.limiter = RateLimiter(limit_bps)
        self.pool = ThreadPoolExecutor(max_workers=parallel)
        self.jobs: list[Job] = []
        self._lock = threading.Lock()
        self._closing = threading.Event()
        # az automatikus mentés csak akkor indulhat, ha már volt hozzáadás
        # vagy lefutott a restore() - különben induláskor felülírnánk a
        # korábban mentett, még folytatható sort egy üres listával
        self._allow_autosave = False
        # háttérszál: ütemezett indítás + a sor időnkénti mentése
        self._ticker = threading.Thread(target=self._tick_loop, daemon=True)
        self._ticker.start()

    # ---- hozzáadás ----------------------------------------------------

    def add(self, url: str, kind: str | None = None,
            out_dir: str | None = None, audio_only: bool | None = None,
            start_at: float | None = None, overwrite: bool = False,
            verify: bool = False, autostart: bool = True) -> Job:
        """Új letöltés a sorba. `autostart=False` esetén csak felveszi
        „leállítva" állapotban, és NEM indítja el magától (ezt használja a
        restore() a korábban leállított elemekhez)."""
        if kind is None:
            if is_torrent_url(url):
                kind = "torrent"
            else:
                kind = "media" if is_media_url(url) else "file"
        job = Job(url=url, kind=kind, out_dir=out_dir, audio_only=audio_only,
                  start_at=start_at, overwrite=overwrite, verify=verify)
        job.progress.filename = url
        if start_at and start_at > time.time():
            job.progress.status = "ütemezve"
        elif not autostart:
            job.progress.status = "leállítva"   # folytatható, de magától nem indul
        with self._lock:
            self.jobs.append(job)
        self._allow_autosave = True
        if job.progress.status not in ("ütemezve", "leállítva"):
            self._launch(job)
        self._save()
        return job

    def _launch(self, job: Job) -> None:
        job.submitted = True
        if job.kind == "torrent":
            # a torrentet az aria2 kezeli, nem foglal helyet a sorban
            # (seedelés közben sem tartana fel más letöltést)
            threading.Thread(target=self._run_job, args=(job,),
                             daemon=False).start()
        else:
            self.pool.submit(self._run_job, job)

    def _run_job(self, job: Job) -> None:
        if job.progress.status == "leállítva":
            return
        # A célmappa vezető/záró szóközét levágjuk: Windowson a „ C:\\…" (vezető
        # szóközzel) érvénytelen útvonal → WinError 123, és MINDEN letöltő
        # (torrent/média/szegmens) elhasal (így a podcast-epizódoké is, ha a
        # mentett mappában bennragadt egy szóköz). Egy közös csomópont véd.
        out_dir = str(job.out_dir or self.out_dir).strip()
        audio = self.audio_only if job.audio_only is None else job.audio_only
        # MK8 (az MK3 maradéka): hely-figyelmeztetés a yt-dlp és a torrent
        # motorra is. Ezek indulás előtt NEM ismerik a méretet, ezért nem
        # tarthatjuk vissza a letöltést – de a majdnem tele lemezt ki tudjuk
        # mondani, amíg tenni lehet valamit. A szegmentált motor a saját,
        # PONTOS ellenőrzését végzi a `_probe()` után (MK3); ott ez a durvább
        # figyelmeztetés fölösleges volna.
        if job.kind in ("torrent", "media"):
            uzenet = lemezhely.indulas_elott(out_dir)
            if uzenet:
                self._jelez(uzenet, job)
        try:
            if job.kind == "torrent":
                # A kényszerített újraindítás EGYETLEN indításra kér
                # ellenőrzést (a meglévő adat megtartásához). Átmeneti jelző,
                # nem mentett mező: különben minden későbbi induláskor is
                # ellenőrizne, ami nagy torrentnél percekig tart.
                kenyszer = bool(getattr(job, "kenyszer_ujra", False))
                job.kenyszer_ujra = False
                job.downloader = TorrentDownloader(
                    job.url, out_dir, progress=job.progress,
                    seed_ratio=self.seed_ratio, limit_bps=self.limiter.bps,
                    allow_overwrite=job.overwrite,
                    check_integrity=job.verify or kenyszer,
                    seed_forever=self.seed_forever,
                    upload_limit_bps=self.upload_limit_bps)
            elif job.kind == "media":
                job.downloader = MediaDownloader(
                    job.url, out_dir, connections=self.connections,
                    audio_only=audio, progress=job.progress,
                    limit_bps=self.limiter.bps,
                    audio_format=self.audio_format,
                    video_format=self.video_format,
                    audio_bitrate=self.audio_bitrate,
                    audio_samplerate=self.audio_samplerate,
                    cookies_browser=self.cookies_browser,
                    cookies_file=self.cookies_file,
                    playlist_folders=self.playlist_folders)
            else:
                job.downloader = SegmentDownloader(
                    job.url, out_dir, connections=self.connections,
                    progress=job.progress, limiter=self.limiter)
            job.downloader.run()
        except Exception as exc:
            uzenet = job.progress.error or str(exc)
            # MK8: KILÉPÉSKOR NINCS HIBA, csak leállítás.
            # A bezárás kirántja az aria2-t a futó torrent alól; a szál ebből
            # kivételt kap, és eddig HIBÁNAK könyvelte el. A `finally` mentés
            # pedig a `close()` UTÁN futott le, tehát a hibás állapot lett a
            # mentett állapot — a felhasználó a KÖVETKEZŐ indításkor látta,
            # hogy „hibás a torrent", holott csak bezárta a programot.
            # (Az MK6 óta ez rosszabb: az F6 oda is küldi, egy nem létező
            # hibához.) A leállítás-jelző itt a mérvadó, nem a kivétel.
            leallt = (self._closing.is_set()
                      or (job.downloader is not None
                          and getattr(job.downloader, "_stop", None) is not None
                          and job.downloader._stop.is_set()))
            if leallt:
                job.progress.status = "leállítva"
                job.progress.error = ""
                job.next_retry_at = None
                _log.info("Leállítás közbeni kivétel elnyelve: %s", job.url)
            elif (job.progress.status != "leállítva"
                    and self.halozati_eredetu(uzenet)):
                # MK2: NEM hiba, hanem VÁRAKOZÁS. Ha elment a net, a felhasználó
                # nem tud mit tenni – és ha „hibát" mondunk, azzal azt üzenjük,
                # hogy tennie kellene. Vakon ez a legrosszabb: a program megáll,
                # semmi nem szól érte, és órákkal később derül ki, hogy nem
                # történt semmi. A hálózatfigyelő innen veszi át.
                job.progress.status = self.HALOZATRA_VAR
                job.progress.error = ""
                job.next_retry_at = None
                _log.info("Hálózat-kimaradás, várakozás: %s", job.url)
            else:
                # a letöltők többsége már beállítja a job.progress.error mezőt, de
                # ha NEM (pl. már a letöltő-objektum létrehozása elszállt), itt
                # gondoskodunk róla, hogy a hiba látszódjon és NAPLÓZÓDJON
                if job.progress.status not in ("hiba", "leállítva"):
                    job.progress.status = "hiba"
                    if not job.progress.error:
                        job.progress.error = str(exc)
                # MK6: a hibaszöveg emberi nyelvre fordítása MINDEN motorra.
                # ⚠️ A SORREND KÖTÖTT: ez CSAK a hálózati besorolás UTÁN
                # futhat. A `halozati_eredetu()` az ANGOL nyers szövegben
                # keres mintát („failed to establish", „getaddrinfo"); ha
                # előbb fordítanánk, a minta nem illene, és a hálózat-
                # kimaradásból megint HIBA lenne – vagyis az MK2-t
                # csendben visszacsinálnánk.
                if job.progress.status == "hiba":
                    job.progress.error = hibaszoveg.emberi(job.progress.error)
                _log.exception("Letöltési feladat hibája: %s", job.url)
        finally:
            self._save()

    # ---- ütemezés + mentés háttérszál ---------------------------------

    def _tick_loop(self) -> None:
        last_save = time.time()
        while not self._closing.is_set():
            now = time.time()
            for job in list(self.jobs):
                if (job.progress.status == "ütemezve" and not job.submitted
                        and job.start_at and job.start_at <= now):
                    job.progress.status = "várakozik"
                    self._launch(job)
                self._retry_tick(job, now)
                self._hely_tick(job)
                self._kuzd_tick(job)
                self._elakadas_tick(job)
            self._halozat_tick(now)
            self._savszelesseg_tick()
            if self._allow_autosave and now - last_save >= 3:
                last_save = now
                self._save()
            time.sleep(1)

    # ---- MK6: melyik elem igényel FIGYELMET ---------------------------

    # Hányadik újrapróba után mondjuk, hogy ez már emberi beavatkozást kér.
    # Az első néhány bukás gyakran magától rendbe jön (pillanatnyi
    # szerverhiba); a sokadik viszont már nem fog.
    MAKACS_PROBA = 3

    @staticmethod
    def figyelmet_igenyel(job) -> bool:
        """Van-e ezzel az elemmel VALÓDI teendő?

        Három eset, és mindháromnál a felhasználó tud tenni valamit:

        1. **hiba** – meg kell nézni, mi történt;
        2. **ütközés** (`p.conflict`, a cél fájl már létezik) – DÖNTÉSRE vár, és
           az MK4-ben külön kimondtuk, hogy ez NEM kap újrapróbát: magától
           soha nem oldódik meg;
        3. **makacsul újrapróbálkozó elem** – ami már sokadszor bukott el,
           az valószínűleg nem fog magától megjavulni.

        ⚠️ **AMI SZÁNDÉKOSAN KIMARAD, és ez a lényeg:**

        - **`várakozik a hálózatra`** – az MK2 egész értelme az volt, hogy ez
          NEM igényel beavatkozást („nem kell tenned semmit"). Ha idesorolnánk,
          a felhasználót olyasmihez küldenénk, amit nem tud megjavítani –
          vagyis csendben visszacsinálnánk az MK2-t.
        - **`várakozik` / `ütemezve`** – ez a sor normális működése.
        - **`leállítva`** – ezt ő maga kérte. A saját döntést problémának
          nevezni bosszantó és bizalomromboló.
        """
        p = job.progress
        # A KIZÁRÁS ÁLL ELÖL, és ez nem stílus kérdése.
        # Az első változatban a „makacs újrapróba" ág volt a végén, feltétellel
        # („nem kész és nem leállítva") – és ÁTENGEDTE a hálózatra várakozó
        # elemet, ha az sokat próbálkozott. A teszt fogta meg. Így a szabály
        # csendben visszacsinálta volna az MK2-t: a felhasználót olyasmihez
        # küldtük volna, amit nem tud megjavítani. Egyetlen listán, elöl.
        if p.status in (DownloadManager.HALOZATRA_VAR, "kész", "leállítva"):
            return False
        if getattr(p, "conflict", False):
            return True
        if p.status == "hiba":
            return True
        # NEGYEDIK eset (Laci hibajelentése, 2026-09-05): ELAKADT, de „aktív”.
        # Ez volt a rendszer vakfoltja. A torrent státusza „letöltés”, kivétel
        # nincs, újrapróba nincs – tehát a fenti három ág egyike sem fogta meg,
        # és a felhasználó egy órán át nézett egy listát, amely azt állította,
        # hogy minden rendben. **A hamis megnyugtatás rosszabb, mint a néma
        # hiba**, mert a felhasználó nem is kezd keresni.
        # ⚠️ A kizárás fent VÁLTOZATLAN: a hálózatra várakozó elem NEM lehet
        # elakadt (ott a letöltő le sem fut), tehát az MK2-t ez sem érinti.
        if getattr(p, "elakadt", False):
            return True
        if getattr(job, "retries", 0) >= DownloadManager.MAKACS_PROBA:
            return True
        return False

    def figyelmet_igenylok(self) -> list:
        """A figyelmet igénylő elemek, a SORRENDBEN, ahogy a listában állnak.

        A sorrend nem esztétika: vakon a lista sorrendje az egyetlen térkép.
        Ha a navigáció más sorrendben lépkedne, mint amit a képernyőolvasó
        felolvas, a felhasználó elveszne benne."""
        return [j for j in self.jobs if self.figyelmet_igenyel(j)]

    # ---- MK9: időzített sebességkorlát --------------------------------

    def _savszelesseg_tick(self) -> None:
        """Az órarend szerinti sebességkorlát érvényesítése.

        A korlát a KÖZÖS `limiter`-en él, tehát az összes letöltésre együtt
        vonatkozik — ahogy a kézzel beállított is. Váltáskor SZÓLUNK: a
        hirtelen lelassuló letöltés magától nem érthető, és a felhasználó azt
        hinné, elromlott valami vagy gyenge a net."""
        rend = getattr(self, "savszelesseg_rend", "") or ""
        if not rend:
            return
        korlat = savszelesseg.korlat_most(rend)
        if korlat is None:
            return
        if korlat == getattr(self, "_savszelesseg_elozo", None):
            return
        self._savszelesseg_elozo = korlat
        try:
            self.limiter.bps = parse_limit(korlat)
        except Exception:
            return
        self._jelez(savszelesseg.valtas_mondat(korlat), None)

    # ---- MK8: a letöltés menet közben küzd ----------------------------

    # Ennyi belső újrapróba után szólunk. Az első kettő teljesen normális
    # (egy szerver ejt egy kapcsolatot, és kész); a harmadiktól viszont már
    # nem véletlen, és a felhasználó észreveszi, hogy „lassú" – csak azt nem
    # tudja, miért.
    KUZD_KUSZOB = 3

    def _kuzd_tick(self, job: Job) -> None:
        """Egyszeri jelzés, ha egy letöltés MENET KÖZBEN sokat újrapróbál.

        Eddig ez teljesen néma volt: a szegmentált letöltő ötször
        újrapróbálkozott szegmensenként, a felhasználó pedig annyit
        érzékelt, hogy lassú. **Vakon a lassú és az akadozó között nincs
        különbség** — pedig az egyik normális, a másik nem, és a kettőre
        más a helyes válasz (várni vs. leállítani és később újrakezdeni)."""
        p = job.progress
        if p.status != "letöltés":
            return
        if getattr(p, "belso_probak", 0) < self.KUZD_KUSZOB:
            return
        if getattr(job, "_kuzd_szolt", False):
            return
        job._kuzd_szolt = True
        self._jelez(retrypolicy.kuzd_uzenet(p.belso_probak), job)

    # ---- elakadt, de „aktív” letöltés (Laci, 2026-09-05) --------------

    def _elakadas_tick(self, job: Job) -> None:
        """EGYSZERI jelzés arról, hogy egy futó letöltés régóta nem halad.

        Miért egyszeri: az elakadás percekig-órákig eltarthat, és egy
        percenként ismételt bemondás használhatatlanná tenné a programot.
        Egyszer szólunk, utána az F6 és a lista oszlopa tartja számon.

        A mondat KIMONDJA a teendőt is. Egy jelzés, ami csak a bajt nevezi
        meg, vakon alig ér többet a csendnél: a felhasználó tudja, hogy baj
        van, de nem tudja, mit tehet."""
        p = job.progress
        if not getattr(p, "elakadt", False):
            job._elakadas_szolt = False      # újraindulhat a jelzés, ha megint
            return
        if getattr(job, "_elakadas_szolt", False):
            return
        job._elakadas_szolt = True
        nev = p.filename or job.url
        ok = getattr(p, "elakadas_oka", "") or "Nem érkezik adat."
        self._jelez(
            f"Elakadt: {nev}. {ok} Kényszerített újraindítás: Control F6.", job)

    def kenyszeritett_ujrainditas(self, job: Job,
                                  varakozas: float = 6.0) -> bool:
        """Torrent kényszerített újraindítása a MEGLÉVŐ adat megtartásával.

        Ezt Laci kérte, más kliensek mintájára, és igaza volt: amikor egy
        torrent áll, a felhasználónak kell egy kapaszkodó. Eddig nem volt —
        a Ctrl+F6 annyit mondott, hogy „nincs mit tenni”.

        **Amit csinál:** leállítja a futó aria2-munkát, megvárja, hogy tényleg
        megálljon, majd `check-integrity`-vel újra hozzáadja. Ez a torrent
        hash-ei alapján ellenőrzi a már meglévő darabokat, a jókat MEGTARTJA,
        és csak a hiányzókat tölti — közben pedig újra bejelentkezik a
        trackerekhez, és nulláról indítja a peer-keresést. **Nem kezdi elölről
        a letöltést**, és pontosan ez a lényeg: egy órányi letöltést eldobni
        rosszabb volna, mint az elakadás.

        ⚠️ A `verify` mezőt SZÁNDÉKOSAN nem írjuk át: az MENTŐDIK, és akkor
        minden későbbi indulás ellenőrizne — ami nagy fájlnál percekig tart.
        Ez a kérés egyetlen indításra szól, ezért átmeneti jelzőt használunk.
        """
        if job.kind != "torrent":
            return False
        dl = job.downloader
        if dl is not None and getattr(dl, "_stop", None) is not None:
            dl.stop()
            # MK8 tanulsága: a szálat MEG KELL VÁRNI. Ha az újraindítás
            # ráindulna a még futó régire, két szál kezelné ugyanazt a jobot.
            hatarido = time.monotonic() + float(varakozas)
            while (time.monotonic() < hatarido
                   and job.progress.status in ("letöltés", "seedelés",
                                               "előkészítés")):
                time.sleep(0.2)
        p = job.progress
        p.elakadt = False
        p.elakadas_oka = ""
        job._elakadas_szolt = False
        job.kenyszer_ujra = True             # egyszeri check-integrity
        self.start(job)
        return True

    # ---- MK3: fogyó lemezhely -----------------------------------------

    def _hely_tick(self, job: Job) -> None:
        """A letöltő által felírt hely-figyelmeztetés felolvastatása.

        A letöltő maga NEM tud a felolvasóról (és nem is szabad, hogy tudjon),
        ezért csak beírja a `progress.figyelmeztetes` mezőbe; a kimondás itt
        történik. Elemenként EGYSZER: a figyelmeztetés kiürül, miután
        elhangzott, és a letöltő már nem írja újra (ő is csak egyszer teszi).

        Ez FIGYELMEZTETÉS, nem hiba: a letöltés fut tovább. Lehet, hogy
        közben felszabadul a hely – egy futó letöltés megölése miatta
        biztosan rosszabb volna, mint egy mondat."""
        uzenet = job.progress.figyelmeztetes
        if not uzenet:
            return
        job.progress.figyelmeztetes = ""
        self._jelez(uzenet, job)

    # ---- MK2: hálózat-visszatérés -------------------------------------

    @staticmethod
    def halozati_eredetu(uzenet: str) -> bool:
        """Hálózat-kimaradás okozta-e a hibát?

        KÉT feltétel, és mindkettő kell. A hibaszöveg felismerése önmagában
        kevés: a `looks_like_offline` mintái közt ott az „ssl" és a „timeout"
        is, amit egy lassú vagy rosszul beállított szerver is kiválthat úgy,
        hogy közben a net tökéletes. Ezért utána MEG IS MÉRJÜK. Ha van net, ez
        valódi hiba – és akkor hibaként kell megjelennie, nem várakozásként,
        különben a felhasználó a végtelenségig várna valamire, ami nem jön el.
        """
        if not netcheck.looks_like_offline(uzenet):
            return False
        return not netcheck.online(force=True)

    @staticmethod
    def halozat_elment_uzenet(db: int) -> str:
        return ("Megszakadt az internetkapcsolat, %d letöltés várakozik. "
                "Nem kell tenned semmit: amint visszajön a net, magától "
                "folytatódnak." % db)

    HALOZAT_VISSZAJOTT = "Visszatért a kapcsolat, a letöltések folytatódnak."

    def _halozat_tick(self, now: float) -> None:
        varok = [j for j in self.jobs
                 if j.progress.status == self.HALOZATRA_VAR]
        if not varok:
            self._halo_offline = False
            return
        if not self._halo_offline:
            self._halo_offline = True
            self._jelez(self.halozat_elment_uzenet(len(varok)), varok[0])
        if now - self._halo_ellenorizve < self.HALO_ELLENORZES_SEC:
            return
        self._halo_ellenorizve = now
        if not netcheck.online():
            return
        self._halo_offline = False
        self._jelez(self.HALOZAT_VISSZAJOTT, varok[0])
        for job in varok:
            # a folytatás magukban a letöltőkben van: a szegmentált fájl a
            # .sdlstate-ből, a torrent az aria2 vezérlőfájlból, a yt-dlp a
            # .part-ból folytatódik – nekünk csak újra kell indítani őket
            self._ujraindit(job)

    def _ujraindit(self, job: Job) -> None:
        """Egy job újraindítása a helyéről (újrapróba és hálózat-visszatérés)."""
        job.downloader = None
        job.submitted = False
        job.progress.error = ""
        job.progress.status = "várakozik"
        self._launch(job)

    def _retry_tick(self, job: Job, now: float) -> None:
        """Újrapróba növekvő szünetekkel (MK1 döntés + MK4 közös politika).

        A hibára futott TORRENT a sorban marad, és magától újrapróbálkozik
        1, 2, 5, 10 perc, majd 15 percenként. Miért épp a torrentnél a
        legfontosabb: a torrent órákig-napokig fut, tehát biztosan „átalussza"
        a hálózat megbicsaklását – és vakon ezt a legnehezebb észrevenni,
        mert semmi nem szól érte.

        A kézzel leállított elem SOHA nem próbálkozik újra (`user_stopped`).
        """
        if job.kind != "torrent" or job.user_stopped:
            return
        if job.progress.status != "hiba":
            return
        if job.progress.conflict:
            return          # a „fájl már létezik" DÖNTÉST vár, nem újrapróbát
        if job.next_retry_at is None:
            job.next_retry_at = now + retrypolicy.szunet(job.retries)
            self._jelez(retrypolicy.uzenet(
                job.retries, int(job.next_retry_at - now)), job)
            return
        if now < job.next_retry_at:
            return
        job.retries += 1
        job.next_retry_at = None
        self._ujraindit(job)

    def _jelez(self, szoveg: str, job: Job) -> None:
        """Felolvasandó jelzés a felületnek. A kezelő nem ismeri a wx-et, ezért
        csak egy visszahívást hív, ha a felület beállított egyet."""
        if not szoveg:
            return
        cb = getattr(self, "on_notice", None)
        if cb is None:
            return
        try:
            cb(szoveg, job)
        except Exception:
            _log.exception("a jelzés-visszahívás hibája")

    def _persistable(self, job: Job) -> bool:
        """Elmentendő-e a sorba?

        A folytatható állapotok igen. A TORRENT viszont MINDIG marad – „hiba"
        és „kész" állapotban is –, mert:
          * a hibára futott torrent eddig nyomtalanul eltűnt a sorból egy
            hálózatkimaradás után (MK1 4. pont), pedig épp ilyenkor kellene
            magától újrapróbálkoznia;
          * a készre töltött torrent a döntés szerint KÉZI LEÁLLÍTÁSIG seedel,
            tehát nem szabad eldobni.
        A torrentet CSAK a törlés veszi ki a sorból.
        """
        if job.kind == "torrent":
            return True
        return job.progress.status in self.RESUMABLE

    def _save(self) -> None:
        if not self.persist or not self._allow_autosave:
            return
        records = [j.to_record() for j in self.jobs if self._persistable(j)]
        try:
            store.save_queue(records)
        except Exception:
            pass

    def restore(self) -> list[Job]:
        """A korábban mentett, befejezetlen letöltések folytatása
        program-indításkor. A szegmentált fájlok a .sdlstate alapján onnan
        folytatódnak, ahol abbamaradtak."""
        restored: list[Job] = []
        records = store.load_queue()      # előbb beolvassuk az egész sort
        self._allow_autosave = True       # innentől menthet a háttérszál
        for r in records:
            url = r.get("url")
            if not url:
                continue
            status = r.get("status", "")
            kind = r.get("kind")
            user_stopped = bool(r.get("user_stopped", False))
            # A már befejezett vagy hibára futott elemeket nem töltjük vissza –
            # DE A TORRENTET IGEN. FIGYELEM: ez a szűrő a `_persistable()`
            # TESTVÉRE; ha csak az egyiket javítjuk, a mentés megtörténik, a
            # visszatöltés viszont némán eldobja – vagyis a teszt zöld, a
            # felhasználónál mégsem működik. Mindkét helyen javítani kell.
            if kind != "torrent" and status in ("kész", "hiba"):
                continue
            if kind == "torrent":
                # MK1: a torrent akkor és CSAK akkor nem indul magától, ha a
                # FELHASZNÁLÓ állította le. A „leállítva" státusz önmagában
                # semmit nem jelent: a kilépéskori stop_all() is azt írja be.
                autostart = not user_stopped
                if status == "kész" and not self.seed_forever:
                    # A „kész" itt azt jelenti, hogy a MEGOSZTÁSI ARÁNY is
                    # teljesült – a felhasználó pedig épp azt kérte, hogy addig
                    # seedeljen, ne tovább. Ilyenkor a sorban marad (látja és
                    # kézzel újraindíthatja), de magától NEM kezd újra seedelni.
                    # Enélkül minden programindítás újraindítaná a megosztást,
                    # szemben a beállításával.
                    autostart = False
            else:
                # a leállított elemeket NEM indítjuk újra magától; a többi
                # (letöltés/várakozik) folytatható, az ütemezett az idejére vár
                autostart = status != "leállítva"
            # SEEDELŐ torrent: az adat már kész a lemezen, de a .aria2 vezérlő-
            # fájl a befejezéskor eltűnt. Újra hozzáadva az aria2 „a fájl már
            # létezik"-et dobna, és a seedelés némán megszakadna – ami akár
            # tracker-kizárást is okozhat. Ezért induláskor AUTOMATIKUSAN
            # ellenőrzés+seed (verify) módban tesszük vissza: az aria2 leellenőrzi
            # a meglévő fájlt és MAGÁTÓL folytatja a seedelést, kérdés nélkül.
            # A „kész" is ide tartozik: a készre töltött torrent adata megvan a
            # lemezen, vezérlőfájl nélkül – ugyanaz a helyzet, mint a seedelőnél.
            verify = bool(r.get("verify", False)) or (
                kind == "torrent" and status in ("seedelés", "kész"))
            job = self.add(
                url, kind=r.get("kind"), out_dir=r.get("out_dir"),
                audio_only=r.get("audio_only"),
                start_at=r.get("start_at"),
                overwrite=bool(r.get("overwrite", False)),
                verify=verify,
                autostart=autostart)
            job.user_stopped = user_stopped
            if r.get("filename"):
                job.progress.filename = r["filename"]
            restored.append(job)
        return restored

    def resume_summary(self, restored: list[Job]) -> str:
        """Egy MONDAT a folytatott torrentekről – nem kérdés, közlés.

        A torrentet nem kérdezzük meg, csak elmondjuk: „2 torrent folytatódik:
        1 letöltés, 1 megosztás." Vakon egy lista végigléptetése ehhez sok."""
        torrentek = [j for j in restored if j.kind == "torrent"]
        if not torrentek:
            return ""
        megoszt = sum(1 for j in torrentek
                      if j.progress.status in ("seedelés", "kész")
                      or j.verify)
        tolt = len(torrentek) - megoszt
        reszek = []
        if tolt:
            reszek.append("%d letöltés" % tolt)
        if megoszt:
            reszek.append("%d megosztás" % megoszt)
        return "%d torrent folytatódik: %s." % (len(torrentek),
                                                ", ".join(reszek))

    # ---- vezérlés -----------------------------------------------------

    def stop(self, job: Job, felhasznaloi: bool = True) -> None:
        """Leállítás. `felhasznaloi=True` = a FELHASZNÁLÓ akarta.

        A kettő közti különbség az MK1 lényege: a kilépéskori leállítás nem
        szándék, hanem takarítás. A szándékot NEM a státuszszóból olvassuk
        vissza – az mindkét esetben „leállítva" lesz –, hanem itt jegyezzük fel.
        """
        if felhasznaloi:
            job.user_stopped = True
            job.next_retry_at = None        # kézi leállítás: nincs újrapróba
        if job.downloader is not None:
            job.downloader.stop()
        elif job.progress.status in ("várakozik", "ütemezve"):
            job.progress.status = "leállítva"
        self._save()

    def stop_all(self, felhasznaloi: bool = True) -> None:
        """`felhasznaloi=False`: kilépéskori takarítás (lásd `stop`)."""
        for job in self.jobs:
            self.stop(job, felhasznaloi=felhasznaloi)

    # Meddig várunk kilépéskor a futó letöltőszálakra. Az aria2 RPC-időkorlátja
    # 15 másodperc, de a felhasználót nem várakoztatjuk annyit egy bezárásnál:
    # 6 másodperc alatt a szálak a szokásos esetben bőven megállnak.
    LEALLAS_VARAKOZAS = 6.0

    def varj_leallasra(self, masodperc: float = None) -> bool:
        """Megvárja, hogy a futó letöltőszálak TÉNYLEG megálljanak (MK8).

        **Miért kell.** Kilépéskor eddig ez történt: `stop_all()` beállította a
        leállítás-jelzőt, majd AZONNAL jött a `close()` és az aria2 kilövése —
        a torrent-szál viszont másodpercenként néz a jelzőre, és épp egy
        `tellStatus` hívás közepén lehetett. Az alóla kirántott aria2 kivételt
        dobott, amit a szál HIBÁNAK könyvelt el, a `finally: self._save()` pedig
        a `close()` UTÁN még egyszer kimentette a sort — immár „hiba"
        státusszal.

        **A felhasználó ebből annyit lát, hogy a következő indításkor a torrent
        hibás.** Az MK6 óta ez rosszabb: az F6 oda is küldi, egy nem létező
        hibához. Egy sima bezárásból így lett volna teendő.

        Igaz, ha minden szál megállt; hamis, ha lejárt az idő."""
        hatarido = time.monotonic() + float(
            self.LEALLAS_VARAKOZAS if masodperc is None else masodperc)
        while time.monotonic() < hatarido:
            if not any(j.progress.status in ("letöltés", "seedelés",
                                             "előkészítés")
                       for j in list(self.jobs)):
                return True
            time.sleep(0.2)
        return False

    def start(self, job: Job) -> None:
        """Kézi (újra)indítás. Ez a `stop()` párja: visszavonja a felhasználói
        leállítást, és nullázza az újrapróba-számlálót.

        Enélkül a kézzel leállított torrent VÉGLEG leállt volna: a `user_stopped`
        örökre igaz marad, és a `restore()` sosem indítaná el többé."""
        job.user_stopped = False
        job.retries = 0
        job.next_retry_at = None
        job.downloader = None
        job.submitted = False
        p = job.progress
        p.error = ""
        p.status = "várakozik"
        self._launch(job)
        self._save()

    def takarithato(self, job: Job) -> list:
        """A jobhoz tartozó félkész fájlok (.part és .sdlstate) – MK3.

        **Az azonosítás elsősorban az állapotfájlban tárolt URL alapján
        történik, nem névegyezéssel.** Két letöltés célneve könnyen ütközhet
        (`video.mp4` mindenhol van), és egy törléskor a MÁSIK letöltés
        félkész fájlját kitörölni olyan kár, amit nem lehet visszacsinálni.

        Az állapotfájl nélküli, csupasz `.part` csak akkor kerül a listára, ha
        a neve pontosan ezé a letöltésé: a régi (MK3 előtti) egyszálú
        letöltések nem hagytak állapotfájlt, azoknak ez az egyetlen esélyük."""
        mappa = Path(job.out_dir or ".")
        talalt: list = []
        if not mappa.is_dir():
            return talalt
        try:
            allapotok = sorted(mappa.glob("*.sdlstate"))
        except OSError:
            allapotok = []
        for sp in allapotok:
            try:
                adat = json.loads(sp.read_text())
            except (OSError, ValueError):
                continue
            if adat.get("url") != job.url:
                continue
            talalt.append(sp)
            part = sp.with_suffix("")          # …kit.sdlstate → …kit
            part = part.with_suffix(part.suffix + ".part")
            if part.exists():
                talalt.append(part)
        nev = (job.progress.filename or "").strip()
        if nev:
            csupasz = mappa / (nev + ".part")
            if csupasz.exists() and csupasz not in talalt:
                talalt.append(csupasz)
        return talalt

    def remove(self, job: Job, fajlokat_is: bool = False) -> list:
        """Eltávolítja a sorból (leállítja, ha fut).

        `fajlokat_is=True` esetén a félkész fájlokat is törli. **Ez alapból
        KIKAPCSOLT és marad is:** a sorból kivétel és a letöltött adat
        megsemmisítése két különböző szándék, és a másodikat nem szabad az
        elsőből következtetni. A hívó (felület vagy CLI) kérdezze meg.

        Visszaadja azoknak a fájloknak a listáját, amiket NEM sikerült
        törölni – hallgatni róla ugyanaz a hiba volna, mint eddig: a
        felhasználó azt hinné, takarítottunk."""
        self.stop(job)
        maradt: list = []
        if fajlokat_is:
            # a letöltőszál még írhat: megvárjuk, amíg tényleg megáll,
            # különben a törlés után újra létrejönne a fájl
            hatarido = time.monotonic() + 5.0
            while (job.progress.status == "letöltés"
                   and time.monotonic() < hatarido):
                time.sleep(0.2)
            for ut in self.takarithato(job):
                try:
                    ut.unlink()
                except OSError:
                    maradt.append(ut)
        with self._lock:
            if job in self.jobs:
                self.jobs.remove(job)
        self._save()
        return maradt

    def resolve_conflict(self, job: Job, mode: str) -> Job:
        """A 'fájl már létezik' ütközés feloldása ugyanazon az elemen.
        mode: 'overwrite' = felülírás, 'verify' = ellenőrzés + megosztás."""
        # MK3: a job mezőinek átírása ZÁR ALATT. A `_tick` szál ugyanezeket
        # olvassa, és félig átírt állapotot látva vagy hibát mondana egy
        # induló elemre, vagy kétszer indítaná el. A `_launch()` és a
        # `_save()` a záron KÍVÜL marad – azok maguk is zárat kérnek.
        with self._lock:
            job.overwrite = (mode == "overwrite")
            job.verify = (mode == "verify")
            job.downloader = None
            job.submitted = False
            p = job.progress
            p.conflict = False
            p.error = ""
            p.status = "várakozik"
            p.total = 0
        p.nullaz()
        self._launch(job)
        self._save()
        return job

    def wait(self) -> None:
        self.pool.shutdown(wait=True)

    def close(self) -> None:
        self._closing.set()
        self._save()

    @property
    def active(self) -> bool:
        return any(j.progress.status in
                   ("várakozik", "ütemezve", "előkészítés", "letöltés",
                    "seedelés")
                   for j in self.jobs)
