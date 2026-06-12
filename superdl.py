#!/usr/bin/env python3
"""SuperDL - parancssori többszálú letöltő.

Példák:
  python superdl.py https://example.com/nagyfajl.zip
  python superdl.py -c 16 -o D:\\Letoltesek https://example.com/video.mp4
  python superdl.py --audio https://soundcloud.com/sajat/szamom
  python superdl.py -j 4 url1 url2 url3 url4
  python superdl.py --list urlek.txt
  python superdl.py --at "03:00" https://example.com/nagy.iso   (időzítés)
  python superdl.py --resume                       (félbeszakadtak folytatása)
  python superdl.py --subscribe https://pelda.hu/podcast.xml    (feliratkozás)
  python superdl.py --check-feeds                  (új epizódok letöltése)
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# a Windows-konzol alapból nem UTF-8, e nélkül a folyamatjelző elszáll
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from superdl.manager import DownloadManager, parse_when
from superdl.report import build_summary
from superdl.segment import parse_limit


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def render(jobs) -> list[str]:
    lines = []
    for j in jobs:
        p = j.progress
        name = (p.filename or j.url)[:46]
        if p.status == "letöltés":
            if p.total:
                bar_len = 24
                filled = int(bar_len * p.percent / 100)
                bar = "█" * filled + "░" * (bar_len - filled)
                lines.append(f"  {name:<48} [{bar}] {p.percent:5.1f}%  "
                             f"{human(p.speed)}/s  ({p.connections} szál)")
            else:
                lines.append(f"  {name:<48} {human(p.downloaded)}  "
                             f"{human(p.speed)}/s")
        elif p.status == "seedelés":
            lines.append(f"  {name:<48} seedelés  fel: {human(p.up_speed)}/s  "
                         f"arány: {p.ratio:.2f}  ({p.peers} peer)")
        elif p.status == "hiba":
            lines.append(f"  {name:<48} HIBA: {p.error[:60]}")
        else:
            lines.append(f"  {name:<48} {p.status}")
    return lines


def run_live(mgr) -> None:
    """Helyben frissülő folyamatjelző (látó felhasználóknak)."""
    prev_lines = 0
    while mgr.active:
        lines = render(mgr.jobs)
        if prev_lines:
            sys.stdout.write(f"\x1b[{prev_lines}A")
        for line in lines:
            sys.stdout.write("\x1b[2K" + line + "\n")
        sys.stdout.flush()
        prev_lines = len(lines)
        time.sleep(0.5)


def run_plain(mgr) -> None:
    """Képernyőolvasó-barát mód: csak akkor ír, ha érdemi változás van,
    és mindig teljes, kimondható mondatot."""
    reported: dict[int, str] = {}
    last_pct: dict[int, int] = {}
    while mgr.active:
        for j in mgr.jobs:
            p = j.progress
            name = p.filename or j.url
            if p.status == "ütemezve" and reported.get(j.id) != "ütemezve":
                reported[j.id] = "ütemezve"
                print(f"{name}: időzítve, a megadott időpontban indul.")
            if p.status in ("várakozik", "letöltés") \
                    and reported.get(j.id) == "ütemezve":
                reported[j.id] = "indul"
                print(f"{name}: az időzített letöltés most elindult.")
            if p.status == "letöltés" and p.total:
                pct = int(p.percent // 10) * 10
                if last_pct.get(j.id, -1) != pct:
                    last_pct[j.id] = pct
                    print(f"{name}: {pct} százalék kész, "
                          f"sebesség {human(p.speed)} másodpercenként.")
            if p.status == "seedelés" and reported.get(j.id) != "seedelés":
                reported[j.id] = "seedelés"
                print(f"{name}: a letöltés kész, seedelés folyamatban. "
                      f"Leállítás: Ctrl+C.")
            if p.status in ("kész", "hiba", "leállítva") \
                    and reported.get(j.id) != p.status:
                reported[j.id] = p.status
                if p.status == "kész":
                    print(f"{name}: a letöltés elkészült.")
                elif p.status == "hiba":
                    print(f"{name}: hiba történt: {p.error}")
                    if p.conflict:
                        print("   Tipp: felülíráshoz add hozzá a --overwrite, "
                              "ellenőrzéshez és megosztáshoz a --verify-seed "
                              "kapcsolót, majd indítsd újra.")
                else:
                    print(f"{name}: a letöltés le lett állítva.")
            sys.stdout.flush()
        time.sleep(1)
    for j in mgr.jobs:
        if reported.get(j.id) is None and j.progress.status == "kész":
            print(f"{j.progress.filename or j.url}: a letöltés elkészült.")


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="superdl",
        description="Többfunkciós, többszálú letöltő (közvetlen fájlok + "
                    "médiaoldalak a yt-dlp révén). Csak legálisan letölthető "
                    "tartalomhoz használd!")
    ap.add_argument("urls", nargs="*", help="letöltendő URL-ek")
    ap.add_argument("--list", metavar="FÁJL",
                    help="URL-lista fájlból (soronként egy)")
    ap.add_argument("-o", "--out", default="Letoltesek",
                    help="célmappa (alapértelmezés: Letoltesek)")
    ap.add_argument("-c", "--connections", type=int, default=8,
                    help="kapcsolatok/szálak száma letöltésenként (alap: 8)")
    ap.add_argument("-j", "--parallel", type=int, default=3,
                    help="egyszerre futó letöltések száma (alap: 3)")
    ap.add_argument("--audio", action="store_true",
                    help="médiaoldalról csak a hangot tölti le")
    ap.add_argument("--file", action="store_true", dest="force_file",
                    help="kényszerített közvetlen fájlletöltés (yt-dlp nélkül)")
    ap.add_argument("-l", "--limit", default="0", metavar="SEBESSÉG",
                    help="közös sebességkorlát, pl. 2M vagy 500K (alap: nincs)")
    ap.add_argument("--seed-ratio", type=float, default=1.0, metavar="ARÁNY",
                    help="torrent seedelés eddig a megosztási arányig; "
                         "0 = nincs seedelés (alap: 1.0)")
    ap.add_argument("--overwrite", action="store_true",
                    help="torrent: a már létező cél fájl felülírása")
    ap.add_argument("--verify-seed", action="store_true",
                    help="torrent: a már létező fájl ellenőrzése és megosztása")
    ap.add_argument("--plain", action="store_true",
                    help="képernyőolvasó-barát kimenet: folyamatjelző sáv "
                         "helyett sima szöveges állapotsorok")
    ap.add_argument("--at", metavar="IDŐ",
                    help="időzített indítás, pl. '03:00', '+2h', "
                         "'2026-06-12 03:00'")
    ap.add_argument("--resume", action="store_true",
                    help="a korábban félbeszakadt letöltések folytatása")
    ap.add_argument("--subscribe", metavar="FEED",
                    help="feliratkozás podcast/RSS-csatornára (URL)")
    ap.add_argument("--unsubscribe", metavar="FEED",
                    help="feliratkozás megszüntetése (URL)")
    ap.add_argument("--list-subs", action="store_true",
                    help="feliratkozások listázása")
    ap.add_argument("--check-feeds", action="store_true",
                    help="feliratkozások ellenőrzése, új epizódok letöltése")
    ap.add_argument("--speak", action="store_true",
                    help="a záró összefoglalót a beszédmotor is felolvassa")
    ap.add_argument("--engines", action="store_true",
                    help="a letöltőmotorok (yt-dlp, aria2) verziójának kiírása")
    ap.add_argument("--update", action="store_true",
                    help="a letöltőmotorok frissítése a legújabb verzióra")
    args = ap.parse_args()

    if args.engines or args.update:
        from superdl import updater, selfupdate
        selfupdate.cleanup_old()
        app = selfupdate.check()
        if args.update and app.get("update"):
            print("SuperDL frissítése...")
            try:
                selfupdate.apply(app["assets"], restart=False)
                print(f"  SuperDL: letöltve a(z) {app['latest']} verzió "
                      "(a következő indításkor lép életbe).")
            except Exception as e:
                print(f"  SuperDL: hiba – {e}")
        elif app.get("latest"):
            flag = "FRISSÍTHETŐ" if app["update"] else "naprakész"
            print(f"  SuperDL (maga a program): jelenleg {app['current']}, "
                  f"legújabb {app['latest']}  [{flag}]")
        elif app.get("error"):
            print(f"  SuperDL (maga a program): {app['current']} "
                  f"({app['error']})")
        if args.update:
            print("Letöltőmotorok frissítése...")
            for c in updater.check_updates():
                if not c["update"]:
                    print(f"  {c['name']}: naprakész ({c['current']}).")
                    continue
                try:
                    fn = (updater.update_ytdlp if c["key"] == "ytdlp"
                          else updater.update_aria2)
                    v = fn()
                    print(f"  {c['name']}: frissítve erre: {v}")
                except Exception as e:
                    print(f"  {c['name']}: hiba – {e}")
        else:
            for c in updater.check_updates():
                lat = c["latest"] or "ismeretlen"
                flag = "FRISSÍTHETŐ" if c["update"] else "naprakész"
                print(f"  {c['name']}: jelenleg {c['current']}, "
                      f"legújabb {lat}  [{flag}]")
            try:
                import yt_dlp
                honnan = "frissített" if ".superdl" in (yt_dlp.__file__ or "") \
                    else "beágyazott"
                print(f"  (betöltött yt-dlp: {yt_dlp.version.__version__}, "
                      f"{honnan})")
            except Exception as e:
                print(f"  (yt-dlp betöltési hiba: {e})")
        return 0

    # ---- feliratkozás-kezelés (letöltés nélkül is) -------------------
    if args.subscribe or args.unsubscribe or args.list_subs:
        from superdl.feeds import FeedManager
        fm = FeedManager()
        if args.subscribe:
            sub = fm.subscribe(args.subscribe, out_dir=args.out,
                               audio_only=args.audio)
            print(f"Feliratkozva: {sub.title}  ({len(sub.seen)} meglévő "
                  f"epizód kihagyva, csak az újakat tölti majd le)")
        if args.unsubscribe:
            ok = fm.unsubscribe(args.unsubscribe)
            print("Leiratkozva." if ok else "Nincs ilyen feliratkozás.")
        if args.list_subs:
            if not fm.subs:
                print("Nincs feliratkozás.")
            for s in fm.subs:
                print(f"  {s.title}  [{s.feed_url}]  "
                      f"({len(s.seen)} epizód látva)")
        return 0

    limit = parse_limit(args.limit)
    start_at = parse_when(args.at) if args.at else None

    mgr = DownloadManager(args.out, parallel=args.parallel,
                          connections=args.connections,
                          audio_only=args.audio,
                          limit_bps=limit, seed_ratio=args.seed_ratio)
    print(f"Célmappa: {Path(args.out).resolve()}")

    # ---- félbeszakadtak folytatása ----------------------------------
    if args.resume:
        restored = mgr.restore()
        print(f"Folytatás: {len(restored)} korábbi letöltés visszatöltve.")

    # ---- új podcast-epizódok letöltése ------------------------------
    if args.check_feeds:
        from superdl.feeds import FeedManager
        fm = FeedManager()
        new = fm.check_all()
        print(f"Feliratkozások: {len(new)} új epizód.")
        for sub, ep in new:
            mgr.add(ep.url, out_dir=sub.out_dir or args.out,
                    audio_only=sub.audio_only)
            fm.mark_seen(sub, ep)
            print(f"  letöltésre jelölve: {ep.title}")

    urls = list(args.urls)
    if args.list:
        urls += [line.strip() for line in Path(args.list).read_text().splitlines()
                 if line.strip() and not line.startswith("#")]

    if not urls and not args.resume and not args.check_feeds:
        ap.print_help()
        return 1

    if start_at:
        import datetime
        when = datetime.datetime.fromtimestamp(start_at).strftime("%H:%M")
        print(f"Időzítve {when}-ra/-re ({len(urls)} letöltés).")
    for url in urls:
        mgr.add(url, kind="file" if args.force_file else None,
                start_at=start_at, overwrite=args.overwrite,
                verify=args.verify_seed)

    if not mgr.jobs:
        print("Nincs letölteni való.")
        mgr.close()
        return 0

    plain = args.plain or not sys.stdout.isatty()
    try:
        if plain:
            run_plain(mgr)
        else:
            run_live(mgr)
    except KeyboardInterrupt:
        print("\nLeállítás...")
        mgr.stop_all()
    mgr.wait()
    mgr.close()
    from superdl.torrent import shutdown_aria2
    shutdown_aria2()

    if not plain:
        for line in render(mgr.jobs):
            print(line)
    ok = sum(1 for j in mgr.jobs if j.progress.status == "kész")
    summary = build_summary(mgr.jobs)
    print(f"\n{summary}")
    print(f"Kész: {ok}/{len(mgr.jobs)} letöltés sikeres.")
    if args.speak:
        from superdl.speech import Speaker
        sp = Speaker()
        if sp.available:
            sp.speak(summary)
            time.sleep(min(2 + len(summary) / 12, 12))   # várjuk a felolvasást
    return 0 if ok == len(mgr.jobs) else 2


if __name__ == "__main__":
    sys.exit(main())
