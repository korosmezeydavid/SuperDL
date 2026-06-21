"""Podcast-felfedezés az INGYENES, KULCS NÉLKÜLI Apple/iTunes API-val.

  * kulcsszavas keresés (itunes.apple.com/search),
  * egy ország legnépszerűbb podcastjai (Apple top charts → feedUrl-ek),
  * a találatok RSS feedUrl-jére a meglévő FeedManager-rel iratkozunk fel.

Nincs API-kulcs, nincs regisztráció. A magyar (hu) bolt is támogatott.
"""

import json
import urllib.request
from dataclasses import dataclass
from urllib.parse import quote

UA = {"User-Agent": "SuperDL/3.0"}

# iTunes-bolt országkódok (a leggyakoribbak), Magyarország az alap
COUNTRIES = [
    ("Magyarország", "hu"), ("Egyesült Államok", "us"),
    ("Egyesült Királyság", "gb"), ("Németország", "de"),
    ("Ausztria", "at"), ("Franciaország", "fr"), ("Olaszország", "it"),
    ("Spanyolország", "es"), ("Hollandia", "nl"), ("Belgium", "be"),
    ("Svájc", "ch"), ("Lengyelország", "pl"), ("Csehország", "cz"),
    ("Szlovákia", "sk"), ("Románia", "ro"), ("Horvátország", "hr"),
    ("Szerbia", "rs"), ("Svédország", "se"), ("Norvégia", "no"),
    ("Dánia", "dk"), ("Finnország", "fi"), ("Írország", "ie"),
    ("Portugália", "pt"), ("Görögország", "gr"), ("Kanada", "ca"),
    ("Ausztrália", "au"), ("Japán", "jp"), ("Brazília", "br"),
    ("Mexikó", "mx"), ("India", "in"),
]


@dataclass
class Podcast:
    name: str
    author: str = ""
    feed_url: str = ""
    page_url: str = ""
    genre: str = ""

    def quality(self) -> str:                 # a listához (műfaj + szerző)
        return self.genre or ""


def _get(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _from_result(r: dict) -> Podcast | None:
    feed = r.get("feedUrl")
    if not feed:
        return None
    return Podcast(
        name=(r.get("collectionName") or r.get("trackName")
              or "(névtelen podcast)"),
        author=r.get("artistName", "") or "",
        feed_url=feed,
        page_url=r.get("collectionViewUrl", "") or "",
        genre=r.get("primaryGenreName", "") or "")


def search(term: str, country: str = "hu", limit: int = 50) -> list[Podcast]:
    """Kulcsszavas podcast-keresés a megadott boltban."""
    url = (f"https://itunes.apple.com/search?term={quote(term.strip())}"
           f"&country={country}&media=podcast&entity=podcast&limit={limit}")
    out = []
    for r in _get(url).get("results", []):
        pod = _from_result(r)
        if pod:
            out.append(pod)
    return out


def top(country: str = "hu", limit: int = 50) -> list[Podcast]:
    """Az adott ország legnépszerűbb podcastjai, feedUrl-lel.

    Az Apple top-lista csak ID-ket ad → EGYETLEN `lookup` hívással kérjük le
    az összeshez a feedUrl-t (vesszővel elválasztott ID-k)."""
    url = (f"https://rss.marketingtools.apple.com/api/v2/{country}"
           f"/podcasts/top/{limit}/podcasts.json")
    entries = _get(url).get("feed", {}).get("results", [])
    ids = [str(e.get("id")) for e in entries if e.get("id")]
    meta: dict[str, dict] = {}
    if ids:
        lu = _get(f"https://itunes.apple.com/lookup?id={','.join(ids)}"
                  f"&country={country}&entity=podcast")
        for r in lu.get("results", []):
            cid = str(r.get("collectionId") or r.get("trackId") or "")
            if cid:
                meta[cid] = r
    out = []
    for e in entries:
        r = meta.get(str(e.get("id")))
        if not r:
            continue
        pod = _from_result(r)
        if pod:
            # az élő top-listából a név/szerző gyakran pontosabb
            pod.name = e.get("name") or pod.name
            pod.author = e.get("artistName") or pod.author
            out.append(pod)
    return out
