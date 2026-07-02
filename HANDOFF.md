# SuperDL – STAFÉTABOT / átadási térkép

Ez a fájl a **közös stafétabot** Claude és bármely másik AI (pl. Grok) között.
Bármelyik AI ebből tudja, HOL van minden, HOGYAN kell buildelni és kiadni, mik a
VASSZABÁLYOK, és pontosan HOL TARTUNK. Aki dolgozik rajta, a végén **frissíti a
„JELENLEGI ÁLLAPOT" szakaszt**, aki felveszi, azt olvassa el először.

> Nyelv: a felhasználóval **magyarul**. A program teljes **akadálymentesség** (vak,
> képernyőolvasós felhasználó). **Kizárólag legális** felhasználásra készül.

---

## 0. STAFÉTA-PROTOKOLL (a lényeg)

**Felvételkor (amikor elkezdesz dolgozni):**
1. Olvasd el ezt a fájlt végig, KÜLÖNÖSEN a „JELENLEGI ÁLLAPOT" szakaszt (§6).
2. Ellenőrizd a valós állapotot a lemezen (mi épült meg, mi van kiadva) – ne csak
   a leírásnak higgy.

**Átadáskor (amikor abbahagyod):**
1. Frissítsd a §6 „JELENLEGI ÁLLAPOT"-ot: mi készült el, mi van hátra, hol a szál.
2. Írd oda a dátumot és hogy melyik AI dolgozott.

**Két VASSZABÁLY, amit AI-váltáskor is TARTANI KELL:**
- **„create maxima"** = ez a jelszó indítja a kódolást/buildet. Amíg NEM hangzik
  el, **tervezési módban maradsz** (nem írsz kódot, csak tervezel) – kreditkímélés.
- **„publikálás"** = csak EKKOR szabad GitHubra feltölteni / élesben kiadni.
  Kód/build mehet create maximára, de FELTÖLTÉS csak külön „publikálás"-ra.
- **PUBLIKÁLÁS ELŐTT KÖTELEZŐ a KULCS-SZKEN** (lásd §5.4). Soha ne adj ki olyan
  fájlt, amiben a felhasználó AI-kulcsa szerepel. Ez a #1 szabály.

---

## 1. Mi ez a projekt

**SuperDL** – akadálymentes, többfunkciós letöltő + médiaközpont Windowsra
(wxPython, Python 3.14, PyInstaller). Egy **Core** (letöltő + AI-eszközök +
futtatókörnyezet + modulrendszer) + **9 telepíthető modul** (a bővebb funkciók).
GitHub: `korosmezeydavid/SuperDL`.

---

## 2. HOL VAN MINDEN – útvonal-térkép

Minden a **`C:\Users\msn\Documents\Audacity\SuperDownloader`** mappában.

