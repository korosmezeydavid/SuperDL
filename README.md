# SuperDL – akadálymentes, többfunkciós, többszálú letöltő

Készítette: **Kőrösmezey Dávid** — korosmezey.david.richard@gmail.com

> A `dist\SuperDL.exe` és `dist\SuperDL-cli.exe` **önálló, terjeszthető**
> programok: a Python, a wxPython, a yt-dlp, a feedparser és az aria2 mind
> beléjük van csomagolva, és semmilyen útvonal nincs egy adott géphez kötve.
> Bármely 64 bites Windowson elindulnak telepítés nélkül; a beállítások és a
> letöltési sor a felhasználó saját mappájában jönnek létre futáskor.

Három letöltőmotor egyben:

- **Közvetlen fájlok** (zip, iso, mp4, pdf, bármi): a fájlt darabokra osztja
  és **több párhuzamos HTTP-kapcsolaton** tölti le (mint az IDM vagy az
  aria2). Megszakadt letöltés folytatható. Ha a szerver nem támogatja a
  Range kéréseket, automatikusan egyszálú módra vált.
- **Médiaoldalak** (YouTube, Vimeo, SoundCloud, Twitch és több ezer más): a
  beépített **yt-dlp** intézi, a fragmenseket szintén több szálon szedi le.
  „Csak hang" módban a **Hangformátum** is választható (MP3, M4A, OPUS,
  FLAC, WAV, AAC); az átkódoláshoz szükséges **ffmpeg**-et a program első
  alkalommal automatikusan letölti a `~/.superdl/bin` mappába.
  **Bejelentkezést igénylő videók** (korhatáros, tagsági, régiózárt) a
  **Sütik** választóval tölthetők: megadod, melyik böngésződből (Chrome,
  Firefox, Edge, Brave, Opera, Vivaldi, Chromium) vegye a bejelentkezett
  munkamenet sütijeit, vagy betöltesz egy `cookies.txt` fájlt. Jelszót nem
  tárol. Parancssorban: `--cookies-from-browser firefox`, vagy
  `--cookies cookies.txt`.
  **Lejátszási listák / albumok** (pl. YouTube és YouTube Music): a „Lista
  mappába" beállítással a program a lista nevével ellátott külön mappába
  tölti, sorszámozva (`01 - Cím`, `02 - Cím`…), így egy egész lemez magától,
  helyes sorrendben jön le. Parancssorban a `--flat` kapcsolja ki.
- **Torrentek** (magnet-link és .torrent fájl): a beépített **aria2** motor
  kezeli, DHT-vel, letöltés után a beállított megosztási arányig seedel.

A program automatikusan felismeri, melyik motor kell az adott URL-hez.

Ezen felül tud **időzíteni**, a **félbeszakadt letöltéseket folytatni**
(a már letöltött szeletek megőrzésével, program-újraindítás után is), és
**podcast/RSS-csatornákra feliratkozni**, hogy az új epizódokat magától
letöltse.

## Médiakereső (Ctrl+F)

Beépített **médiakereső** (Eszközök → Médiakereső): beírod a keresőszót, és
a program több legális forráson (YouTube, SoundCloud) keres, az eredményeket
egyetlen, egybefűzött listába téve. A „Tovább" gomb a következő 25 találatot
hozza. Minden találaton:

- **Enter** – lejátszás a beépített kis médialejátszóban (a lejátszóban a
  bal/jobb nyíl tekerés, fel/le nyíl hangerő, Ctrl+bal/jobb az ugrásköz
  váltása 5–60 mp között, szóköz szünet, Escape vissza a listához);
- **Ctrl+B** – virtuális **kosárba** (a kosár a bezárás után is megmarad);
- **Ctrl+D** – közvetlen letöltés a fő beállításokkal;
- **Ctrl+C** – az URL pontos másolása;
- helyi menü a jobb klikkre, a Menü-billentyűre és a Shift+F10-re is.

A „Kosár letöltése" gombbal a kosár teljes tartalma egyben letölthető.

