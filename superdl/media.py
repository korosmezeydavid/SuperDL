"""Médiaoldalak letöltése a yt-dlp könyvtárral.

A yt-dlp több ezer oldalt támogat (YouTube, Vimeo, SoundCloud, Twitch,
közmédia-oldalak stb.). A fragmens-alapú streameket több szálon tölti le
(concurrent_fragment_downloads). Csak olyan tartalmat tölts le, amelyhez
jogod van!
"""

import threading

from .segment import Progress


def is_media_url(url: str) -> bool:
    """Igaz, ha a yt-dlp-nek van dedikált kinyerője az URL-hez."""
    import yt_dlp.extractor

    for ie in yt_dlp.extractor.gen_extractor_classes():
        if ie.IE_NAME == "generic":
            continue
        if ie.suitable(url):
            return True
    return False


class MediaDownloader:
    def __init__(self, url: str, out_dir: str, connections: int = 8,
                 audio_only: bool = False, fmt: str | None = None,
                 progress: Progress | None = None, limit_bps: int = 0):
        self.url = url
        self.out_dir = out_dir
        self.connections = connections
        self.audio_only = audio_only
        self.fmt = fmt
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

    def run(self) -> str:
        import yt_dlp

        if self.audio_only:
            fmt = "bestaudio/best"
        else:
            fmt = self.fmt or "bestvideo*+bestaudio/best"

        opts = {
            "format": fmt,
            "outtmpl": str(self.out_dir) + "/%(title)s [%(id)s].%(ext)s",
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
        if self.audio_only:
            # ffmpeg nélkül is működjön: csak akkor konvertálunk, ha van
            import shutil
            if shutil.which("ffmpeg"):
                opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]

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
            self.progress.error = str(e)
            raise