| Mi | Hol |
|----|-----|
| **Core forrás (csomag)** | `superdl\` (pl. `coremod.py` = modul-host/menük, `selfupdate.py` = önfrissítés, `searchwin.py` = Médiakereső, `store.py` = beállítás/kulcs-tár, `manager.py` = letöltéskezelő) |
| **Fő GUI belépő** | `superdl_gui.py` (a `MainFrame` osztály) |
| **CLI belépő** | `superdl.py` |
| **Verziószám** | `superdl\__init__.py` → `__version__` (most: `3.29.0`) |
| **Modulok forrása** | `modules_src\<id>\manifest.json` + `modules_src\<id>\<id>_mod\` (9 db: docconvert, konyvek, szervezes, mediatools, supermedia, iptv, radio, hangalamondas, p2p) |
| **Modul-csomagoló** | `tools\build_module.py` (ZIP + SHA + modules.json-bejegyzés) |
| **Modul-katalógus (a „bolt")** | `modules.json` (repó gyökér) – a program ebből tudja, milyen modulok/verziók vannak |
| **Build-specek** | `SuperDL.spec` (onefile GUI), `SuperDL-cli.spec` (CLI), `SuperDL-onedir.spec` (telepítőhöz) |
| **Telepítő-szkript** | `SuperDL.iss` (Inno Setup / ISCC) |
| **Kulcs-szkenner** | `tools\keyscan.py` (publikálás előtt KÖTELEZŐ) |
| **Kimenetek** | `dist\SuperDL.exe`, `dist\SuperDL-cli.exe`, `dist\SuperDL\` (onedir), `installer\SuperDL-Setup-<verzió>.exe`, `dist_modules\<id>-<verzió>.zip` |
| **Hírlevél a listának** | `C:\Users\msn\Documents\superdllistara.txt` |
| **Claude saját memóriája** | `C:\Users\msn\.claude\projects\C--Users-msn-Documents-Audacity\memory\` (ez CLAUDE-specifikus; Grok NEM éri el – ezért van EZ a HANDOFF.md a repóban) |

**Build-interpreter (FONTOS, mindig ezt használd, ne a sima `python`-t):**
`C:\Users\msn\AppData\Local\Python\pythoncore-3.14-64\python.exe`

---

## 3. Architektúra dióhéjban

- A **Core** (a nagy exe) tartalmazza: letöltő, AI-eszközök (kép/OCR/átirat…),
  a megosztott futtatókörnyezetet (ffmpeg, BASS-hangmotor, numpy, TTS), és a
  **modulrendszert** (`superdl\coremod.py` = a `WxHost`, ami a menüket/ablakokat
  adja a moduloknak; `superdl\modkit.py` = betöltő + manifest + eseménybusz).
- A **modulok** külön ZIP-ek, amiket a program a Modulkezelőből tölt le a
  `modules.json` alapján. Egy modul: `manifest.json` (gyökér) + `<id>_mod\`
  csomag `register(core)` / `unregister(core)` függvényekkel.
- **Menük (3.29.0-tól):** a Core `add_menu(cím)` = FIND-OR-CREATE (nem duplikál),
  `add_submenu(felső, almenü)` = a kategória-menü alá fűz. A modulok a
  kategóriájuk alá kerülnek: Média / Könyvek / Eszközök. A Súgó mindig utolsó.
- **CORE_API = "1.0"** (a modulok ezt várják; új host-metódusok additívak).

---

## 4. Fejlesztési ritmus

- Alapból **TERVEZÉS**: megbeszéljük mit, hogyan. Kód CSAK **„create maxima"**-ra.
- Minden mérföldkő „a kategória legjobbja, vakosan is egyszerűen" (maximalizmus).
- Modul-változás → elég **modul-kiadás** (nem kell Core-build), HA a Core-ban már
  megvan a szükséges futtatókörnyezet. Core-forrás változás → **Core-build kell**.

---

## 5. BUILD & KIADÁS – pontos lépések

Jelöld: `PY="C:\Users\msn\AppData\Local\Python\pythoncore-3.14-64\python.exe"`

### 5.1 Modul kiadása (könnyű, nincs Core-build)
1. Bumpold a `modules_src\<id>\manifest.json` `version` mezőjét.
2. `& $PY tools\build_module.py modules_src\<id>` → ZIP a `dist_modules\`-ba +
   kiírja a `modules.json`-bejegyzést (URL/SHA/méret). Frissítsd a `modules.json`
   megfelelő modul `latest` blokkját.
3. (publikáláskor) töltsd fel a ZIP-et a `mod-<id>-<verzió>` GitHub-release-tagre,
   és pushold a `modules.json`-t a repóba.

### 5.2 Core buildje (nehéz, hosszú – csak ha `superdl\`/`superdl_gui.py` változott)
yt-dlp-t FRISSÍTSD build előtt: `& $PY -m pip install -U yt-dlp`
- **GUI onefile:** `& $PY -m PyInstaller --noconfirm --clean SuperDL.spec` → `dist\SuperDL.exe` (~176 MB)
- **CLI:** `& $PY -m PyInstaller --noconfirm --clean SuperDL-cli.spec` → `dist\SuperDL-cli.exe` (~132 MB)
- **onedir (telepítőhöz):** `& $PY -m PyInstaller --noconfirm --clean SuperDL-onedir.spec` → `dist\SuperDL\`
- **Telepítő (PowerShell-ből, NEM Git-Bashből – az elrontja a /D kapcsolót):**
  `& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=3.29.0 SuperDL.iss`
  → `installer\SuperDL-Setup-3.29.0.exe`

### 5.3 Feltöltés (csak „publikálás"-ra)
- Core-release: `gh release create v<verzió> --repo korosmezeydavid/SuperDL ...`
  assetek: `SuperDL.exe`, `SuperDL-cli.exe`, `SuperDL-Setup-<verzió>.exe`, és egy
  **version-nélküli** `SuperDL-Setup.exe` másolat (a „legfrissebb" stabil linkhez).
  Stabil linkek: `releases/latest/download/SuperDL.exe` stb. → ezért kell a
  version-nélküli telepítő-alias, és a release legyen „Latest".
- Modulok: `gh release create mod-<id>-<verzió> ...` + a ZIP feltöltése.
- Végül `modules.json` push a repó `main` ágára.

### 5.4 KULCS-SZKEN (KÖTELEZŐ minden feltöltés előtt)
```
PYTHONIOENCODING=utf-8 & $PY tools\keyscan.py dist_modules superdl superdl_gui.py dist\SuperDL.exe dist\SuperDL-cli.exe
```
Kilépési kód 0 = TISZTA (kiadható). 2 = KULCS TALÁLAT → **NE PUBLIKÁLD**, keresd
meg, hol szivárog. (A szkenner a felhasználó tárolt AI/TTS-kulcsait dekódolja és
nyers bájtként keresi a fájlokban.)

---

## 6. JELENLEGI ÁLLAPOT  ⟵ EZT FRISSÍTSD MINDEN VÁLTÁSKOR

**Utolsó frissítés:** 2026-07-02 · dolgozott: Claude (Opus 4.8)

**3.29.0 KIADVA ✅ (2026-07-02).** Minden fent és ellenőrizve:
- Core release `v3.29.0` „Latest", 4 asset (SuperDL.exe, SuperDL-cli.exe,
  SuperDL-Setup-3.29.0.exe, SuperDL-Setup.exe). Stabil linkek 200-asak.
- 8 modul-release fent (mod-*-tageken); `modules.json` élő a `main`-en.
- Forrás + HANDOFF.md + tools/keyscan.py pusholva a `main`-re (commit cd13251).
- Hírlevél kiírva: `C:\Users\msn\Documents\superdllistara.txt`.
- Kulcs-szken minden kiadott fájlra: TISZTA.

**Buildelési tanulság (FONTOS a következő Core-buildhez):** a onefile
(`SuperDL.spec` → `dist\SuperDL.exe`) ÉS az onedir (`SuperDL-onedir.spec` →
`dist\SuperDL\`) NÉV-ÜTKÖZ a `dist`-ben: ha az onedirt a onefile UTÁN buildeled,
letörli a `dist\SuperDL.exe`-t. SORREND: előbb onedir + telepítő, UTOLJÁRA a
onefile GUI — vagy más `--distpath`. (Most emiatt kellett a onefile-t újraépíteni.)

**Nincs függő kiadási teendő.** A backlog a §7-ben (csak „create maxima"-ra).

---
### (archív) 3.29.0 kiadás-menete – ami lezajlott
A **3.29.0** (menü-átrendezés + javítási létra #1–#6).

**Kód: KÉSZ és verifikálva.** Tartalom (mind benne a forrásban):
- **Menü-átrendezés:** kategória-menük (Média/Könyvek/Eszközök), Súgó utolsó,
  megnyitás-hardening (az ablak tényleg előjön, nem dob vissza). `coremod.py`.
- **#1 Kosár checkout-ürítés:** a Médiakereső kosara a letöltések befejeztével
  ürül (a főablak `_on_tick`-je figyeli). `searchwin.py` + `superdl_gui.py`.
- **#2 Telepítős auto-újraindítás:** `selfupdate.py` `_swapper_script` → a .bat a
  csere után `start`-tal újraindítja az exét.
- **#3 CWI-2 kódlap:** `docconvert` – cp437-alap + 8 magyar felülírás, auto+kézi.
- **#4 Videóvágó „két marker közti rész kivágása":** `mediatools` –
  `videoedit.export_cut` + `videoeditwin._cut_section`.
- **#5 Csúszkák:** effekt/pitch csúszkák + DX8 valós idejű intenzitás
  (`BASS_FXSetParameters`, Get-then-Set). `supermedia`.
- **#6 IPTV:** belépés-állapotgép (belépés előtt tiszta képernyő, utána minden
  előjön) + kategóriák + beszélő hibák. `iptv`.

**Modul-zipek + `modules.json`: KÉSZ** a `dist_modules`-ban (mind egyezik):
docconvert 1.1.1 · mediatools 1.4.1 · supermedia 1.2.1 · iptv 1.0.1 · radio 1.0.1 ·
hangalamondas 1.0.2 · szervezes 1.2.1 · p2p 1.0.2 · **konyvek 1.0.0 (változatlan)**.

**Core 3.29.0 build – RÉSZBEN kész (a session-váltások megszakították):**
- ✅ `dist\SuperDL.exe` (176 MB) – KÉSZ
- ✅ `dist\SuperDL-cli.exe` (132 MB) – KÉSZ
- ❌ `dist\SuperDL\` onedir – **ÚJRA KELL ÉPÍTENI** (`SuperDL-onedir.spec`)
- ❌ `installer\SuperDL-Setup-3.29.0.exe` – **MÉG NINCS** (onedir után ISCC)
- ✅ Kulcs-szken a forrásra + modul-zipekre: TISZTA (2 kulcs, 217 fájl, 0 találat).
  A KÉSZ exékre a szken még hátravan (feltöltés előtt).

**A FOLYTATÁS PONTOS LÉPÉSEI (innen kell vinni):**
1. onedir build: `& $PY -m PyInstaller --noconfirm --clean SuperDL-onedir.spec`
2. Telepítő: `& "…\ISCC.exe" /DMyAppVersion=3.29.0 SuperDL.iss`
3. Version-nélküli alias: másold `SuperDL-Setup-3.29.0.exe` → `SuperDL-Setup.exe`.
4. Kulcs-szken az exékre+telepítőre (§5.4). Ha TISZTA:
5. Feltöltés: Core `v3.29.0` (4 asset) + 8 modul-tag + `modules.json` push (§5.3).
6. **Hírlevél** a `C:\Users\msn\Documents\superdllistara.txt`-be (piszkozat kész a
   Claude scratchpadjában – a tartalmat lásd a §7-ben összefoglalva).

**Backlog (a következő körökre, csak „create maxima"-ra):** lásd a §7-et.

---

## 7. Backlog / következő irányok

Ezek TERVEK, csak „create maxima"-ra épülnek:
- **IPTV 1.1.0 továbbfejlesztés:** Xtream `player_api.php` teljes hitelesítés-
  állapotgép, kategória-előbb navigáció, m3u-tartalék (Szabó Zsolt + Laci jelezte).
- **„Indító nézet" beállítás (Laci):** választható, mi jöjjön elő induláskor.
- Nagyobb roadmap-tételek (AI hangalámondás bővítés, Super M rádió-stúdió,
  asszisztens) – a Claude-memória `project-superdl-roadmap.md`-jében részletesen.

**A 3.29.0 hírlevél lényege (a listás levélhez):** Core 3.29.0 – rendrakott,
kategória-alapú menük; a Médiakereső kosara letöltés után ürül; telepítős verzió
frissítés után magától újraindul; konverter érti a régi magyar DOS-kódlapokat
(CP852/CWI-2); videóvágóban két marker közti rész kivágható; hangszerkesztő+voice
changer csúszkákkal (pitch + DX8-erősség); IPTV érthető belépéssel és valódi
kategóriákkal, tiszta belépés-előtti képernyővel. Frissítés: a program felajánlja
(Súgó→Frissítés), telepítős magától újraindul; modulok a Modulkezelőben.

---

## 8. Grok „biztonságos" használata – mire figyelj

- Grok **olvashatja/írhatja a repót**, tud buildelni és `gh`-val feltölteni, DE:
- **Feltöltés CSAK „publikálás"-ra**, és **CSAK sikeres kulcs-szken után** (§5.4).
- Grok ne nyúljon a felhasználó tárolt kulcsaihoz, és **ebbe a fájlba SE** kerüljön
  kulcs.
- Ha bizonytalan az állapotban, előbb **nézze meg a lemezt** (mi épült/van kiadva),
  és kérdezzen, mielőtt kiadna vagy törölne bármit.
- Build mindig a **pythoncore-3.14-64** interpreterrel; a telepítőt **PowerShellből**.
