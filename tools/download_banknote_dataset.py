#!/usr/bin/env python3
"""Download Hungarian banknote reference photos from Wikimedia Commons."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATASET_ROOT = Path(__file__).resolve().parent / "banknote_dataset"
USER_AGENT = "SuperDL-BanknoteTrainer/1.0 (accessibility app; korosmezey.david.richard@gmail.com)"

# Wikimedia Commons – current and legacy HUF series reference scans.
CURATED: dict[str, list[str]] = {
    "huf_500": [
        "https://upload.wikimedia.org/wikipedia/commons/f/f5/HUF_500_1998_obverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/4/43/HUF_500_1998_reverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/3/3a/500Ft2006front.JPG",
        "https://upload.wikimedia.org/wikipedia/commons/0/0e/HUF_500_2001_obverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/3/37/HUF_500_2001_reverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/f/fc/HUF_500_2009_obverse.png",
        "https://upload.wikimedia.org/wikipedia/commons/5/59/HUF_500_2009_reverse.png",
        "https://upload.wikimedia.org/wikipedia/commons/4/46/500_forint_elolap.png",
        "https://upload.wikimedia.org/wikipedia/commons/6/66/500_forint_hatlap.png",
    ],
    "huf_1000": [
        "https://upload.wikimedia.org/wikipedia/commons/0/04/HUF_1000_1998_obverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/d/d6/HUF_1000_1998_reverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/2/24/HUF_1000_2002_obverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/f/f5/HUF_1000_2006_obverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/f/f1/HUF_1000_2009_obverse.png",
        "https://upload.wikimedia.org/wikipedia/commons/8/8e/HUF_1000_2009_reverse.png",
        "https://upload.wikimedia.org/wikipedia/commons/5/55/HUF_1000_2018_obverse.png",
        "https://upload.wikimedia.org/wikipedia/commons/0/0b/HUF_1000_2018_reverse.png",
    ],
    "huf_2000": [
        "https://upload.wikimedia.org/wikipedia/commons/1/19/HUF_2000_1998_obverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/0/03/HUF_2000_1998_reverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/f/f8/HUF_2000_2000_obverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/2/2c/HUF_2000_2000_reverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/1/1c/HUF_2000_2002_obverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/2/2a/HUF_2000_2002_reverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/9/9e/HUF_2000_2009_obverse.png",
        "https://upload.wikimedia.org/wikipedia/commons/c/c4/HUF_2000_2009_reverse.png",
        "https://upload.wikimedia.org/wikipedia/commons/5/58/2000_HUF_2017_ob.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/b/b7/2000_HUF_2017_rev.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/4/43/Hungarian_money_2000_%28cropped%29.jpg",
    ],
    "huf_5000": [
        "https://upload.wikimedia.org/wikipedia/commons/4/42/HUF_5000_1999_obverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/d/d3/HUF_5000_1999_reverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/a/a5/HUF_5000_2005_obverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/3/33/HUF_5000_2005_reverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/a/a2/HUF_5000_2009_obverse.png",
        "https://upload.wikimedia.org/wikipedia/commons/4/4a/HUF_5000_2009_reverse.png",
        "https://upload.wikimedia.org/wikipedia/commons/7/73/5000_HUF_2017_ob.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/e/e9/5000_HUF_2017_rev.jpg",
    ],
    "huf_10000": [
        "https://upload.wikimedia.org/wikipedia/commons/f/fd/HUF_10000_1997_obverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/c/c9/HUF_10000_1997_reverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/d/d1/HUF_10000_1998_obverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/6/6f/HUF_10000_1998_reverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/2/28/10000_HUF_2008_ob.png",
        "https://upload.wikimedia.org/wikipedia/commons/4/4d/10000_HUF_2008_rev.png",
        "https://upload.wikimedia.org/wikipedia/commons/8/8b/10000_HUF_2014_ob.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/c/cc/10000_HUF_2014_rev.jpg",
    ],
    "huf_20000": [
        "https://upload.wikimedia.org/wikipedia/commons/7/78/HUF_20000_1999_obverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/2/2c/HUF_20000_1999_reverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/7/7b/HUF_20000_2004_obverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/1/1f/HUF_20000_2004_reverse.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/a/a8/20000_HUF_2009_ob.png",
        "https://upload.wikimedia.org/wikipedia/commons/5/56/20000_HUF_2009_rev.png",
        "https://upload.wikimedia.org/wikipedia/commons/8/89/20000_HUF_2015_ob.png",
        "https://upload.wikimedia.org/wikipedia/commons/c/cf/20000_HUF_2015_rev.png",
        "https://upload.wikimedia.org/wikipedia/commons/2/2f/20ezres.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/9/95/20.000Ft.png",
        "https://upload.wikimedia.org/wikipedia/commons/c/c3/20.000Ft_-1.png",
    ],
    "none": [
        "https://upload.wikimedia.org/wikipedia/commons/5/5c/Plain_white_background.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/3/3f/Fabric_texture.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/8/8d/Wood_grain_texture.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/9/9e/Grey_background.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/2/2f/Black_background.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/1/1a/Dark_wood_texture.jpg",
    ],
}


def fetch_commons_category(category: str, limit: int = 80) -> list[dict]:
    base = "https://commons.wikimedia.org/w/api.php"
    results: list[dict] = []
    continue_token: str | None = None
    while len(results) < limit:
        params = {
            "action": "query",
            "format": "json",
            "generator": "categorymembers",
            "gcmtitle": category,
            "gcmlimit": str(min(50, limit - len(results))),
            "prop": "imageinfo",
            "iiprop": "url",
        }
        if continue_token:
            params["gcmcontinue"] = continue_token
        url = base + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        pages = payload.get("query", {}).get("pages", {})
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            file_url = info.get("url")
            title = page.get("title", "")
            if file_url:
                results.append({"title": title, "url": file_url})
        if "continue" not in payload:
            break
        continue_token = payload["continue"].get("gcmcontinue")
        time.sleep(2.0)
    return results


def classify_title(title: str) -> str | None:
    t = title.lower()
    if any(x in t for x in ("reverse", "rev", "hatlap", "reverse.")):
        pass
    m = re.search(r"\b(500|1000|2000|5000|10000|20000)\b", t.replace(".", " "))
    if not m:
        m = re.search(r"\b(500|1000|2000|5000|10000|20000)ft\b", t)
    if not m:
        m = re.search(r"huf[_ ](\d+)", t)
    if not m:
        return None
    value = int(m.group(1))
    mapping = {
        500: "huf_500",
        1000: "huf_1000",
        2000: "huf_2000",
        5000: "huf_5000",
        10000: "huf_10000",
        20000: "huf_20000",
    }
    return mapping.get(value)


def download_file(url: str, dest: Path, retries: int = 5) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1024:
        return True
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            if len(data) < 512:
                return False
            dest.write_bytes(data)
            return True
        except Exception as exc:
            message = str(exc)
            if "429" in message and attempt < retries - 1:
                wait = 8 * (attempt + 1)
                print(f"  RATE {dest.name}: wait {wait}s")
                time.sleep(wait)
                continue
            print(f"  FAIL {dest.name}: {exc}")
            return False
    return False


def safe_name(url: str, index: int) -> str:
    name = url.rsplit("/", 1)[-1]
    name = urllib.parse.unquote(name)
    name = re.sub(r"[^\w.\-]+", "_", name)
    if not name:
        name = f"image_{index}.jpg"
    return name


def main() -> None:
    counts: dict[str, int] = {k: 0 for k in CURATED}

    print("Curated Wikimedia downloads...")
    for label, urls in CURATED.items():
        folder = DATASET_ROOT / label
        for i, url in enumerate(urls):
            dest = folder / safe_name(url, i)
            if download_file(url, dest):
                counts[label] += 1
                print(f"  OK {label}: {dest.name}")
            time.sleep(2.5)

    print("Commons category scan...")
    for item in fetch_commons_category("Category:Banknotes_of_Hungary,_forint,_1997", limit=100):
        label = classify_title(item["title"])
        if not label:
            continue
        folder = DATASET_ROOT / label
        dest = folder / safe_name(item["url"], counts[label])
        if download_file(item["url"], dest):
            counts[label] += 1
            print(f"  OK {label}: {dest.name}")

    print("\nDataset summary:")
    total = 0
    for label in sorted(counts):
        n = len(list((DATASET_ROOT / label).glob("*"))) if (DATASET_ROOT / label).exists() else 0
        total += n
        print(f"  {label}: {n} files")
    print(f"  TOTAL: {total} files")


if __name__ == "__main__":
    main()