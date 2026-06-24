# SuperDL – Moduláris „plug-and-play" architektúra TERVRAJZ
(v1 – 2026-06-24, tervezési fázis, KÓD NÉLKÜL. Szombati kezdéshez.)

## 0. Alapelvek és őszinte kényszerek
- PyInstaller-frozen app → a **Core bundle-öli a közös runtime-ot**: Python + wxPython
  + közös libek (requests, bs4, ebooklib, pypdf, docx, feedparser…) + a **közös
  szolgáltatások**: letöltőmotor, self-voice, self-update, AI-kliens, store.
- A **modulok TISZTA PYTHON** feature-csomagok, amik erre a runtime-ra épülnek.
- A nagy **binárisok download-on-demand** a Core „toolmanager"-én át (ffmpeg/ffprobe,
  BASS+bassmix/enc, pandoc, tesseract, aria2, espeak) – a meglévő `ffmpeg.ensure` mintára.
- Következmény: a „tiny core" reálisan ~100 MB (a runtime miatt). A nyereség nem a
  méret, hanem a **moduláris kód + szelektív telepítés + független frissítés**.
- A program MINDEN iterációban KIADHATÓ marad (a régi menüpontok megmaradnak, amíg a
  megfelelő modul el nem készül).

## 1. Futásidejű könyvtárszerkezet (a felhasználónál)
```
~/.superdl/
  modules/
    <id>/ manifest.json
          <pkg>/__init__.py   (belépési pont)
    _cache/ modules_index.json, index_etag.txt
  bin/   (download-on-demand binárisok)
  ...    (a meglévő config-fájlok, DPAPI-titkok)
```

## 2. A modul-ZIP felépítése
```
manifest.json
<pkg>/__init__.py        -> register(core), unregister(core)
<pkg>/...                 (a modul kódja)
```
A modul SOHA nem importál más modult közvetlenül – csak a `core`-on át kér szolgáltatást.

## 3. manifest.json (a modulban)
```
{ "id","name","version","min_core_api","entry"(=pkg-név),"category",
  "description","requires_tools":["pandoc?"],"requires_modules":[],"author" }
```

## 4. modules.json – a TÁVOLI bolt-index (a fő repóban EGY fájl)
```
{ "schema_version":1, "core_api":"1.0",
  "modules":[ { "id","name","category","description",
    "latest":{ "version","min_core_api","url","sha256","size" } }, ... ] }
```
- Modul-ZIP-ek külön GitHub Release-ekben (tag: `mod-<id>-<version>`).
- Az index a fő repo fájlja vagy egy „modules" Release asset.

## 5. A Core↔Modul SZERZŐDÉS: CoreContext felület (CORE_API="1.0")
A Core egy `core` objektumot ad a `register(core)`-nak:
- `core.api_version`
- MENÜ: `add_menu(title)`, `add_menu_item(menu,label,callback,shortcut=None,help="")`,
  `remove_menu_item(item)`
- ABLAK: `main_frame`, `register_window(key,factory)` (egyablakos kezelés, mint most a `_xxx_win`)
- LETÖLTÉS: `downloads.add(url,**opts)->job`
- BESZÉD: `voice.speak(text)`
- AI: `ai.chat / ai.vision / ai.transcribe`
- TÁROLÁS: `store.load(name,default) / store.save(name,data)` (modul-névtérrel, DPAPI a titkokra)
- ESZKÖZÖK: `tools.ensure("ffmpeg"/"pandoc"/"tesseract",progress)->path`
- BEÁLLÍTÁS: `settings.get/set`
- ESEMÉNYEK: `events.subscribe(topic,cb) / events.publish(topic,data)` (laza csatolás)
- NAPLÓ: `log` (modulonkénti logger)
A modul a `register`-ben felépíti a menüt/ablakot a `core`-on át; az `unregister`-ben
MINDENT leszerel (a hot-reload/frissítéshez).

