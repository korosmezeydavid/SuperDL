"""Médiaoldalak letöltése a yt-dlp könyvtárral.

A yt-dlp több ezer oldalt támogat (YouTube, Vimeo, SoundCloud, Twitch,
közmédia-oldalak stb.). A fragmens-alapú streameket több szálon tölti le
(concurrent_fragment_downloads). Csak olyan tartalmat tölts le, amelyhez
jogod van!
"""

import threading

from .segment import Progress


def friendly_error(msg: str) -> str:
    """Ismert, gyakori hibák érthető, lépésenkénti magyar üzenete."""
    m = msg.lower()
    if "could not copy" in m and "cookie" in m:
        return ("A böngésző (Chrome/Edge) épp FUT, ezért a program nem tudja "
                "kiolvasni a sütijeit. Megoldás: zárd be a böngészőt, VAGY a "
                "Sütik beállításnál válaszd a Firefoxot, VAGY használj "
                "cookies.txt fájlt.")
    if ("dpapi" in m or "failed to decrypt" in m
            or "could not decrypt" in m):
        return ("Az újabb Chrome/Edge titkosítja a sütiket, amit egyetlen "
                "letöltő sem tud kiolvasni. Megoldás: a Sütik beállításnál "
                "válaszd a FIREFOXOT (ezt nem érinti), VAGY exportálj egy "
                "cookies.txt fájlt egy böngésző-kiegészítővel, és azt add meg.")
    return msg


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
                 cookies_browser: str | None = None,
                 cookies_file: str | None = None,
                 playlist_folders: bool = True):
        self.url = url
        self.out_dir = out_dir
        self.connections = connections
        self.audio_only = audio_only
        self.fmt = fmt
        # lejátszási listát külön, a lista nevével ellátott mappába,
        # sorszámozva ment (01 - Cím, 02 - Cím, ...)
        self.playlist_folders = playlist_folders
        self.audio_format = (audio_format or "mp3").lower()
        self.video_format = (video_format or "").lower() or None
        # bejelentkezés/sütik: böngészőből vagy cookies.txt fájlból
        self.cookies_browser = (cookies_browser or "").lower() or None
        self.cookies_file = cookies_file or None
        self.progress = progress or Progress()
        self.limit_bps = limit_bps
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

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
            with p._lock:
                p.downloaded = p.total or p.downloaded

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
        else:
            fmt = self.fmt or "bestvideo*+bestaudio/best"

        base = str(self.out_dir)
        if self.playlist_folders:
            # lista esetén: <mappa>/<lista neve>/01 - Cím [id].kit
            # egyedi videónál a lista-mező üres, így marad a fő mappában
            outtmpl = (base + "/%(playlist_title|)s/"
                       "%(playlist_index&{:02d} - |)s%(title)s [%(id)s].%(ext)s")
        else:
            outtmpl = base + "/%(title)s [%(id)s].%(ext)s"

        opts = {
            "format": fmt,
            "outtmpl": outtmpl,
            "concurrent_fragment_downloads": self.connections,
            "progress_hooks": [self._hook],
            "noprogress": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 5,
            "fragment_retries": 5,
        }
        if self.limit_bps:
            opts["ratelimit"] = self.limit_bps

        # bejelentkezés/sütik: a fiókod mögötti (korhatáros, tagsági,
        # régiózárt) tartalmakhoz – a böngésződ munkamenetéből vagy fájlból
        if self.cookies_browser:
            opts["cookiesfrombrowser"] = (self.cookies_browser,)
        elif self.cookies_file:
            opts["cookiefile"] = self.cookies_file

        # van-e szükség átkódolásra (ehhez ffmpeg kell)?
        need_ffmpeg = self.audio_only or bool(self.video_format)
        ff_dir = ffmpeg_mod.find_ffmpeg() and ffmpeg_mod.ffmpeg_dir()
        if need_ffmpeg and not ff_dir:
            # igény esetén automatikusan letöltjük az ffmpeg-et
            ff_dir = ffmpeg_mod.ensure_ffmpeg(self._ffmpeg_progress)
        if ff_dir:
            opts["ffmpeg_location"] = ff_dir

        if self.audio_only:
            codec = self.audio_format if self.audio_format in AUDIO_FORMATS \
                else "mp3"
            if ff_dir:
                pp = {"key": "FFmpegExtractAudio", "preferredcodec": codec}
                if codec not in ("flac", "wav"):     # veszteségmentesnél nincs
                    pp["preferredquality"] = "192"
                opts["postprocessors"] = [pp]
            else:
                # ffmpeg nélkül a natív hangsáv jön le (nincs átkódolás)
                self.progress.error = ("ffmpeg nélkül a hang az eredeti "
                                       "formátumában (nem MP3) töltődik le")
        elif self.video_format in VIDEO_FORMATS and ff_dir:
            opts["merge_output_format"] = self.video_format

        self.progress.status = "letöltés"
        self.progress.connections = self.connections
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
            self.progress.status = "kész"
            self.progress.filename = info.get("title", self.url)
            return info.get("title", "")
        except KeyboardInterrupt:
            self.progress.status = "leállítva"
            return ""
        except Exception as e:
            self.progress.status = "hiba"
            self.progress.error = friendly_error(str(e))
            raise