> ⚠️ Csak olyan tartalmat tölts le, amelyhez jogod van (saját, szabad
> licencű, vagy az oldal felhasználási feltételei engedik)!

> Megjegyzés: a fájlmegosztó tárhelyek (pl. 1fichier, vikingfile) **nyitólapra**
> mutató, közvetett linkjeit a program nem tudja közvetlenül letölteni –
> ezek gyakran várakozást, belépést vagy ellenőrzést kérnek, amit csak a
> böngészőben lehet elvégezni. Ilyenkor a SuperDL érthető üzenetet ad, és nem
> ment használhatatlan fájlt.

## Akadálymentesség

A program kiemelt szempontja a teljes akadálymentesség:

- A grafikus felület **wxPythonban** készült, amely natív
  Windows-vezérlőket használ — az **NVDA, a JAWS és a Narrátor** hibátlanul
  felolvassa (maga az NVDA képernyőolvasó is wxPythonban íródott).
- **Minden funkció elérhető billentyűzetről**, minden mezőnek van címkéje
  és gyorsbillentyűje (Alt+aláhúzott betű).
- A letöltések elkészültéről **rendszerértesítés** és hangjelzés szól — az
  értesítéseket a képernyőolvasók maguktól felolvassák.
- **Apró hanghatások** (Letöltések → Hanghatások) jelzik a fontos
  eseményeket: találati lista megjelenése, letöltés indulása, befejezése és
  hibája. A program maga állítja elő őket; ki-be kapcsolható.
- Az **eseménynapló** (Ctrl+E) csak olvasható szövegmezőben, időbélyeggel
  őrzi a történteket, így bármikor kényelmesen visszaolvasható.
- A parancssor **--plain** kapcsolóval (vagy átirányításnál automatikusan)
  folyamatjelző sáv helyett teljes, kimondható mondatokban jelez, és csak
  érdemi változásnál ír új sort — nem árasztja el a képernyőolvasót.