## 6. Modul-életciklus
felfedezés (modules/) → érvényesítés (manifest + min_core_api) → import (sys.path +
importlib) → `register(core)` → futás → `unregister(core)` → frissítéskor reload.
- Hibatűrés: a `register` try/except-ben; rossz modul naplóz + kimarad, a Core fut tovább.
- `min_core_api` > Core api → nem tölt, „frissítsd a SuperDL-t" üzenet.

## 7. Modul-bolt folyamat (AKADÁLYMENTES)
- Index (cache + offline). Lista: név, kategória, leírás, állapot (telepítve/frissíthető/elérhető).
- Telepítés: ZIP letöltés → **SHA-256 ellenőrzés** → kicsomagolás temp-be → manifest-
  érvényesítés → ATOMI áthelyezés `modules/<id>/`-be (a régi `.bak`-ba) → betöltés.
- Frissítés = telepítés, de előbb `unregister` a régiről. Eltávolítás = unregister + törlés.
- Hibánál visszagörgetés a `.bak`-ból (a self-update/.part tanulságok).

## 8. Biztonság (a Tibi-spec 20.x tanulságaival)
- Csak a hivatalos `DEFAULT_REPO` indexe; nem-hivatalos forrás → naplózás/figyelmeztetés.
- Minden ZIP **SHA-256** (index adja; a GitHub asset digesttel keresztben is).
- ZIP-bomba védelem (kicsomagolt méret-korlát), **útvonalbejárás-ellenőrzés a ZIP-entryknél**,
  URL-séma engedélylista.
- A publikálási **kulcs-szken kiterjed a modul-ZIP-ekre** (a superdl_keyscan.py a ZIP-tartalomra is).
- Opcionális kód-aláírás (Ed25519) a manifest fölött – később.

## 9. Verziózás
- `CORE_API` szemantikus ("1.0"); a modul `min_core_api`-t deklarál; a Core csak kompatibilist tölt.
- Külön: a SuperDL-verzió (self-update) és a modul-verziók.

## 10. Migráció (végig kiadható marad)
1. Bevezetjük a CoreContext-et + betöltőt ÚGY, hogy minden funkció VÁLTOZATLANUL a Core-ban marad.
2. Egy funkciót (docconvert) modulba emelünk, a Core-ban egy „shim" tölti, ha telepítve van;
   ha nincs, a boltból ajánlja.
3. Iterációnként továbbiak, mindig kiadható állapotban.

## 11. ITERÁCIÓK / MÉRFÖLDKÖVEK (összefoglaló)
- **It.0 Alapozás:** M0.1 modul-modell · M0.2 CoreContext API · M0.3 manifest · M0.4 biztonsági modell
- **It.1 Core kimozdítás:** M1.1 gui szétszedés · M1.2 betöltő · M1.3 lokális felderítés · M1.4 dinamikus menü
- **It.2 Bolt + index:** M2.1 modules.json · M2.2 akadálymentes bolt-ablak · M2.3 telepít/frissít/töröl ·
  M2.4 értesítések · M2.5 atomi telepítés+rollback
- **It.3 Funkció-modulok:** M3.1 docconvert (PILOT) · M3.2 médiaelemző · M3.3 Könyvek · M3.4 IPTV ·
  M3.5 Super M · M3.6 podcast/hírek/naptár/P2P/csengőhang/videó · M3.7 AI-eszközök
  (a LETÖLTŐMOTOR a Core-ban marad)
- **It.4 Élesítés:** M4.1 verzió-kapuk · M4.2 biztonsági audit + ZIP kulcs-szken · M4.3 diagnosztika ·
  M4.4 Core karcsúsítás

## 12. Szombati kezdés
1. Lezárjuk papíron: **M0.2 (CoreContext felület) + M0.3 (manifest) + M0.4 (modules.json séma)**.
2. Majd **M1.2 (betöltő) + M3.1 (docconvert PILOT)** párban → a teljes lánc egy igazi modullal:
   manifest → bolt → letöltés → SHA-256 → dinamikus betöltés → register.
```
```
```
```
```
```
```
```
```
```
