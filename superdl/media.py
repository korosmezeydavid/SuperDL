"""Médiaoldalak letöltése a yt-dlp könyvtárral.

A yt-dlp több ezer oldalt támogat (YouTube, Vimeo, SoundCloud, Twitch,
közmédia-oldalak stb.). A fragmens-alapú streameket több szálon tölti le
(concurrent_fragment_downloads). Csak olyan tartalmat tölts le, amelyhez
jogod van!
"""

import threading
from urllib.parse import parse_qs, urlparse

from .segment import Progress
# MK6: a hibaszöveg-fordítás átköltözött a `hibaszoveg.py`-ba, hogy
# MINDEN motor elérje, ne csak a yt-dlp. Itt visszaimportáljuk, mert
# a modul több helyen használja – és mert a `media.friendly_error`
# néven hívott kód (tesztek, searchwin) továbbra is működjön.
from .hibaszoveg import (friendly_error, _is_bot_check,  # noqa: F401
                        _is_cookie_error, _looks_offline)


def _prefers_single_video(url: str) -> bool:
    """Igaz, ha az URL EGY KONKRÉT videóra mutat (van `v=` azonosító, vagy
    youtu.be/<id> alak). Ilyenkor CSAK azt a videót töltjük le akkor is, ha a
    linken egy `list=` lóg – ez lehet YouTube Rádió/Mix (`list=RD…`,
    `start_radio=1`, gyakorlatilag VÉGTELEN) vagy sima lejátszási lista. Enélkül
    a yt-dlp a teljes listát elkezdené lehúzni (ezt jelezték: „egy szóló videóra
    kattintok, mégis mindent lekapkod egy mappába”).

    Tiszta lista-URL (pl. `playlist?list=…`, NINCS videó-azonosító) → False, azt
    SZÁNDÉKOSAN egész listaként töltjük (mappa + sorszám)."""
    try:
        u = urlparse(url)
    except (ValueError, TypeError):
        return False
    host = (u.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host in ("youtu.be", "y2u.be"):     # youtu.be/<VIDEOID> – az út a videó
        return len(u.path.strip("/")) > 0
    return bool(parse_qs(u.query).get("v"))  # …/watch?v=<VIDEOID>


class _CollectingLogger:
    """yt-dlp-naplózó, ami az ignoreerrors módban ELNYELT hibákat összegyűjti
    (különben a kihagyott elemek hibája némán elveszne, és nem tudnánk
    süti-/bot-újrapróbát indítani vagy érthető üzenetet adni)."""

    def __init__(self):
        self.errors: list[str] = []

    def debug(self, m):
        pass

    def info(self, m):
        pass

    def warning(self, m):
        pass

    def error(self, m):
        if m:
            self.errors.append(str(m))


def _count_entries(info) -> tuple[int, int]:
    """(sikeres, hibás) elemszám egy yt-dlp eredményből. Egyedi videónál
    (1, 0) sikernél, (0, 1) bukásnál; lejátszási listánál az elemek szerint."""
    if not info:
        return (0, 1)
    if isinstance(info, dict) and "entries" in info:
        entries = list(info.get("entries") or [])
        ok = sum(1 for e in entries if e)
        return (ok, len(entries) - ok)
    return (1, 0)


def is_media_url(url: str) -> bool:
    """Igaz, ha a yt-dlp-nek van dedikált kinyerője az URL-hez."""
    import yt_dlp.extractor

    for ie in yt_dlp.extractor.gen_extractor_classes():
        if ie.IE_NAME == "generic":
            continue
        if ie.suitable(url):
            return True
    return False


# a yt-dlp-nek átadható hangkodek-azonosítók
AUDIO_FORMATS = ("mp3", "m4a", "opus", "flac", "wav", "aac", "vorbis")
# konténerek, amikbe a videót össze lehet fűzni
VIDEO_FORMATS = ("mp4", "mkv", "webm")


class MediaDownloader:
    def __init__(self, url: str, out_dir: str, connections: int = 8,
                 audio_only: bool = False, fmt: str | None = None,
                 progress: Progress | None = None, limit_bps: int = 0,
                 audio_format: str = "mp3", video_format: str | None = None,
                 audio_bitrate: str = "192", audio_samplerate: str = "",
                 cookies_browser: str | None = None,
                 cookies_file: str | None = None,
                 playlist_folders: bool = True):
        self.url = url
        # A célmappa VEZETŐ/ZÁRÓ szóközét levágjuk: Windowson a „ C:\\…" (vezető
        # szóközzel) érvénytelen útvonal → WinError 123, és minden letöltés
        # elhasal (pl. a podcast-epizódoké, ha a beállított mappában bennragadt
        # egy szóköz). Így a mentett/begépelt szóköz sem tör el semmit.
        self.out_dir = str(out_dir).strip()
        self.connections = connections
        self.audio_only = audio_only
        self.fmt = fmt
        # lejátszási listát külön, a lista nevével ellátott mappába,
        # sorszámozva ment (01 - Cím, 02 - Cím, ...)
        self.playlist_folders = playlist_folders
        self.audio_format = (audio_format or "mp3").lower()
        self.video_format = (video_format or "").lower() or None
        self.audio_bitrate = str(audio_bitrate or "192").strip()
        self.audio_samplerate = str(audio_samplerate or "").strip()
        # bejelentkezés/sütik: böngészőből vagy cookies.txt fájlból
        self.cookies_browser = (cookies_browser or "").lower() or None
        self.cookies_file = cookies_file or None
        self.progress = progress or Progress()
        self.limit_bps = limit_bps
        self._stop = threading.Event()
        self._finished = False        # a letöltés VALÓBAN befejeződött-e (hook)

    def stop(self) -> None:
        self._stop.set()

    def _retry_with_browser_cookies(self, opts: dict, _download):
        """A YouTube bot-ellenőrzésekor sorra próbáljuk a gépen MEGTALÁLT
        böngészők bejelentkezett sütijeit, és az első működővel térünk vissza
        (None, ha egyik sem segít). Jogtiszta: a SAJÁT böngésződ munkamenete a
        SAJÁT letöltéseidhez."""
        from .cookies import available_browsers
        for br in available_browsers():
            o2 = dict(opts)
            o2["cookiesfrombrowser"] = (br,)
            o2.pop("cookiefile", None)
            try:
                info = _download(o2)
            except Exception:
                continue                       # ez a böngésző nem jó → következő
            if info:
                self.cookies_browser = br      # bookkeeping a futó letöltéshez
                return info
        return None

    def _retry_with_tv_client(self, opts: dict, _download):
        """UTOLSÓ ESÉLY bot-ellenőrzésnél: a yt-dlp „tv_embedded" lejátszó-
        kliensével próbálkozunk (a beágyazott TV-s felület ellenőrzése enyhébb;
        NINCS az alapértelmezett kliens-listában). Kizárólag akkor fut, amikor
        minden más már elbukott, és hibánál None-t ad vissza – így SOSEM adhat
        rosszabb hibaüzenetet az eredetinél (a sima „tv" kliens pl. egyes
        videóknál DRM-es streamet kap, ezért azt nem használjuk)."""
        o2 = dict(opts)
        ea = dict(o2.get("extractor_args") or {})
        yt = dict(ea.get("youtube") or {})
        yt["player_client"] = ["tv_embedded"]
        ea["youtube"] = yt
        o2["extractor_args"] = ea
        try:
            return _download(o2) or None
        except Exception:
            return None

    def _hook(self, d: dict) -> None:
        if self._stop.is_set():
            raise KeyboardInterrupt
        p = self.progress
        if d["status"] == "downloading":
            p.status = "letöltés"
            p.total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            with p._lock:
                p.downloaded = d.get("downloaded_bytes") or 0
            p.speed = d.get("speed") or 0.0
            p.filename = d.get("info_dict", {}).get("title", "") or p.filename
        elif d["status"] == "finished":
            self._finished = True        # a fájl VALÓBAN elkészült (nem hamis)
            with p._lock:
                p.downloaded = p.total or p.downloaded

    def _letoltes_kesz(self, info) -> bool:
        """Igaz, ha a letöltés VALÓBAN befejeződött: a progress-hook 'finished'-t
        jelzett, vagy létezik (és nem üres) a yt-dlp által jelzett végső fájl.
        `ignoreerrors` mellett a megszakadt letöltés is visszaad info-szótárt
        fájl nélkül – ezt NEM szabad sikernek venni (ez volt a hamis-siker bug)."""
        if getattr(self, "_finished", False):
            return True
        import os
        try:
            for rd in (info.get("requested_downloads") or []):
                fp = rd.get("filepath") or rd.get("_filename")
                if fp and os.path.exists(fp) and os.path.getsize(fp) > 0:
                    return True
        except Exception:
            pass
        return False

    def _ffmpeg_progress(self, done: int, total: int) -> None:
        p = self.progress
        p.status = "előkészítés"
        p.filename = "Átalakító (ffmpeg) letöltése – egyszeri"
        p.total = total
        with p._lock:
            p.downloaded = done

    def run(self) -> str:
        import yt_dlp
        from . import ffmpeg as ffmpeg_mod

        if self.audio_only:
            fmt = "bestaudio/best"
        elif self.video_format == "mp4" and not self.fmt:
            # MP4 előnyben: a legjobb MP4-barát sávok (H.264/m4a), hogy a
            # legtöbb esetben átkódolás nélkül, sima MP4-et kapjunk
            fmt = ("bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/"
                   "bestvideo*+bestaudio/best")
        else:
            fmt = self.fmt or "bestvideo*+bestaudio/best"

        base = str(self.out_dir)
        # tiszta fájlnév: NINCS [videó-azonosító] a végén (a felhasználók
        # zavarónak találták). Listánál a sorszám marad (a sorrendhez hasznos).
        if self.playlist_folders:
            # lista esetén: <mappa>/<lista neve>/01 - Cím.kit
            # egyedi videónál a lista-mező üres, így marad a fő mappában
            outtmpl = (base + "/%(playlist_title|)s/"
                       "%(playlist_index&{:02d} - |)s%(title)s.%(ext)s")
        else:
            outtmpl = base + "/%(title)s.%(ext)s"

        opts = {
            "format": fmt,
            "outtmpl": outtmpl,
            # EGY konkrét videóra mutató linknél (v=… vagy youtu.be/<id>) CSAK azt
            # a videót töltjük, akkor is, ha egy Rádió/Mix vagy lejátszási lista
            # (list=…) lóg rajta – különben a yt-dlp az egész (mixnél végtelen)
            # listát lehúzná egy mappába. Tiszta lista-URL-nél (nincs v=) marad a
            # szándékos teljes lista.
            "noplaylist": _prefers_single_video(self.url),
            "concurrent_fragment_downloads": self.connections,
            "progress_hooks": [self._hook],
            "noprogress": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 5,
            "fragment_retries": 5,
            # egy hibás/elérhetetlen elem NE állítsa meg a lejátszási lista
            # többi elemét – a kihagyott elemek hibáit a _CollectingLogger fogja
            "ignoreerrors": True,
        }
        if self.limit_bps:
            opts["ratelimit"] = self.limit_bps

        # bejelentkezés/sütik: a fiókod mögötti (korhatáros, tagsági,
        # régiózárt) tartalmakhoz – a böngésződ munkamenetéből vagy fájlból
        if self.cookies_browser:
            opts["cookiesfrombrowser"] = (self.cookies_browser,)
        elif self.cookies_file:
            # a kiegészítővel exportált cookies.txt gyakran hibás (hiányzó
            # Netscape-fejléc, BOM, JSON-export) → normalizáljuk; ha tényleg
            # nem használható, ÉRTHETŐ hibát adunk (ne a yt-dlp homályos
            # „does not look like a Netscape format" üzenetét)
            from .cookies import prepare_cookiefile, CookieFileError
            try:
                opts["cookiefile"] = prepare_cookiefile(self.cookies_file)
            except CookieFileError as e:
                self.progress.status = "hiba"
                self.progress.error = str(e)
                raise

        # ffmpeg szinte minden médialetöltéshez kell: hangkivonás,
        # formátum-átkódolás, ÉS a videó+hang sávok ÖSSZEFŰZÉSE (a YouTube
        # külön sávban adja a képet és a hangot). Ezért MINDIG biztosítjuk –
        # ha nincs a gépen, egyszer automatikusan letöltődik. (Korábban tiszta
        # videónál nem töltöttük le → „ffmpeg is not installed" merge-hiba.)
        ff_dir = ffmpeg_mod.find_ffmpeg() and ffmpeg_mod.ffmpeg_dir()
        if not ff_dir:
            ff_dir = ffmpeg_mod.ensure_ffmpeg(self._ffmpeg_progress)
        if ff_dir:
            opts["ffmpeg_location"] = ff_dir

        if self.audio_only:
            codec = self.audio_format if self.audio_format in AUDIO_FORMATS \
                else "mp3"
            if ff_dir:
                pp = {"key": "FFmpegExtractAudio", "preferredcodec": codec}
                if codec not in ("flac", "wav"):     # veszteségmentesnél nincs
                    pp["preferredquality"] = self.audio_bitrate
                opts["postprocessors"] = [pp]
                if self.audio_samplerate:            # pl. 44100 / 48000 Hz
                    opts["postprocessor_args"] = {
                        "extractaudio": ["-ar", self.audio_samplerate]}
            else:
                # ffmpeg nélkül a natív hangsáv jön le (nincs átkódolás)
                self.progress.error = ("ffmpeg nélkül a hang az eredeti "
                                       "formátumában (nem MP3) töltődik le")
        elif self.video_format in VIDEO_FORMATS and ff_dir:
            opts["merge_output_format"] = self.video_format

        errlog = _CollectingLogger()
        opts["logger"] = errlog

        self.progress.status = "letöltés"
        self.progress.connections = self.connections

        def _download(o):
            errlog.errors.clear()
            self._finished = False            # minden próba friss „befejezett" jelzővel
            with yt_dlp.YoutubeDL(o) as ydl:
                info = ydl.extract_info(self.url, download=True)
            # ignoreerrors módban a TELJES bukás nem dob kivételt (None vagy
            # csupa-None elem) → mi alakítjuk kivétellé, hogy a süti-/bot-
            # újrapróba és az érthető hibaüzenet a megszokott ágon menjen
            if _count_entries(info)[0] == 0:
                raise RuntimeError("; ".join(errlog.errors)
                                   or "a letöltés nem sikerült")
            return info

        had_cookies = bool(opts.get("cookiesfrombrowser")
                           or opts.get("cookiefile"))
        try:
            try:
                info = _download(opts)
            except KeyboardInterrupt:
                self.progress.status = "leállítva"
                return ""
            except Exception as e:
                msg = str(e)
                # a beállított böngésző sütijét nem sikerült beolvasni (fut a
                # böngésző / App-Bound titkosítás) → előbb próbáljunk MÁS
                # telepített böngészőt, és csak utána sütik nélkül (a nyilvános
                # tartalomhoz). Így nem áll meg azonnal a „failed to load cookies"-nál.
                if had_cookies and _is_cookie_error(msg):
                    info = self._retry_with_browser_cookies(opts, _download)
                    if info is None:
                        opts.pop("cookiesfrombrowser", None)
                        opts.pop("cookiefile", None)
                        info = _download(opts)
                # PLUSZ: a YouTube bot-ellenőrzésénél két automatikus mentőöv,
                # mielőtt feladnánk: (1) ha nem volt beállítva süti, a gépen
                # talált bejelentkezett böngészők sütijei; (2) UTOLSÓ ESÉLYKÉNT
                # a yt-dlp „tv_embedded" lejátszó-kliense (a beágyazott TV-s
                # felület ellenőrzése enyhébb; élesben igazoltan ad formátumot).
                # Ha a mentőöv is elbukik, az EREDETI bot-check hibát adjuk
                # tovább (a friendly_error arra ad pontos tanácsot).
                elif _is_bot_check(msg):
                    info = None
                    if not had_cookies:
                        info = self._retry_with_browser_cookies(opts, _download)
                    if info is None:
                        info = self._retry_with_tv_client(opts, _download)
                    if info is None:
                        raise
                else:
                    raise
            ok, failed = _count_entries(info)
            # HAMIS SIKER ELLEN: egyedi videónál (nem lejátszási lista) a letöltés
            # CSAK akkor „kész", ha a fájl VALÓBAN elkészült. `ignoreerrors` mellett
            # a megszakadt letöltés (pl. a szerver ejti a kapcsolatot egy nagy
            # fájlnál) info-szótárt ad vissza kivétel nélkül, fájl nélkül – ezt
            # eddig sikernek vettük. Mostantól ilyenkor ÉRTHETŐ hibát adunk.
            is_lista = isinstance(info, dict) and "entries" in info
            if not is_lista and not self._letoltes_kesz(info):
                raise RuntimeError("a letöltés megszakadt, a fájl nem készült "
                                   "el teljesen – próbáld újra")
            self.progress.status = "kész"
            if isinstance(info, dict) and "entries" in info:
                # lejátszási lista: hallható összegzés (hány jött le, mennyi maradt)
                summary = f"Lejátszási lista: {ok} elem letöltve"
                if failed:
                    summary += f", {failed} kihagyva (hibás vagy elérhetetlen)"
                self.progress.filename = summary
                return summary
            title = (info.get("title") if isinstance(info, dict) else "") \
                or self.url
            self.progress.filename = title
            return title
        except KeyboardInterrupt:
            self.progress.status = "leállítva"
            return ""
        except Exception as e:
            self.progress.status = "hiba"
            self.progress.error = friendly_error(str(e))
            raise