- **Hangos összefoglaló** (Ctrl+J): egyetlen billentyűre teljes,
  kimondható mondatban jelenti az állapotot („Jelenleg 3 letöltés fut,
  összesen 42 százalék kész, hátralévő idő körülbelül 8 perc."). A
  képernyőolvasód a saját hangján olvassa fel az értesítésből, és a
  beépített Windows-beszédmotor (SAPI) is felmondja — ezt egyetlen másik
  letöltő sem tudja. A „Befejezés felolvasása" kapcsolóval minden elkészült
  letöltést hangosan is bemond.

### Billentyűparancsok (grafikus felület)

| Billentyű | Művelet |
|---|---|
| Ctrl+N | URL-mező fókuszálása (új letöltés) |
| Enter (URL-mezőben) | letöltés indítása |
| Ctrl+T | torrentfájl megnyitása |
| Ctrl+O | URL-lista megnyitása fájlból |
| Ctrl+R | feliratkozás podcast/RSS-csatornára |
| Ctrl+L | feliratkozások kezelése |
| Ctrl+D | letöltési lista fókuszálása |
| Ctrl+E | eseménynapló fókuszálása |
| Ctrl+J | hangos összefoglaló (mennyi van hátra) |
| Delete (a listában) | kijelölt letöltés leállítása |
| Ctrl+Shift+S | összes letöltés leállítása |
| Ctrl+M | célmappa megnyitása |
| F1 | billentyűparancsok súgója |
| Ctrl+Q | kilépés |

## Telepítés

```
pip install -r requirements.txt
```

Vagy használd a `dist` mappában lévő kész programokat telepítés nélkül:
`SuperDL.exe` (grafikus) és `SuperDL-cli.exe` (parancssori).

(Opcionális: ha az [ffmpeg](https://ffmpeg.org) telepítve van, a „csak hang"
mód MP3-ba konvertál; nélküle az eredeti hangformátumot kapod.)

## Grafikus felület

Dupla katt a `SuperDL.bat`-ra (vagy a `dist\SuperDL.exe`-re), vagy:

```
python superdl_gui.py
```

URL beillesztése → Enter. További kényelmi funkciók:

- **Vágólap figyelése**: ha bekapcsolod, a böngészőben vágólapra másolt
  hivatkozásokat magától felveszi a letöltési sorba.
- **Hivatkozás idehúzása**: a böngészőből az ablakra húzott linkeket is
  letölti.
- **Sebességkorlát**: pl. `2M` (2 MB/s) vagy `500K` — az összes letöltésre
  együttesen érvényes, így a böngészés közben sem fogy el a sávszélesség.
- **Torrentek**: magnet-linket az URL-mezőbe illesztve, .torrent fájlt a
  Ctrl+T-vel megnyitva. A „Seed-arány" mező mondja meg, meddig oszd vissza
  (1.0 = amennyit letöltöttél; 0 = letöltés után azonnal leáll). A listában
  látod a feltöltési sebességet és a megosztási arányt is.
- **Ha a torrent cél fájlja már létezik**: a program nem ír felül vakon,
  hanem érthetően megkérdezi, mit tegyen: *Kihagyom* (marad a meglévő),
  *Felülírom* (újra letölti az elejéről), vagy *Ellenőrzöm és megosztom*
  (a meglévő fájlt a torrent hash-ei alapján ellenőrzi, és onnan seedeli –
  így a már letöltött anyagot vissza tudod adni a közösségnek anélkül, hogy
  újra letöltenéd). A parancssorban: `--overwrite`, illetve `--verify-seed`.
- **Időzítés**: az „Időzítés" mezőbe írj időpontot (`03:00`), eltolást
  (`+2h`, `+90` perc) vagy teljes dátumot (`2026-06-12 03:00`), majd add hozzá
  az URL-t — a megadott időpontban indul. Üres mező = azonnali indítás.
- **Folytatás**: ha letöltés közben bezárod a programot (vagy elszáll az
  áram), újraindításkor felajánlja a félbeszakadt letöltések folytatását,
  és a már letöltött szeletektől folytatja, nem kezdi elölről.
- **Podcast/RSS** (Feliratkozások menü): iratkozz fel egy csatorna RSS-
  címére (Ctrl+R). A program 15 percenként és induláskor ellenőrzi, és az
  új epizódokat magától letölti (a régieket nem tölti újra). A
  feliratkozásokat a Ctrl+L-lel kezeled.
- **Frissítések** (Súgó → Frissítések keresése, Ctrl+U): a program a
  hivatalos forrásból ellenőrzi és felkínálja **magának a SuperDL-nek** és a
  letöltőmotoroknak (yt-dlp, aria2) az új verzióit. Naponta egyszer magától
  is ránéz, és ha van újdonság, felajánlja. A motorfrissítések a
  `~/.superdl/bin` mappába kerülnek; a SuperDL új verzióját a GitHub-
  kiadásokból tölti le, kicseréli magát, és újraindul (lásd lentebb a
  beállítást).
- **Súgó és névjegy** (Súgó menü): külön lapon a billentyűparancsok, a
  „Hogyan működik”, az „Adatkezelés és adatvédelem” (pontosan mihez fér
  hozzá a gépen), és a névjegy – minden felolvasható szövegmezőben.
- A beállításokat kilépéskor megjegyzi (`~/.superdl.json`); a letöltési
  sort és a feliratkozásokat a `~/.superdl` mappa őrzi.

## Parancssor

```
python superdl.py URL [URL...]            # automatikus motorválasztás
python superdl.py -c 16 URL               # 16 kapcsolat/letöltés
python superdl.py -j 4 url1 url2 url3     # 4 letöltés egyszerre
python superdl.py -l 2M URL               # sebességkorlát: 2 MB/s
python superdl.py --plain URL             # képernyőolvasó-barát kimenet
python superdl.py --audio URL             # médiaoldalról csak a hang
python superdl.py --file URL              # kényszerített közvetlen letöltés
python superdl.py --list urlek.txt        # URL-lista fájlból
python superdl.py -o D:\Letoltesek URL    # célmappa
python superdl.py "magnet:?xt=..."        # torrent magnet-linkről
python superdl.py fajl.torrent            # torrent .torrent fájlból
python superdl.py --seed-ratio 2.0 URL    # seedelés 2.0 arányig (0 = nincs)
python superdl.py --at "03:00" URL        # időzített indítás (vagy +2h)
python superdl.py --resume                # félbeszakadt letöltések folytatása
python superdl.py --subscribe FEED_URL    # feliratkozás podcast/RSS-re
python superdl.py --check-feeds           # új epizódok letöltése most
python superdl.py --list-subs             # feliratkozások listája
python superdl.py --speak URL             # a záró összefoglalót felolvassa
python superdl.py --engines               # a motorok verziójának kiírása
python superdl.py --update                # a motorok frissítése a legújabbra
```

## Felépítés

| Fájl | Szerep |
|---|---|
| `superdl/segment.py` | szegmentált többszálú HTTP-motor (Range, folytatás, újrapróbálás, sebességkorlát) |
| `superdl/media.py` | yt-dlp wrapper, URL-felismerés |
| `superdl/torrent.py` | torrent-motor: beágyazott aria2c vezérlése JSON-RPC-n át |
| `superdl/feeds.py` | podcast/RSS-feliratkozások (feedparser), új epizódok figyelése |
| `superdl/report.py` | felolvasható, emberi nyelvű állapot-összefoglaló |
| `superdl/speech.py` | felolvasás a Windows-beszédmotorral (SAPI), választható |
| `superdl/updater.py` | a yt-dlp és az aria2 verzió-ellenőrzése és frissítése |
| `superdl/store.py` | tartós tárolás: letöltési sor és feliratkozások (`~/.superdl`) |
| `superdl/manager.py` | letöltési sor, párhuzamos feladatok, időzítés, folytatás, sávszélesség-korlát |
| `bin/aria2c.exe` | az aria2 1.37.0 letöltőmotor (hivatalos kiadás) |
| `superdl.py` | parancssori felület (élő és képernyőolvasó-barát mód) |
| `superdl_gui.py` | akadálymentes wxPython grafikus felület |

A megszakadt szegmentált letöltések állapota `.sdlstate` fájlban tárolódik a
részfájl (`.part`) mellett – ugyanazzal az URL-lel újraindítva onnan
folytatja, ahol abbamaradt.

## Automatikus önfrissítés közzététele (fejlesztőknek)

A SuperDL képes magát frissíteni a GitHub-kiadásokból. Beállítás:

1. Hozz létre egy nyilvános GitHub-tárhelyet (pl. `felhasznalo/SuperDL`).
2. Tedd a kész `SuperDL.exe` mellé egy `repo.txt` fájlt, benne egyetlen
   sorban a tárhely: `felhasznalo/SuperDL`. (A program ezt olvassa; a
   `~/.superdl/repo.txt` vagy a `SUPERDL_REPO` környezeti változó is jó.)
3. Új verzió kiadásakor a `superdl/__init__.py`-ben emeld a `__version__`
   értékét (pl. `1.5.0`), építsd újra az exe-ket, majd a GitHubon hozz létre
   egy **Release**-t `v1.5.0` címkével, és csatold hozzá a `SuperDL.exe` és
   `SuperDL-cli.exe` fájlokat.

A telepített programok naponta ránéznek a legújabb kiadásra, és ha újabb,
felajánlják a letöltését. Windows alatt a futó exe-t a program átnevezi
(`.old.exe`), az újat a helyére teszi, és újraindul; a maradékot a következő
indításkor törli.

## Saját .exe építése

```
pip install pyinstaller
python -m PyInstaller --onefile --windowed --name SuperDL --collect-submodules yt_dlp --collect-submodules feedparser --hidden-import win32com.client --hidden-import pythoncom --hidden-import pywintypes --add-binary "bin\aria2c.exe;." superdl_gui.py
python -m PyInstaller --onefile --console --name SuperDL-cli --collect-submodules yt_dlp --collect-submodules feedparser --hidden-import win32com.client --hidden-import pythoncom --hidden-import pywintypes --add-binary "bin\aria2c.exe;." superdl.py
```
