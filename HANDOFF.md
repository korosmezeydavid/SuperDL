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
futtatókörnyezet + modulrendszer) + **17 telepíthető modul** (a bővebb funkciók).
GitHub: `korosmezeydavid/SuperDL`.

> **Testvérprojekt:** a SuperDL Androidra is létezik (Super Digital Lounge, akadálymentes
> launcher, Kotlin) – forrás: `C:\Users\msn\Documents\SuperDL-Android`, belépő doksi ott:
> `AI_START_HERE.md`. Külön termék, közös filozófia (lean core + letölthető modulbolt).

---

## 2. HOL VAN MINDEN – útvonal-térkép

Minden a **`C:\Users\msn\Documents\Audacity\SuperDownloader`** mappában.

| Mi | Hol |
|----|-----|
| **Core forrás (csomag)** | `superdl\` (pl. `coremod.py` = modul-host/menük, `selfupdate.py` = önfrissítés, `searchwin.py` = Médiakereső, `store.py` = beállítás/kulcs-tár, `manager.py` = letöltéskezelő) |
| **Fő GUI belépő** | `superdl_gui.py` (a `MainFrame` osztály) |
| **CLI belépő** | `superdl.py` |
| **Verziószám** | `superdl\__init__.py` → `__version__` (most: `4.5.5`) |
| **Modulok forrása** | `modules_src\<id>\manifest.json` + `modules_src\<id>\<id>_mod\` (17 db – lásd a listát lent) |
| **Modul-csomagoló** | `tools\build_module.py` (ZIP + SHA + modules.json-bejegyzés) |
| **Modul-katalógus (a „bolt")** | `modules.json` (repó gyökér) – a program ebből tudja, milyen modulok/verziók vannak |
| **Build-specek** | `SuperDL.spec` (onefile GUI), `SuperDL-cli.spec` (CLI), `SuperDL-onedir.spec` (telepítőhöz) |
| **Telepítő-szkript** | `SuperDL.iss` (Inno Setup / ISCC) |
| **Kulcs-szkenner** | `tools\keyscan.py` (publikálás előtt KÖTELEZŐ) |
| **Kimenetek** | `dist\SuperDL.exe`, `dist\SuperDL-cli.exe`, `dist\SuperDL\` (onedir), `installer\SuperDL-Setup-<verzió>.exe`, `dist_modules\<id>-<verzió>.zip` |
| **Hírlevél a listának** | `C:\Users\msn\Documents\superdllistara.txt` |
| **Claude saját memóriája** | `C:\Users\msn\.claude\projects\C--Users-msn-Documents-Audacity\memory\` (ez CLAUDE-specifikus; Grok NEM éri el – ezért van EZ a HANDOFF.md a repóban) |

### 2.1 A 17 modul (a `modules.json` szerint, 2026-08-29)

| id | verzió | kategória | név |
|----|--------|-----------|-----|
| docconvert | 1.3.3 | Könyvek | Dokumentum-konverter |
| konyvek | 1.2.1 | Könyvek | Könyvek (hangoskönyv-lejátszó, könyvjelzők) |
| mediatools | 1.4.10 | Média | Média-eszközök (DVD/VOB, hangformátumok) |
| supermedia | 1.3.3 | Média | Super Media |
| felolvaso | 1.4.8 | Média | Felirat-felolvasó lejátszó |
| radio | 1.1.8 | Média | Internetes rádió (+ időzített felvétel) |
| iptv | 1.0.8 | Média | Internetes TV |
| tvmusor | 1.2.1 | Média | TV műsor (tévéújság, EPG, kedvenc-figyelő) |
| jatekok | 1.15.2 | Játékok | Játékok (37+ retró port, saját játékok, online) |
| mail | 1.2.1 | Kommunikáció | Super Mail (e-mail) |
| csevej | 1.6.0 | Kommunikáció | Csevejcenter (térbeli hang, közös zene) |
| tavsegitseg | 1.0.1 | Kommunikáció | Távsegítség (távvezérlés, P2P) |
| p2p | 1.1.3 | Eszközök | Fájlküldés gépről gépre (P2P) |
| atjaro | 1.0.2 | Eszközök | Átjáró (telefon, könyvjelző-szinkron) |
| iphone | 1.1.0 | Eszközök | iPhone (zene, fotó, videó) |
| szervezes | 1.3.2 | Szervezés | Szervezés (naptár, jegyzet) |
| hangalamondas | 1.0.6 | AI | AI hangalámondás |

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

**Utolsó frissítés:** 2026-08-31 · dolgozott: Claude

---

### 🔨 LETÖLTŐ-MOTOR MK2 – MEGÉPÍTVE, NEM PUBLIKÁLT (2026-08-31)

**A letöltés túléli a kapcsolatkimaradást.** Eddig ha elment a net, a letöltés „hiba"
lett és ott ragadt. **A hiba és a várakozás nem ugyanaz:** a „hiba" azt üzeni, hogy
TENNED KELL valamit; a „várakozik a hálózatra" azt, hogy nem kell.

- **Új állapot: `DownloadManager.HALOZATRA_VAR`** („várakozik a hálózatra"). Benne van a
  `RESUMABLE`-ben → mentődik és újraindítás után is folytatódik; a GUI „aktív vagy
  várakozó" számlálója is számolja; a per-elem hibabemondás NEM sül el rá (az csak
  kész/hiba/seedelés esetén szól), tehát nincs hamis hibajelzés.
- **A besorolás KÉT feltételes, és ez szándékos.** `halozati_eredetu(uzenet)` =
  `netcheck.looks_like_offline(uzenet)` **ÉS** tényleges mérés (`online(force=True)`).
  A szövegfelismerés önmagában kevés: a minták közt ott az „ssl" és a „timeout" is, amit
  egy lassú szerver is kivált, miközben a net tökéletes. Ilyenkor HIBÁT kell mondani,
  különben a felhasználó a végtelenségig várna valamire, ami nem jön el.
- **A figyelő (`_halozat_tick`)** csak akkor mér, ha van várakozó elem (ne nyitogassunk
  TCP-t feleslegesen); az offline jelzés EGYSZER szól; 10 másodpercenként néz rá;
  visszatéréskor egy mondat, majd minden várakozó elem újraindul. **A folytatás magukban
  a letöltőkben van** (`.sdlstate`, aria2 vezérlőfájl, `.part`) – nekünk csak újra kell
  indítani őket (közös `_ujraindit()` az újrapróbával).
- **A jelzés megnyugtat, nem ijeszt:** „…3 letöltés várakozik. **Nem kell tenned semmit:**
  amint visszajön a net, magától folytatódnak."
- **A két gépezet nem lép egymásra:** az újrapróba csak „hiba"-ra fut, a hálózatfigyelő
  csak a várakozókra.

**Ellenőrizve:** **1561 pytest zöld**; új teszt `tests\test_halozat_visszateres.py`
(15 eset, köztük két végponttól végpontig futó a `_run_job` besorolására).
compileall tiszta, attr_audit 0, kulcs-szken tiszta. Commit: `9fa8e3c`.

**HÁTRA (MK4 maradéka, külön kör):** a szegmentált és a yt-dlp motor SAJÁT belső
újrapróbáit (5 exponenciális, illetve 5+5) egységesíteni a közös politikára, és a próbák
számát megmutatni a sorban. **Most szándékosan nem nyúltam hozzá:** a job-szintű
újrapróba ráhúzása duplázna, mert azok a motorok belül már próbálkoznak — a hálózati
esetet pedig ez a kör lefedi.
**ÉLESBEN MÉG NEM MÉRVE:** WiFi kikapcsolása letöltés közben, majd visszakapcsolás.

---

### 🔨 LETÖLTŐ-MOTOR MK1 + MK4 + MK8-részlet – MEGÉPÍTVE, NEM PUBLIKÁLT (2026-08-31)

**Cél (MK1):** ha egy torrent le- vagy feltöltése nem lett kitörölve, a program indításkor
NE kérdezzen – folytassa, vagy végezze a seed-kötelezettséget, **kézi leállításig**.

**Lemez-ellenőrzés előbb:** a terv mind a négy akadási pontja igazolódott (a W0-val
ellentétben itt nem tévedett a terv). **Egy dolgot viszont a terv kihagyott**, és fél
javítást eredményezett volna: a `restore()`-ban van egy MÁSODIK szűrő
(`if status in ("kész","hiba"): continue`) a `_persistable()` mellett. Csak az egyiket
javítva a mentés megtörténik, a visszatöltés viszont némán eldobja – a teszt zöld, a
felhasználónál mégsem működik. **Mindkét helyen javítva.**

**Amit a kód csinál:**
- **Új mentett mező: `Job.user_stopped`.** A SZÁNDÉKOT nem a státuszszóból következtetjük
  vissza – a kilépés és a kézi leállítás ugyanazt írja be, és a kettőnek ELLENTÉTES a
  jelentése. `stop(job, felhasznaloi=True|False)`, `stop_all(felhasznaloi=…)`; a GUI
  kilépéskor `felhasznaloi=False`-szal hív. **Ez egyben a 3. pont versenyhelyzetét is
  megszünteti**, mert nincs mit visszakövetkeztetni a mentés pillanatában.
- **`restore()`:** torrentnél `autostart = not user_stopped`; a „kész" torrent verify
  módban jön vissza (vezérlőfájl nélkül az aria2 „már létezik"-et dobna).
  **Új él, amit a terv nem fedett:** ha a felhasználó KIKAPCSOLTA az örök seedelést, a
  „kész" azt jelenti, hogy az arány teljesült – ilyenkor a torrent a sorban marad, de
  NEM kezd magától újra seedelni (különben minden indítás felülírná a beállítását).
- **`_persistable()`:** a torrent MINDIG marad (hiba és kész állapotban is); csak a
  törlés veszi ki.
- **`_offer_resume()` kettévált:** a torrentek szó nélkül folytatódnak, csak közlés megy
  ki (`resume_summary()`: „2 torrent folytatódik: 1 letöltés, 1 megosztás."); a kérdés
  CSAK a nem-torrent elemekre vonatkozik, és a „nem" CSAK azokat dobja el.
- **Új `start(job)`** – a `stop()` párja: visszavonja a felhasználói leállítást.
  Enélkül a kézzel leállított torrent VÉGLEG leállt volna (a `user_stopped` örökre igaz).
- **`seed_forever` külön kapcsoló (CSAPDA!):** az aria2-nél a `seed-ratio=0.0` ÖRÖK
  seedelést jelent, a mi kódunkban a `seed_ratio == 0` eddig azt, hogy EGYÁLTALÁN NE
  seedeljen (`seed-time=0`). A két jelentés egymás ellentéte – a 0-t nem szabad
  túlterhelni. Az opció-építés kiemelve `TorrentDownloader.aria2_opciok()`-ba, hogy
  aria2 és hálózat nélkül tesztelhető legyen.
  ⚠️ **Alapértelmezés: BE** (ez a tervezőszobai döntés) – vagyis meglévő telepítéseknél
  is megváltozik a viselkedés: a kész torrent kézi leállításig seedel. Kikapcsolható:
  Beállítások → „A kész torrent kézi leállításig ossza meg".
- **MK4 – közös újrapróba-politika** (`superdl/retrypolicy.py`): 1, 2, 5, 10 perc, utána
  15 percenként; **felolvasható mondattal** („Második próbálkozás, öt perc múlva.") és
  EMBERI idővel („negyed óra", nem „00:15:00"). A hibára futott torrent a sorban marad és
  magától újrapróbálkozik; a kézzel leállított SOHA nem, és a „fájl már létezik" ütközés
  sem (az DÖNTÉST vár, nem újrapróbát – különben 15 percenként ugyanabba a falba futna).
  A jelzés a `DownloadManager.on_notice` visszahíváson át jut a felolvasóhoz (a kezelő
  nem ismeri a wx-et). **Ebben a körben CSAK a torrentre kötve** – a másik két motor az
  MK2/MK4 teljes körében jön.
- **MK8-részlet: `max-upload-limit`.** Eddig CSAK letöltési korlát volt; seedelés közben
  a torrent megehette a teljes feltöltési sávot, amitől a saját letöltéseid is
  belassulnak. Új beállítás: „Feltöltési sávkorlát". Ez a párja az örök seedelésnek.
- **CLI:** `--seed-ratio-hasznal` és `--upload-limit`; a `--resume` ugyanazt a
  torrent-viselkedést és összefoglalót kapja, mint a GUI (a két felület ne térjen el).

**Ellenőrizve:** **1546 pytest zöld** (a két SAPI-teszt kihagyva). Új teszt:
`tests\test_torrent_resume_mk1.py` (28 eset). `compileall` tiszta, a CLI súgó rendben,
a névelcsúszás-audit 0 találat, kulcs-szken TISZTA.

**HÁTRA:** Core-build (ez MAG-változás: `manager.py`, `torrent.py`, `superdl_gui.py`,
`superdl.py`), majd „publikálás". **ÉLESBEN MÉG NEM MÉRVE:** valódi torrenttel a
kilépés → újraindítás → kérdés nélküli folytatás, és a növekvő szünetes újrapróba
hálózat-kihúzással.

---

### ✅ KIADVA 2026-08-30 (este): v4.5.5 + mail 1.2.3 + tvmusor 1.2.2 + mail 1.2.4

**Minden kint van, minden link 200, a repó szinkronban.**

| Kiadás | Tag | Megjegyzés |
|---|---|---|
| Core **4.5.5** | `v4.5.5` | **„Latest"**; assetek: `SuperDL.exe`, `SuperDL-cli.exe`, `SuperDL-Setup-4.5.5.exe` + verzió nélküli `SuperDL-Setup.exe` alias |
| Super Mail **1.2.3** | `mod-mail-1.2.3` | `--latest=false` |
| TV műsor **1.2.2** | `mod-tvmusor-1.2.2` | `--latest=false` |
| Super Mail **1.2.4** | `mod-mail-1.2.4` | `--latest=false` · POP3-kör, lásd lent |

Sorrend a bevált szabály szerint: **modulok előbb, a Core utoljára `--latest`-tel** –
nem volt latest-csapda. `modules.json` frissítve és pusholva (új eszközzel, lásd lent),
forrás pusholva: `b077b04` (4.5.5-kör) és `ce122a8` (mail 1.2.4).
Kulcs-szken a feltöltés előtt **TISZTA** (909 fájl, a három binárissal együtt).

**HÍRLEVÉL MEGÍRVA:** `C:\Users\msn\Documents\superdllistara.txt` (a szokott néven és
helyen, 212 sor) – a 3.29.11 → 4.5.5 út: 7 új modul, offline fordítás, teljes mentés,
saját szintetizátor, F1-súgó, audit, és a két friss javítás.
ℹ️ **Tisztázva (Dávid, 2026-08-30):** a hírlevelek KIMENNEK, csak nem mindig kapok róla
visszajelzést – tehát a korábbi „még nem ment ki" bejegyzések félrevezetők voltak. Az
iPhone-hírlevél is kiment; a mostani ezért csak utal rá, nem meséli újra. A fájlt szabad
felülírni, nem archívum.

---

### 🔨 mail 1.2.4 – POP3-kör (2026-08-30, késő este) – KIADVA

**DÁVID JELEZTE:** „a pop3 fiókoknál csak a bejövő leveleket listázza, a többit nem, a
többi mappát. Több szolgáltatónál is teszteltem. Továbbá ha bejelölöd hogy pop3 akkor az
imap adat bekérések tünjenek el.”

**1. A mappák – NEM a mi hibánk, de a hallgatás igen.** A POP3 protokoll nem ismer
mappákat: a szolgáltatónál EGYETLEN postaláda van, az Elküldött/Piszkozatok/Kuka
IMAP-fogalmak. A kód eddig is helyesen egyetlen sort mutatott – csak **nem mondta meg,
miért**, ezért ment el a felhasználó több szolgáltatót végigpróbálni.
- `mail_core.pop3_mappa_magyarazat(fiok)` + `mail_core.POP3_MAPPA_NEV`;
- `mailwin._mappak_betolt` **fiókonként EGYSZER** mondja el (`_pop3_elmondva` halmaz) –
  a lista minden frissítésekor ismételgetni fárasztó volna;
- ha ismerjük a szolgáltató `imap_host`-ját, a szöveg meg is mondja a nevét.

**2. A fiók-párbeszéd mezői.** POP3 → eltűnik az IMAP szerver+port; IMAP → eltűnik a
POP3 szerver+port; **az SMTP MINDIG marad** (a küldés mindkettőnél SMTP).
- `FiokDialog.mezok_protokollhoz(pop)`: a döntés **wx nélkül**, hogy tesztelhető legyen;
- a `sor()` helper eltárolja a sor-sizert ÉS a címkét (`_sorok`), így a mező a
  címkéjével együtt tűnik el, és a sor össze is csukódik (`Sizer.Show(..., recursive=True)`);
- a rejtett mezők ÉRTÉKE megmarad (az auto-konfig nem vész el visszaváltáskor);
- váltáskor a program kimondja, mit rejtett el.

**Kimenet:** `dist_modules\mail-1.2.4.zip` (SHA-256
`17f7c43fcd25c16c086ceb0d2a30cdae0745e7049c41ce732a3b9c792c10762b`, 186 562 byte).
Új teszt: `tests\test_mail_pop3_mappak.py` (8 eset). **1518 pytest zöld.**

**MEGJEGYZÉS a piszkozatról:** POP3-nál eddig is helyesen működött – a program a gépre
menti `.eml`-ként, és ki is mondja, hova. Ezen nem kellett változtatni.

---

### 🔨 tvmusor 1.2.2 (2026-08-30, este) – KIADVA

**LACI JELEZTE:** „Megpróbáltam emlékeztetőt beállítani a Vuk című rajzfilmhez, de azt írja
a program, hogy »A naptár most nem érhető el… A Szervezés modul naptára kell hozzá.«
Nem értem a dolgot, fel van telepítve a szervezés modul.”

**GYÖKÉR (nem a Szervezés modul!):** a naptár KEZELŐJE (`OrganizerManager`) a CORE-ban él –
a `MainFrame.__init__` feltétel nélkül létrehozza (`self._organizer`), hogy az emlékeztetők
zárt ablak mellett is elsüljenek. A Szervezés modul csak az ABLAKOT adja hozzá. A
`tvmusorwin._emlekezteto_hozzaad()` viszont `getattr(self.core, "main")`-en át kereste a
főablakot – a `CoreContext` pedig `main_frame` (és `frame`) néven adja, **`main` néven SOHA**.
A `getattr` alapértelmezése elnyelte a hiányt → `org is None` → a funkció **a megjelenése óta
halott volt, MINDENKINÉL**, és a hibaüzenet ráadásul rossz helyre küldte a felhasználót.
⚠️ **Ez a MÁSODIK ilyen névelcsúszás:** a `modkit.py` `frame`-aliasa mellett ott a
megjegyzés, hogy az volt a „Napi infó nem indul” gyökér-oka.

**JAVÍTÁS (modul-oldali, Core-build NEM kell):**
- új `_naptar_kezelo()`: végigpróbálja az összes ismert útvonalat (`core.organizer`,
  `core._organizer`, `main_frame`, `frame`, `main`), majd mentőövként a **saját szülő-ablakát**
  (a `register_window` megnyitója a főablakot adja szülőnek: `factory(self.frame)`), végül a
  `wx.GetApp().GetTopWindow()`-ot. Property-hibán sem szakad meg (`_biztos_attr`).
- **a hibaüzenet átírva:** nem a Szervezés modult kéri számon; ha tényleg nincs kezelő, kimondja,
  hogy ez a program hibája, nem a felhasználóé.
- **a valódi hiba nem mosódik össze a „nincs naptár”-ral:** eddig az `add_event` kivétele is
  ugyanazt a `None`-t adta. Új `_naptar_hiba` mező + `_naptar_hiba_szoveg()`.

**Kimenetek:** `dist_modules\tvmusor-1.2.2.zip` (SHA-256
`b66048996f29106ca8ba4bcb26a396c99e53925904734a7a67507ed2ba42e061`, 19 093 byte).
Teszt: **1506 pytest zöld** (a két SAPI-teszt kihagyva – az a RÉGI natív összeomlás, független).
Új teszt: `tests\test_tvmusor_naptar.py` (7 eset; a regressziós őr kimondottan azt rögzíti,
hogy a CoreContextnek **nincs** `main`-je, mégis meg kell találni a kezelőt).
Kulcs-szken **TISZTA** (184 fájl, kilépési kód 0).

**➡️ KÖVETŐ: NÉVELCSÚSZÁS-AUDIT az ÖSSZES modulra (2026-08-30, este) – EREDMÉNY: TISZTA.**
Kérdés volt: hol kér még modul olyan Core-attribútumot, ami nem létezik? Új eszköz
(`tools\attr_audit.py`) AST-ből összeveti, mit ADNAK a `CoreContext`/`WxHost`/`MainFrame`
azzal, amit a modulok KÉRNEK (`getattr(core, "…")` és közvetlen `core.X` / `main.X`).
**Több ilyen hiba NINCS** – a tvmusor volt az egyetlen. Két false positive tisztázva:
- `main._module_host` (könyvek modul, Átjáró-küldés): **létezik**, csak nem a MainFrame
  törzsében – a `coremod.py:489` teszi rá kívülről. Az auditor ezért a `superdl\`-t és a
  `superdl_gui.py`-t is átnézi `main.X = …` értékadásokért.
- **23 db `main._<modul>_win = None` takarítás** 15 modulban: a `register_window` óta a Core
  tartja nyilván az ablakokat (`WxHost._windows`), így ezeket a neveket SENKI nem állítja be.
  **HOLT, de ÁRTALMATLAN** kód (`getattr(..., None) is self` sosem igaz). NEM javítottuk:
  15 modul-kiadás nulla felhasználói haszonért. **Takarítsuk ki modulonként, amikor az a
  modul úgyis kiadásra kerül valami valódiért.**

Az őr **állandó teszt** lett: `tests\test_modul_core_szerzodes.py` – és nem csak azt
ellenőrzi, hogy ma tiszta, hanem **azt is, hogy tényleg elkapná a régi tvmusor-kódot**
(enélkül az őr dísz volna). Kézi triázshoz: `tools\attr_audit2.py` (tág, zajos, sosem ad
hibás kilépési kódot).
**Teszt a kör végén: 1510 pytest zöld.** Kulcs-szken TISZTA (728 fájl). Modul-forrás NEM
változott ebben a körben → a `tvmusor-1.2.2.zip` érvényes, nem kell újraépíteni.

**KIADVA** (`mod-tvmusor-1.2.2`, 2026-08-30). **Válaszlevél Lacinak még nem készült.**
**NYITOTT (Core, külön döntés):** a rendszerszintű javítás – vagy `main` alias a
`CoreContext`-be (olcsó, de a harmadik szinonima), vagy egy rendes **`core.organizer`
szolgáltatás**, hogy a moduloknak soha ne kelljen a főablakon átnyúlniuk. A második a tiszta,
és a W6 „figyelő”-nek amúgy is kelleni fog.

---

### 🔨 4.5.5 (2026-08-30) – KIADVA

**Téma: a Super Mail fordítói.** Két dolog készült el egy körben.

**1. HIBA – a helyben futó fordító sosem látszott a kész programban.** Az F9 csak két
fordítót ajánlott fel, mindkettőnél elhagyja a levél a gépet. Ok: a fagyasztott programból
szándékosan kimarad a `ctranslate2.converters` alcsomag (a torch miatt: +365 MB), a
CTranslate2 `__init__.py`-ja viszont FELTÉTEL NÉLKÜL importálja → `import ctranslate2`
ImportError → `offlineford.elerheto()` hamis → a motor csendben eltűnt a listáról.
**Forrásból futtatva sosem látszott** (ott a converters megvan) – ezért élt hetekig.
Javítás három helyen:
- `superdl/offlineford.py` → új `ct2()`: ha az import a hiányzó converters miatt hasal el,
  üres pótmodult ad be a helyére és újrapróbál; a `_Motor` is ezt használja;
- `SuperDL-onedir.spec` → a `models`/`specs` alcsomag kézi kérése (a converters kizárása
  után az elemző nem jutna el hozzájuk);
- **a mail modulban is megismételve** (`forditas._ct2_behoz`), hogy a javítás Core-build
  nélkül, puszta modulfrissítéssel is eljusson a felhasználóhoz. Ez élesben BEVÁLT:
  Dávid gépén a 1.2.3 modul telepítése + újraindítás után megjelent a helyben futó fordító.

**2. ÚJ – alapértelmezett fordító (Dávid kérése).** Beállítások → Általános → legördülő
lista: *kérdezzen rá* (ez marad az alapértelmezés) / helyben / ingyenes / saját AI-kulcs.
Beállított motorral az F9 kérdés nélkül fordít – de csak ha a nyelvet BIZTOSAN felismerte;
bizonytalan nyelvnél feljön a régi párbeszéd, a beállított motorral előre kiválasztva.
A nyelvi csomagok CSENDBEN töltődnek: mentéskor az `en→hu` (minden más nyelv ezen át
fordul), fordításkor a hiányzó nyelvé a munkaszálon. Nincs párbeszéd, nincs hibaablak –
sikertelen letöltésnél az online motor viszi tovább. Tárolás: `forditas_motor` kulcs.

**Kimenetek (megvannak a lemezen, feltöltés NINCS):** `dist\SuperDL.exe` (193,1 MB),
`dist\SuperDL-cli.exe` (133,8 MB), `dist\SuperDL\` onedir, `installer\SuperDL-Setup-4.5.5.exe`
(141,5 MB), `dist_modules\mail-1.2.3.zip`
(SHA-256 `02b8111d75c93dbd21223d502b6ff83163cfe8d37222963a94cf831af1f182f6`, 184 653 byte).
yt-dlp 2026.08.19. Kulcs-szken **TISZTA** (319 fájl, kilépési kód 0). Teszt zöld (a
felolvasó SAPI-tesztje összeomlik egy natív kivétellel – RÉGI és független ettől).
A friss csomagban ellenőrizve: ctranslate2 + models/specs/logging/version/extensions,
superdl.offlineford, subword_nmt, sentencepiece, sacremoses mind bent van, converters nincs.

**KIADVA** (`v4.5.5` + `mod-mail-1.2.3`, 2026-08-30).

---

> ⚠️ **MULASZTÁS-JAVÍTÁS (2026-08-29).** Ez a szakasz 2026-07-17 óta (v3.29.11) NEM volt
> frissítve, miközben a fejlesztés v4.5.4-ig jutott – kb. 200 commit és 7 új modul maradt
> ki belőle. Az alábbi „JELENLEGI ÁLLAPOT" a lemez és a GitHub valós állapotából készült
> (git log, `modules.json`, `gh release list`). A 2026-07-17 alatti bejegyzések innentől
> **ARCHÍVUM**. TANULSÁG: a §0 stafétaprotokoll utolsó pontját (átadáskor frissíts) tartani
> kell, különben egy új AI hetekkel korábbi állapotot lát.

**KIADVA ÉS SZINKRONBAN ✅ (2026-08-29).** Core **v4.5.4** „Latest"; a munkafa tiszta
(egyetlen követetlen mappa: `tools/brailab_hangolas/`), `origin/main` előtt 0 commit,
minden modul kiadva. Utolsó release: `mod-iphone-1.1.0` (2026-08-29).

### Mi történt 3.29.11 → 4.5.4 (a fő szálak)

**7 ÚJ MODUL:**
- **jatekok** (1.0 → 1.15.2) – a legnagyobb szál. 37 hű Homelab retró-port (Kisvarga Zsolt,
  Sédi Gábor, Halmágyi István, Csapó Endre, Ócsvári Áron nyomán), SAJÁT jogtiszta játékok
  (Milliomos kvíz, Szerencsekerék, Ország-Város-Fiú-Lány – Mezei Géza ötlete, Póker,
  Blackjack, UNO), majd **ONLINE** változatok host-hiteles fejetlen motorral (UNO, Blackjack,
  Ország-Város, Póker, Szerencsekerék; `NetPanelMixin` közös bázis). 1.15.0: az EREDETI
  BraiLab PC hang feloldható retesz alatt; 1.15.2: magyar Braille-tábla.
- **mail** – Super Mail (1.0 → 1.2.1): egyesített bejövő, szabályok, időzítés, piszkozat,
  aláírás, HTML, AI-levélírás, helyesírás-ellenőrző, levél-fontosság, offline mód.
- **csevej** – Csevejcenter (1.0 → 1.6.0): akadálymentes valós idejű csevegő, **térbeli hang**
  (helyi hálón és interneten STUN + UDP hole-punching), admin-jogok, közös zenehallgatás.
- **tavsegitseg** – Távsegítség 1.0.1: távvezérlés általános P2P UDP transzporton
  (STUN + hole-punch), billentyű-elkapás, rendszerhang-bridge (WASAPI loopback), biztonsági
  megerősítésekkel (Laci ötlete).
- **tvmusor** – TV műsor (1.0 → 1.2.1): akadálymentes tévéújság XMLTV EPG-motorral,
  kedvenc-figyelő, naptári emlékeztető, nap-választó.
- **atjaro** – Átjáró 1.0.2: telefon-kapcsolat, könyv- és hangoskönyv-küldés,
  könyvjelző-szinkron (közös alap: `superdl.bookmarks`).
- **iphone** – iPhone 1.1.0: zene, fotó, videó mentése ÉS feltöltés a gyári Zene alkalmazásba.

**CORE (3.29.11 → 4.5.4) – a fő újdonságok:**
- **Saját magyar formáns-szintetizátor** (eSpeak nélkül, csatorna-vokóder) + BraiLab-stílusú
  retró hang; Gépi ének eszköz (a szintetizátor dallamra énekel).
- **Képernyőolvasó-elsőbbség**: minden egyéb program-beszéd elnémítható; közvetlen
  **NVDA-vezérlés** (Tolk helyett).
- **OFFLINE FORDÍTÁS** (4.5.0) – a levél szövege el sem hagyja a gépet.
- **TELJES MENTÉS ÉS VISSZAÁLLÍTÁS** (4.5.3) – költözés egy fájllal.
- Internet-teszt a főablakban (Ctrl+Alt+I, 4.4.0); programszintű akadálymentes internet-jelzés.
- Wifi-jelerősség dBm-ben, beépített fájlválasztó, összeomlás-napló (4.5.2);
  UTF-16 szövegfájlok felismerése (4.5.1); önfrissítés-javítás (4.5.4).
- Automatikus háttérindítás a Windows-szal (időzített felvételekhez); periodikus
  frissítés-ellenőrzés; Modulkezelő „Összes frissítése”.
- **F1 részletes súgó MINDEN ablakhoz** + kezdőképernyő (szakmai visszajelzés nyomán).
- Fájltársítások (zene → Super M, videó → felolvasó), HKCU, admin nélkül, visszavonható.

**BIZTONSÁGI/MINŐSÉGI AUDIT (KV1–KV20, 2026-07-23):** közös `URLPolicy` (SSRF- és
méretvédelem), DPAPI-titkosítás a naptár-címre, felhő-AI beleegyezés + prompt-injection
határ, atomikus média-export (`.part` → ellenőrzés → csere), lemez-alapú felvétel (a 8 órás
felvétel sem eszi meg a memóriát), ReadEngine munkamenet-generáció, Pandoc ellátási lánc
rögzített verzióval és hash-sel, közös magyar szöveg-dekódoló. Ezt követte a hiba-audit
MK1–MK4 (SAPI-COM gyökér-fix, `_closing` wx-guard 13 modul-ablakban, alfolyamat-életciklus).

**KÖZÖSSÉG / VISSZAJELZŐK:** Laci (rádiófelvétel, némítás, Modulkezelő gombnév, bemondás-
sorrend, Távsegítség ötlete), István (levél-csatolmány), Barbi és Herman Tibor (audit),
Mezei Géza (Ország-Város társszerző). A hivatalos honlap a Névjegyben: **super-dl.com**.

### ➡️ ZSIGA-JELZÉS (2026-08-29) – DIAGNOSZTIZÁLVA, JAVÍTÁS MÉG NEM KÉSZÜLT
Válaszlevél megírva: `C:\Users\msn\Documents\zsiganak.txt`. Kód NEM módosult
(nem hangzott el a „create maxima”). Három dolog, mindhárom gyökere megtalálva:

1. **DIGEST LEVELEK – a program csak az elejéig jut.** (Jaws- és mobil-info lista
   összevont módban.) GYÖKÉR: `modules_src\mail\mail_mod\mail_core.py`,
   `level_szovegtorzs()` – a `msg.walk()`-ban az ELSŐ `text/plain` részt veszi
   (`if plain is None`), és kész. Egy `multipart/digest` levélnél az első text/plain
   éppen a Mailman-tartalomjegyzék, a `message/rfc822` részekbe csomagolt VALÓDI
   levelek pedig kimaradnak. TERV: ismerjük fel a digestet, és fűzzük össze az
   összes beágyazott levelet, mindegyik elé egy hallható elválasztóval
   (hányadik, kitől, tárgy) – ne egy végtelen szövegfolyam legyen.
2. **AZ AI-FORDÍTÓ CSONKOLJA A HOSSZÚ LEVELET.** GYÖKÉR:
   `modules_src\mail\mail_mod\forditas.py` → `ai_fordit()` egyetlen
   `aiclient.chat(...)` hívást tesz, és a `chat()` alapértelmezett
   `max_tokens=2000` (superdl\aiclient.py:118). A válasz elfogy a korlátnál, és
   ezt SEMMI nem jelzi – a felhasználó némán kap félbevágott fordítást.
   TERV: darabolás mondathatáron (a `darabol()` már megvan a mymemory-hoz,
   csak nagyobb darabmérettel), darabonkénti fordítás, és HALLHATÓ jelzés,
   ha mégis csonka marad. A néma csonkolás a rosszabbik hiba.
3. **AZ OFFLINE FORDÍTÓ MEGTALÁLHATATLAN.** NEM hiba: működik (ellenőrizve –
   `ctranslate2` benne van a kiadott exe-ben, a fejlesztő gépén az `en→hu` és
   `pl→en` csomag már le is van töltve). DE: az EGYETLEN belépési pontja a levél
   F9-fordítás párbeszédének első rádiógombja. Nincs se menüpont, se beállítás,
   se előzetes csomag-letöltés. Maga a fejlesztő sem találta meg.
   TERV: Beállítások fül – nyelvi csomagok előzetes letöltése/törlése + az
   alapértelmezett fordító kiválasztása, hogy ne kelljen levelenként újraválasztani.

### HÁTRA / NYITOTT
- **Hírlevél**: MEGÍRVA, `C:\Users\msn\Documents\superdllistara.txt`. A kiküldés Dávidnál
  van; a hírlevelek ki szoktak menni, csak nem mindig kapunk róla visszajelzést, ezért
  ide NE írjunk többé „nem ment ki"-t, ha nem tudjuk biztosan.
- **Válaszlevél Lacinak** a tévéújság-hibáról (a `lacinak.txt` mintájára).
- **A 23 holt `_<modul>_win` takarítás** kitakarítása, modulonként, alkalomadtán.
- `tools/brailab_hangolas/` követetlen a gitben – eldönteni: commit vagy `.gitignore`.
- Elhalasztva: AI hang-szinkron (ElevenLabs) a felolvasóban (M3).
- Nem verifikált élesben: a dupla-kattintásos fájltársítás valós telepített gépen.

---

## 6/A. ARCHÍVUM (2026-07-17 és korábbi bejegyzések)

**3.29.11 KIADVA ✅ (2026-07-17).** Core `v3.29.11` „Latest" (4 asset) + `mod-felolvaso-1.2.0`
(`--latest=false`) + modules.json; kulcs-szken TISZTA; minden link 200. TARTALOM: (1) a radiorec
néma-megszakadás fix (lásd lent); (2) felolvaso 1.2.0 — a felolvasás TARTJA A LÉPÉST a
filmfelirattal. MÉRÉS (a user kérte: „mennyire működik?"): valósághű film-ritmuson (45 karakteres
sorok 3,1 mp-enként) alap tempón SAPI 0/4 sor fért bele (6,1 mp csúszás), eSpeak 2/4 (1,1), Edge
0/4 (11,8 mp — soronként 1,6 mp HÁLÓZATI válaszidő) → egy 2 órás filmen percekre nőtt volna. FIX:
`DEFAULT_RATE=7` + állítható tempó-SpinCtrl; ELŐRE-GYÁRTÁS (`_prefetch`/`_prefetch_done`/
`_drop_ahead`, csak a 12 mp-es „láthatáron", ugrás/leállítás eldobja); `_closing` zárás-védelem;
ytsource: a magyar felirat ne essen vissza CSENDBEN angolra (újrapróba). EREDMÉNY MÉRVE: SAPI 4/4
(0,0 mp), eSpeak 4/4 (0,0), Edge 3/4 (0,5 mp). 108 pytest + CI zöld. LACINAK VÁLASZLEVÉL:
`C:\Users\msn\Documents\lacinak.txt` (felvevő-fix + felolvasó-ajánlás, a méréssel). Hírlevél a
3.29.11-ről MÉG NEM ment.

**(archív) radiorec FIX — a 3.29.11-ben KIADVA (commit ac6a367).**
LACI JELEZTE: „F9-re indított felvétel a legváratlanabb pillanatokban leáll, és NEM ír semmiféle
hibát." GYÖKÉR (három együtt): (1) nincs `-reconnect` → az élő adás megbicsaklásakor az ffmpeg
KILÉP; (2) 15 mp-es `-rw_timeout` túl szigorú; (3) A NÉMASÁG OKA: a `_watch` bármely >8 KB fájlt
„kész"-nek vett → a megszakadt felvételt SIKERESNEK hitte (`_on_done` „Felvétel kész"), és az
ffmpeg stderr-je DEVNULL-ra ment. FIX: `-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 30`
(VÉDŐKAPU: HTTP-protokoll kapcsolói! nem-http URL-nél „Option reconnect not found"-dal AZONNAL
elszállna → csak `http(s)`-nél; ÉLESBEN igazolva: lavfi-nál hibázik, valódi rádió-streamnél kód=0);
`-rw_timeout` 45 mp; `stderr=PIPE` + `_drain_err` (deque tail, a csövet ürítjük); `_premature()` →
kézinél (F9) minden nem-user vég váratlan, időzítettnél <90% hossz → status HIBA érthető üzenettel
(„kb. N perc rögzült; a fájl megmaradt és lejátszható" + a valódi ffmpeg-üzenet). 8 új pytest (103
összesen). LACINAK VÁLASZLEVÉL: `C:\Users\msn\Documents\lacinak.txt` (a user küldi).

**3.29.10 KIADVA ✅ (2026-07-16).**

**3.29.10 KIADVA ✅ (2026-07-16).** Core `v3.29.10` „Latest" (4 asset) + `mod-felolvaso-1.0.0` (ÚJ,
10. modul) + `mod-supermedia-1.2.3` (mindkettő `--latest=false`) + modules.json a main-en; forrás
push; kulcs-szken TISZTA (forrás+binárisok+zipek); yt-dlp 2026.7.4; minden link 200; a Core maradt
„Latest". Build-sorrend onedir→ISCC(3.29.10, ÚJ társítás-task)→CLI→onefile. TARTALOM: (M2) ÚJ
felirat-felolvasó modul (idegen film + magyar felirat szinkron felolvasása, hang választható
SAPI/Edge/eSpeak); (M1) fájltársítások (zene→Super M, videó→felolvasó) + Média-menü kapcsoló +
telepítő opcionális task + `superdl/fileassoc.py` (HKCU, admin nélkül, visszavonható) + coremod
`open_window` + gui fájl-arg routing. NEM VERIFIKÁLT ÉLESBEN: a dupla-kattintásos társítás és a
felolvasó kettős hang-lejátszása valós telepített gépen. Hírlevél MÉG NEM ment.

**✅ KÖVETŐ: felolvaso 1.1.0 KIADVA (2026-07-16) — YouTube-link a felolvasóba.** mod-felolvaso-1.1.0
(`--latest=false`) + modules.json push d40cac5; zip+modules.json 200; Core maradt v3.29.10.
`ytsource.py`: yt-dlp feloldja a hang-streamet + letölti a feliratot (manuális előny, majd a
YouTube AUTO magyarra fordított feliratát) → a felolvasó olvassa. Élő végpróba OK (stream + 20
magyar auto-felirat sor). 96 pytest zöld. HÁTRA (M3, elhalasztva): AI hang-szinkron (ElevenLabs).

**✅ radio 1.1.1 KIADVA (2026-07-12, Laci: némítás).** mod-radio-1.1.1 (`--latest=false`) +
modules.json a main-en (push fee64fe); zip + modules.json 200; a Core „Latest" MARADT `v3.29.9`.
TARTALOM: NÉMÍTÁS a rádióban (`_toggle_mute()` + „Némítás be/ki" gomb + Ctrl+M) — a hallgatott hang
elnémul, de a FELVÉTEL (radiorec, külön ffmpeg) zavartalanul megy tovább (időzített/munkahelyi
felvételhez). Kézi hangerő feloldja; súgó: némítás vs szünet. Fejnélküli teszttel igazolva; 75
pytest zöld; kulcs-szken tiszta. Hírlevél a listának MÉG NEM ment (a docconvert 1.2.0 + radio
1.1.0/1.1.1 közös hírlevele a superdllistara.txt-ben van, de a némítás-sor még nincs benne).

**✅ MODUL-KIADÁS (2026-07-12): docconvert 1.2.0 + radio 1.1.0 KIADVA.** mod-docconvert-1.2.0 +
mod-radio-1.1.0 release-ek (`--latest=false`!) + modules.json a main-en (push 0129e9d); minden zip
+ modules.json 200; a Core „Latest" MARADT `v3.29.9` (nincs latest-csapda), stabil linkjei
sértetlenek. 75 pytest zöld, CI zöld, kulcs-szken tiszta. TANULSÁG MEGERŐSÍTVE: modul-release-t
`--latest=false`-szal kell létrehozni, ha a Core marad a legfrissebb. Hírlevél a listának MÉG NEM
ment. Az eredeti kódkész-állapot (referenciának):

**➡️ ÚJ FUNKCIÓK (KIADVA a fentiek szerint; modul-only, NINCS Core-build).** Felhasználói kérés
(2026-07-12), mind a 4 mérföldkő kész, 75 pytest zöld + CI, kulcs-szken tiszta:
- **docconvert 1.2.0** (commit 3443a97) — M3 KÖTEGELT (fájllista + „Mappa hozzáadása", per-fájl
  állapot, cél-mappa) + M4 EGY FÁJLBA ÖSSZEFŰZÉS (`merge_documents`, fájlonkénti címmel). Új
  `extract_book` (kép→OCR / közvetlen / exotikus→köztes TXT). zip: docconvert-1.2.0.zip
  SHA d379a3d9eae685c747cd6eb9c1fb5d3d3c0d5d78c6797a67c1b667c6c4497c2f.
- **radio 1.1.0** (commit 7c659e7) — M1 saját állomás URL-lel (`CustomStationDialog`→kedvencek) +
  M2 megosztás a radio-browser NYILVÁNOS adatbázisába (`add_station`→POST /json/add, KIFEJEZETT
  megerősítés után). zip: radio-1.1.0.zip SHA ed1dd0e365b52e8107a7d8cec6af89a4f26c14ec76337bcad75335eedc9672c0.
- **modules.json MINDKETTŐNÉL SZÁNDÉKOSAN ÉRINTETLEN** — a 2 bejegyzés CSAK publikáláskor.
  PUBLIKÁLÁS: mod-docconvert-1.2.0 + mod-radio-1.1.0 release a zipekkel + modules.json 2 bejegyzés
  (build_module.py kiírta) + push. Core-build NEM kell.

**3.29.9 KIADVA ✅ (2026-07-12).** Core `v3.29.9` „Latest" (4 asset) + `mod-iptv-1.0.3` +
modules.json a main-en; forrás 51296ca; kulcs-szken TISZTA (forrás+iptv-zip+binárisok);
yt-dlp 2026.7.4; 67 teszt zöld kiadás előtt; MODUL ELŐBB→Core UTOLJÁRA `--latest` (nem volt
latest-csapda, minden link rögtön 200). TARTALOM: (1) bot-check teljes tanácssor + tv_embedded
utolsó-esélyes mentőöv (Maxi); (2) hivatalos frissítési forrás rögzítése + Fejlesztői mód
(Tibi 3.5); (3) iptv 1.0.3 üres-állapot/első lépések (Tibi 4.12); (4) repón élő 67 teszt+CI+
lockfile. KIADÁSI TANULSÁGOK: (a) az ISCC ma 8+ percig futott → a 10 perces tool-timeout
ELVÁGTA írás közben = CSONKA telepítő (90 MB a ~135 helyett); ha időtúllépés van, ELLENŐRIZD a
méretet, töröld és építsd újra háttérben. (b) gh release --notes-ben magyar „idézőjeles" szöveg
szétszedi a bash-parancsot → MINDIG --notes-file-t használj. Hírlevél a listának MÉG NEM ment.

**➡️ TIBI-AUDIT 2. KÖR KÓDKÉSZ (2026-07-12, commit a5b3622) — PUBLIKÁLÁSRA VÁR.**
(A) MINŐSÉGBIZTOSÍTÁS (repo-szintű, kiadást nem igényel, MÁR ÉL): `tests/` 61 headless
pytest-teszt (media URL+hibák, modkit min_core_version/SHA/zip-slip, store fsync/bak/corrupt,
CLI exit-kódok, audiobook-darabolás, docconvert CWI+kettős-kódolás, diagnostics titok-maszkolás);
`.github/workflows/ci.yml` (windows-latest, Py3.12: requirements + compileall + pytest minden
pushnál); `requirements-build-lock.txt` (a build-env pip freeze pillanatképe, kiadáskor
frissítendő); `pyproject.toml` (pytest-konfig). FIGYELEM: az ELSŐ CI-futás eredményét ellenőrizd
(gh run list)!
(D) ✅ KÉSZ (2026-07-12, commit cc3f7d4; MEGÍGÉRVE Maxinak a maxinak.txt-ben): bot-ellenőrzés
kezelése. (1) `friendly_error` bot-üzenet a teljes tanácssorral: IP-jelölés magyarázat,
hotspot-gyorsteszt, router/VPN, várakozás, PRIVÁT ablakos cookies.txt-recept. (2) ÚJ utolsó-esélyes
mentőöv: bot-checknél (beállított sütis usernél is) automatikus újrapróba a `tv_embedded`
klienssel — ÉLES MÉRÉS alapján választva: a sima „tv" DRM-es streamet kap, a „tv_downgraded"
formátum-hibát, a `tv_embedded` 27 formátumot ad; hibánál None → az EREDETI hiba marad (sosem ad
rosszabb üzenetet). +1 teszt (67 összesen) + izolált mechanizmus-teszt. OAuth2 SZÁNDÉKOSAN NEM
lesz (Google letiltotta a device-flow-t; fiók-felfüggesztés kockázat — Maxinak megírva). Diagnózis-
tanulság: Maxi „Nincs sütivel is ugyanaz + minden yt-dlp-app érintett" = IP-jelölés, nem süti-gond.
(C) HIVATALOS FORRÁS RÖGZÍTÉSE + FEJLESZTŐI MÓD (Tibi 3.5 P0 pragmatikus magja; commit 7a871aa,
Core-változás → a köv. Core-kiadás viszi): a frissítés+modul-bolt alapból CSAK a hivatalos
repóról; SUPERDL_REPO/repo.txt átállítás KIZÁRÓLAG a Beállítások→Általános→„Fejlesztői mód"
kapcsolóval érvényesül (alapból KI). Induláskor: figyelmen kívül hagyott átállítás → bejelentés;
élő nem-hivatalos forrás → HANGOS figyelmeztető ablak; frissítés/modul-telepítés előtt kifejezett
megerősítés. CLI-ben figyelmeztető sorok. selfupdate: `custom_repo_requested`/`repo_is_official`/
`ignored_override`/`_dev_custom_repo_enabled`. 5 új teszt (66 összesen, mind zöld). A TELJES
Ed25519-aláírás TUDATOSAN ELHALASZTVA (kulcskezelési teher: kulcsvesztés=beragadt userek; a
usernek elmagyarázva, tibinek.txt-ben is dokumentálva).
(B) IPTV 1.0.3 KÓDKÉSZ — ÜRES ÁLLAPOT + ELSŐ INDÍTÁS (Tibi 4.12): megnyitáskor felolvasható
„Első lépések" útmutató kap fókuszt (3 forrás-lehetőség + legális-figyelmeztetés + F1); „Legutóbbi
m3u betöltése" gyorsgomb (csak ha van mentett cím) + Súgó gomb; betöltés után fókusz a
CSATORNALISTÁRA. Fejnélküli teszttel verifikálva. A zip KÉSZ (dist_modules/iptv-1.0.3.zip,
SHA 7ead47571d0973759bcaa0e99ec171f7a5e8b8bae0f2bfc8a165180f6f8992bc), de a **modules.json
SZÁNDÉKOSAN érintetlen** — a bejegyzést CSAK publikáláskor írd be (különben a bolt 404-es URL-re
mutatna)! Publikáláskor: `gh release create mod-iptv-1.0.3` a zippel + modules.json frissítés
(build_module.py kiírta a bejegyzést) + push. Core-változás NINCS ebben a körben → ha csak az
iptv megy ki, Core-build sem kell.

**3.29.8 KIADVA ✅ (2026-07-12).** Core `v3.29.8` „Latest" (4 asset; API-latest + stabil linkek
200); forrás push HEAD c0e976e; kulcs-szken TISZTA (forrás + mindhárom bináris); yt-dlp 2026.7.4;
Core-only (nincs modul-változás) → sima `--latest`, nem volt latest-csapda. Build-sorrend:
onedir→ISCC(3.29.8)→CLI→onefile GUI (utolsó). Tartalma az alábbi audit-csomag:

**AUDIT „GYORS GYŐZELMEK" (2026-07-11 kódkész → 2026-07-12 KIADVA).** Herman Tibor
3.29.6-auditjából a 6 kiválasztott tétel MIND KÉSZ és verifikálva
(commit c88e530; unit + fejnélküli GUI + élő maszk-ellenőrzés; kulcs-szken tiszta). Nincs
modul-változás (a mediatools/docconvert/konyvek érintetlen) → sima Core-kiadás `--latest`-tel.
  1. **Diagnosztikai csomag** — ÚJ `superdl/diagnostics.py` (`build_report`): verziók,
     telepítés-típus (forrás/onefile/onedir/telepített: unins000.exe-próba), modul-lista,
     beállítás-FEHÉRLISTA (city/cookies_file értéke SOHA, csak „megadva"), napló-vég; a tárolt
     kulcsok MINDEN előfordulása maszkolva (•••KULCS-MASZKOLVA•••), home→~. GUI: Súgó →
     „Hibajelentés vágólapra (diagnosztika)" (MessageBox-megerősítés, felolvasható). CLI:
     `--diagnose`. ÉLŐ ellenőrzés: a valódi tárolt kulcsok nem szerepelnek a jelentésben.
  2. **min_core_version** — Manifest+ModuleEntry+parse_index+`core_version_ok()`
     (modkit); telepítő ELUTASÍT érthető üzenettel; betöltő kihagy érthető hibával; Modulkezelő
     státusz: „Újabb SuperDL kell (legalább X)"; build_module.py átviszi a manifestből. Üres mező
     = nincs megkötés (minden régi modul változatlanul jó).
  3. **Atomikus mentés** — `store._write_fsync` (írás→flush→fsync→rename) a save_json ÉS
     save_secret_json útján.
  4. **AI-kulcs maszkolás** — a 4 kulcs-mező TE_PASSWORD + „Kulcsok megjelenítése" pipa;
     futásidőben a stílus nem váltható → `_swap_secret_style` mező-CSERE (érték+SetName+
     wx.Accessible+MoveAfterInTabOrder+fókusz megőrzve); `_on_ok` a cserélt attribútumból olvas.
  5. **yt-dlp hibák emberi nyelven** — `friendly_error` +14 kategória (korhatár/privát/tagság/
     régiózár/törölt/premier/formátum/ffmpeg/403/429/hálózat/tele lemez/nem írható/nem támogatott);
     CSAPDA-FIX: a korhatár-ág a bot-ellenőrzés ELÉ került („Sign in to confirm your age" a
     bot-mintára is illik). 17 mintaüzenet-teszt zöld.
  6. **CLI** — dokumentált exit-kódok (0 siker/1 általános/2 hálózati/3 fájl/4 nem támogatott/
     5 részleges; `_classify_error`+`_exit_code`, a --help epilógusában is) + `--no-speak`
     (a --speak-et is felülírja) + `--json` (utolsó sor gépi összegzés) + `--diagnose`.
STRATÉGIAI (Tibi-audit, KÉSŐBBRE): aláírt release/modules.json manifest beégetett kulccsal;
minimál CI (ruff+pytest+build smoke) + pytest-alapkészlet; IPTV üres-állapot + első indítási
varázsló; MainFrame→controllerek + formális CoreContext-SDK. Tibinek köszönő válasz még NEM ment.
Az audit-fájl: `C:\Users\msn\Downloads\SuperDL 3.29.6 teljeskörű szakmai audit.txt`.

**3.29.7 KIADVA ✅ (2026-07-11).** Core `v3.29.7` „Latest" (4 asset) + forrás push (HEAD 6b75231).
Kulcs-szken TISZTA (forrás+binárisok). yt-dlp 2026.7.4. Core-only (nincs modul-változás → nincs
latest-csapda, sima `--latest`). Stabil linkek RÖGTÖN 200. Három javítás:
(a) `superdl/media.py` — **konkrét videó-URL-nél NE töltse a rádió/mix/lejátszási listát** (a fő,
felhasználó által jelzett bug; commit 2ef7b4b). GYÖKÉR: a yt-dlp alapból a teljes `list=…`-t
lehúzza; a YouTube Rádió/Mix (`list=RD…`, `start_radio=1`) végtelen → egy szóló videóra kattintva
„mindent lekapkodott" egy mappába (link: `watch?v=HCfH6DAA3hM&list=RDHCfH6DAA3hM&start_radio=1`).
FIX: `_prefers_single_video(url)` → ha az URL konkrét videóra mutat (`v=…`/`youtu.be/<id>`),
`opts["noplaylist"]=True` → csak azt a videót tölti; tiszta lista-URL (`playlist?list=…`, nincs
`v=`) marad teljes lista. Élesben IGAZOLVA (noplaylist=True → 1 videó; alap → a mix). 8 URL-eset
unit-teszt zöld.
(b) `superdl_gui.py` — új **Közreműködők (Credits)** menüpont a Súgó menüben (commit 383979c):
akadálymentes felolvasható ablak (helpdialog) fejlesztő + Herman Tibor (audit) + Horváth Dorina
Éva + tesztelő közösség. `MainFrame.CREDITS_TEXT` + `_on_credits`.
(c) `superdl_gui.py` top-szintű `import os` (commit ff9da50): a `_single_instance_mutex()` az
`os.name`-et használta, de az `os` csak lokálisan volt importálva → forrásból NameError; a frozen
exe futott (PyInstaller a `__main__`-be teszi az `os`-t), ezért a kiadott 3.29.5/3.29.6 NEM volt
érintett. Horváth Dorina Éva jelezte (PR #1, forkról, draft) — a main érintetlen volt, a PR-t NEM
mergeltem, az egy sort beírtam és a PR-t köszönettel lezártam.


**3.29.6 KIADVA ✅ (2026-07-06).** Core `v3.29.6` „Latest" (4 asset) + `mod-docconvert-1.1.4`
+ modules.json a main-en + forrás push (HEAD 0e714d1). Kulcs-szken TISZTA (forrás+zip+binárisok).
yt-dlp 2026.7.4. KIADÁS-SORREND TANULSÁG ALKALMAZVA: a MODUL-release-t ELŐBB hoztam létre,
a Core-t UTOLJÁRA `--latest`-tel → nem volt latest-csapda, minden stabil link RÖGTÖN 200
(nem kellett utólag `gh release edit`). Két javítás:
- **BEÁLLÍTÁS-FÜLEK CÍMKE-ELCSÚSZÁSA (Dávid jelezte, akadálymentesség):** a képernyőolvasó a
  mezők neveit EGGYEL elcsúsztatva mondta (első mező névtelen, a többi az ELŐZŐ címkéjét — pl.
  a formátum-listára „sebességkorlát"). GYÖKÉR: a StaticText a vezérlő UTÁN jön létre, a natív
  MSAA a Z-sorrendben előtte állót veszi névnek; a 3.29.5-ös `MoveBeforeInTabOrder` a wx 4.2.5-ben
  NEM rendezi át a natív MSAA-sorrendet, csak a wx-belső listát → nem oldotta meg. FIX
  (`settingsdialog.py`): új `_NamedAccessible(wx.Accessible)` + minden vezérlőn `ctrl.SetAccessible(...)`
  a HELYES névvel (csak a nevet írja felül, szerep/érték/állapot marad natív; GC-védelem:
  `self._accessibles`). A `_row` mostantól példány-metódus; `MoveBeforeInTabOrder` tartaléknak marad.
  VERIFIKÁLVA: fejnélküli példányosítás → mind a 8 vizsgált mező a SAJÁT címkéjét adja. VASSZABÁLY:
  natív wx-vezérlő nevét NE csak SetName/MoveBeforeInTabOrder-rel add meg (nem hat az MSAA-ra) →
  wx.Accessible.SetAccessible a megbízható. (Ugyanez a minta kell máshol is, ha „csúszik a címke".)
- **docconvert 1.1.4 — CWI KETTŐS KÓDOLÁS (Turai László mintája: „Ráadó és Anyicska"):** a fájl
  ÉRVÉNYES UTF-8, de valójában CWI→CP1250→UTF-8 mojibake (Á→Ź, Ó→•, É→U+0090) → auto rögtön
  visszaadta a kacatot, kézi CWI a táblát UTF-8 többájtokra futtatta. FIX: `_has_c1_controls`
  (C1-vezérlő = biztos mojibake-jel, nulla hamis pozitív) → `_undouble_cwi` (CP1250-vissza →
  CWI-2 tábla) + `read_cwi`; `_auto_decode` csak TISZTA UTF-8-nál short-circuitel. A CWI-2 tábla
  VÉGIG helyes volt — a gond a kettős kódolás. Verifikálva: mojibake auto+kézi = „RÁADÓ ÉS
  ANYICSKA", nyers egybájtos CWI nem regresszált, tiszta UTF-8 magyar/angol érintetlen. Az 1.1.3
  új CWI-címkéje oldotta a „nem tudtam kiválasztani" panaszt.

**Korábbi: 3.29.5 KIADVA ✅ (2026-07-06).** Core `v3.29.5` „Latest" (4 asset: SuperDL.exe,
SuperDL-cli.exe, SuperDL-Setup-3.29.5.exe, version-nélküli SuperDL-Setup.exe) + 3 modul-tag
(mod-konyvek-1.0.2, mod-mediatools-1.4.3, mod-docconvert-1.1.3) + modules.json a main-en +
forrás push (HEAD 2796f5b). Kulcs-szken TISZTA (forrás+zipek+binárisok, 2 kulcs, egy sem
található). yt-dlp 2026.7.4. Build-sorrend: onedir→ISCC(3.29.5)→CLI→onefile GUI (utolsó).
FONTOS a következő váltónak: a modul-release-eket a Core UTÁN létrehozva a GitHub az egyik
modult jelölte „Latest"-nek → a `releases/latest/download/…` 404 lett; JAVÍTVA
`gh release edit v3.29.5 --latest` + a modulok `--latest=false`. TANULSÁG: a Core-release-t
utoljára hozd létre, VAGY a végén tedd vissza kifejezetten latest-re. Laci CWI-mintája MÉG
NEM érkezett → a docconvert CWI-2 dekódoló TÁBLA finomítása továbbra is RÁ VÁR (a 1.1.3 csak
a címkéket tisztította). Tartalom (create maxima batch, tesztelve):

**(archív, korábbi állapot) 3.29.5 KÓDKÉSZ (Core 3.29.5 + konyvek 1.0.2 + mediatools 1.4.3 +
docconvert 1.1.3).** Több user-jelzés javítása (create maxima, tesztelve); modul-zipek +
modules.json KÉSZ (SHA-k egyeznek); a Core-build a „publikálás"-ra vár. FONTOS: Laci
CWI-mintája MÉG NEM ÉRKEZETT MEG — a docconvert CWI-2 tábla finomhangolása RÁ VÁR; a user:
„ha nem kapom meg holnap estig [2026-07-07], akkor publikálunk, de erről majd szólok" →
PUBLIKÁLÁS CSAK a user kifejezett jelére. Az új batch tételei:
- **KÖTEGELT KONVERTÁLÓ (Maxi):** tünet — kb. jó méretű mp3 készül, de a konverzió „nem
  ZÁRÓDIK LE", a fájlnak nincsenek adatai (bitráta/hossz), nem játszható. A tiszta
  tesztfájl 0,3 mp alatt HIBÁTLANUL lefut nálam → nem univerzális kód-bug, hanem Maxi
  konkrét videói. FIX (mediatools 1.4.3 `converter.py`/`convertwin.py`): (a) VALÓS IDEJŰ
  százalék — `for line in stdout` helyett `iter(readline, "")` (eddig a puffer benyelte a
  progresst); (b) az ffmpeg log-sorait `deque(maxlen=25)`-be gyűjtjük, HIBÁNÁL a valódi
  üzenet megjelenik (bejelentés első sora + `_finished` MessageBox a hibás fájlok teljes
  ffmpeg-hibájával) — eddig NÉMA volt. Így Maxi következő tesztje MEGMUTATJA a pontos okot.
- **„CSAK HANG" ALAPBÓL (Maxi):** a főablaki „Csak hang" pipa eddig nem maradt meg
  indítások közt. FIX (Core): `audio_only` beállítás (default False); `_apply_settings`
  visszaállítja a pipát, `_save_settings` menti, és a pipa `EVT_CHECKBOX`-ra AZONNAL ment
  → a következő indításkor ugyanúgy jön vissza. (A „Csak hang" SZÁNDÉKOSAN a főablakon
  marad, nem a Beállításokban — a settingsdialog dokumentációja is ezt írja.)
- **AI-KULCS ELSŐ MEZŐ (Dorina):** az NVDA a Beállítások AI-fülén a LEGELSŐ kulcs-mezőnél
  nem olvasta a címkét (a mező elé eső gomb miatt), mert a `_row` a StaticTextet a ctrl
  UTÁN hozza létre → az akadálymentességi fában a mező MÖGÉ került. FIX (Core
  `settingsdialog._row`): `lbl.MoveBeforeInTabOrder(ctrl)` → minden mező (az első is) a
  SAJÁT címkéjét kapja.
- **DOCCONVERT CWI-CÍMKÉK (docconvert 1.1.3):** tisztább legördülő-címkék —
  „Magyar CWI / CWI-2 (régi DOS, 437-alapú)" és „Régi DOS (CP437, nem magyar)". (A CWI-2
  dekódoló TÁBLA finomítása Laci mintájára vár — MÉG NEM.)
- **NAPI INFÓ nem indult (Ctrl+Shift+W és menü sem):** GYÖKÉR — a szervezés
  `open_dayinfo` a `core.frame`-et hívta, de a CoreContext-en NINCS `frame` (csak
  `main_frame`) → AttributeError → az ablak sose nyílt meg. FIX: `CoreContext.frame`
  ALIAS-property (a main_frame-et adja) — így a MÁR KIADOTT szervezés 1.2.2 is működik
  (Core-only fix, nincs szervezés-rebuild). (A „startup üdvözlés sem szól" rész: ha a
  user bekapcsolta a Teljes némítást, az SZÁNDÉKOS; egyébként külön ág — user-visszajelzésre vár.)
- **KÖNYVOLVASÓ „szaggat" (Szabó László):** az én 3.29.4-es mondatvég-fixem
  mellékhatása — a 140+ karakteres mondatot több darabra bontotta, a darabok közti
  szünet a mondat KÖZEPÉRE esett. FIX: (a) konyvek `readengine.CHUNK_LIMIT` 140→400 (a
  mondatok túlnyomó része EGY darab → folyamatos); (b) Core `audiobook._wrap_long` most
  TAGMONDAT-HATÁRON (vessző/pontosvessző/kettőspont/gondolatjel) tör, nem akárhol → a
  ritka >400 mondatnál is a vesszőhöz esik a szünet. Tesztelve: 239 kar.→1 darab; 639
  kar.→2 darab vesszőnél, minden szó megvan.

**3.29.4 KIADVA ✅ (2026-07-05).** Core `v3.29.4` „Latest” (4 asset, stabil linkek
200); 9 modul-release fent; `modules.json` élő a `main`-en; forrás push `77f23c4`;
kulcs-szken TISZTA (108 fájl); hírlevél kiírva. Nincs függő kiadási teendő.
Kiadott modul-verziók: docconvert 1.1.2, konyvek 1.0.1, szervezes 1.2.2,
mediatools 1.4.2, supermedia 1.2.2, iptv 1.0.2, radio 1.0.2, hangalamondas 1.0.3,
p2p 1.0.3.
TOVÁBBI (create maxima, MIND tesztelve, a fenti listán felül):
- **(5) KÖNYVOLVASÓ mondatvég-lehagyás JAVÍTVA (Core, audiobook.py):** a `chunk_text`
  a 140+ karakteres mondatot `sent[:limit]`-tel CSONKOLTA → a felolvasó lehagyta a
  mondatvégeket (Szabó László jelezte; JAWS-szal a szöveg teljes volt). FIX: új
  `_wrap_long()` szóhatáron darabol, SEMMIT el nem dobva. Igazolva: 263-karakteres
  mondat 2 darabban, minden szó megvan.
- **(6) EGYÉNI, TÉTELES, VAK-FÓKUSZÚ SÚGÓ MINDEN ESZKÖZ-ABLAKBAN (F1):** új Core
  `superdl/helpdialog.py` (görgethető, csak olvasható súgó-ablak, a fókusz a szövegen
  → a képernyőolvasó felolvassa; F1/Esc zárja) + benne a **„Támogatás" gomb** (a
  meglévő `supportwin.SupportDialog`-ot nyitja: Revolut+IBAN) és egy támogatás-sor a
  szöveg végén (Farkas: „hátha más is felfedezi"). MIND A 21 eszköz-ablak F1-re a saját
  tételes súgóját adja (Mire való / Lépésről lépésre vakon / Gyorsbillentyűk / Tipp),
  modul-oldali MessageBox-fallbackkel (régi Core-on is megy). CSAPDA-TANULSÁG: a
  `_help` szövegekben a záró idézőjel LEGYEN ” (U+201D), NE ASCII " – a „szó" ASCII "-e
  lezárja a Python-stringet; a string-összefűzős _help-eket háromszoros idézőjeles
  HELP-konstansra írtam át (ott a sima " biztonságos). NE fusson tömeges regex-csere a
  fájlokon (elrontja a meglévő kódot – egyszer megtörtént, git checkout-tal visszaálltam).

EREDETI NÉGY (create maxima), MIND tesztelve:
- **(1) Self-voice MAGYAR alapból** (Core, selfvoice.py): üres hang esetén magyar
  SAPI-hang (ha van), különben BEÉPÍTETT eSpeak magyar (`espeak:hu`) – SOHA a Zira
  angol (ez volt a listások „angolul szólal meg" panasza). `_effective_voice_desc()`;
  kézi hangválasztás tisztelve. Igazolva: üres→espeak:hu, „Zira"→SAPI.
- **(2) INDULÓ SZIGNÁL** (Core, sounds.py + gui + spec): `sounds.play_startup()` –
  user `~/.superdl/sounds/startup.wav` → BEÁGYAZOTT `superdl/startup.wav` (a user
  supdl.wav-ja, datas a 2 GUI-specben) → szintetizált akkord. `startup_signal`
  beállítás (alap BE), induláskor CallLater(250), FÜGGETLEN a teljes némítástól
  (hang, nem beszéd). Settings-checkbox. (Farkas: némítva is legyen indulás-jel.)
- **(3) docconvert 1.1.2** (modul): a KIMENETI kódlap-legördülő auto/cwi2 nélkül
  (`OUT_ENCODINGS`, alap UTF-8) → nincs „unknown encoding: auto"; `_write_txt`
  LookupError→utf-8 védőháló; a bemeneti lista duplikált „auto"-ja is javítva.
- **(4) mediatools 1.4.2 – VIDEÓVÁGÓ akadálymentesítés** (modul): a `_announce`
  mostantól KIMONDJA (self-voice) a visszajelzést (eddig csak státuszsor → a
  képernyőolvasó néma volt → „nem csinál semmit"); a feltétel-hibák FELOLVASOTT
  MessageBox-szal (`_cannot`, némítva is hallja a JAWS); `_section_markers`: pontosan
  2 markernél kijelölés NÉLKÜL is a kettő közt vág/ment; kimondott útmutatás 2.
  marker után és hozzáfűzés után. A MOTOR JÓ VOLT (valódi ffmpeg-teszt: cut 10→7mp,
  concat 10+6→16mp) – a hiba tisztán akadálymentességi/UX volt.
- **PUBLIKÁLÁSKOR:** Core-build (onedir→ISCC→CLI→onefile) + kulcs-szken + v3.29.4
  (4 asset) + 2 modul-release (mod-docconvert-1.1.2, mod-mediatools-1.4.2) +
  modules.json push + forrás push + hírlevél. FONTOS: a `superdl/startup.wav`
  bekerült a repóba (bundle-höz kell).

**Korábbi: 3.29.3 KIADVA ✅ (2026-07-03).** Core `v3.29.3` „Latest", 4 asset; forrás push
`c8be77c`; kulcs-szken TISZTA (96 fájl). Modulok VÁLTOZATLANOK. Hírlevél kiírva.
Backlog #1 = Farkas István hordozható-önfrissítés robusztussága, KIADVA:
- `selfupdate.py`: `mark_update_pending(target)` (jelzőt ír `~/.superdl/
  update_pending.json`-ba a csere indításakor) + `check_update_result()`
  (induláskor: a futó verzió eléri-e a célt → "ok"/"failed", a jelzőt törli).
  Az `apply`/`apply_installer` új `target_version` paramétert kap. Swapper
  move-retry 30→120 mp (AV zárolás). superdl_gui: `_check_update_result`
  (CallLater 900 ms) – SIKER: toast; HIBA: felolvasott MessageBox a kézi
  letöltő linkkel („valószínűleg a víruskereső fogta a fájlt"). Verzió 3.29.3.
  Tesztelve: jelző-logika ok/failed helyes, MainFrame felépül, no-op jelző nélkül.
- **Publikáláskor:** Core-build (onedir→ISCC→CLI→onefile UTOLJÁRA) + kulcs-szken +
  v3.29.3 (4 asset) + forrás push + hírlevél. Modulok VÁLTOZATLANOK.

Backlog #2 = IPTV 1.1.0: **MÁR KÉSZ a kódban** (a kiadott iptv 1.0.1-ben) – a
player_api hitelesítés (`xtream_authenticate` beszélő hibákkal), kategóriák
(`xtream_live_categories`+`xtream_live_streams`), m3u-tartalék (`xtream_load`) és
a pre/post-login állapotgép mind bent van. NINCS érdemi új IPTV-munka (az „1.1.0"
csak tervezett címke volt; opcionálisan bumpolható a modul 1.1.0-ra kozmetikából).

**Korábbi: 3.29.2 KIADVA ✅ (2026-07-02).** Core `v3.29.2` „Latest", 4 asset; forrás push
`25d7bdd`; kulcs-szken TISZTA (96 fájl). Modulok VÁLTOZATLANOK (Core-only fix).
- **AKADÁLYMENTESSÉGI HOTFIX:** a 3.29.0-ban bevezetett opener `_bring_to_front`
  a KERETRE hívott `SetFocus()`-t → ellopta a fókuszt a vezérlőtől, amire a
  modul-ablak a saját __init__-jében ráállította (pl. rádió keresőmező) → a
  képernyőolvasónak „üres ablak" (Karcsi jelezte a rádión). FIX: SetFocus KIVÉVE
  a `_bring_to_front`-ból (marad Show + Iconize(False) + Raise; a Raise aktivál,
  a wx visszaállítja az utolsó vezérlő-fókuszt). MINDEN modul-ablakot érintett.
- Éles megerősítés Karcsitól: a telepítős auto-újraindítás (#2) MŰKÖDIK.
- TANULSÁG: modul-ablak megnyitásakor SOHA ne hívj a KERETRE SetFocus()-t – a
  vezérlő-fókuszt hagyd az ablak __init__-jére (screen reader!).

**Korábbi: 3.29.1 KIADVA (2026-07-02).** Core `v3.29.1`, 4 asset feltöltve;
forrás pusholva (`2bbeaf1`); kulcs-szken TISZTA (96 fájl). Modulok VÁLTOZATLANOK
(nem kellett újra feltölteni – a fix a Core-ban van).

Mit tartalmaz a 3.29.1:
- **KRITIKUS menü-regresszió fix (Claude):** a `CoreContext` nem proxyzta az
  `add_submenu`-t → a 3.29.0 menü-átrendezése VALÓJÁBAN NEM lépett életbe (a
  modulok a régi saját menüikbe estek vissza; ezért jelezte Zsolt, hogy „nem
  működnek a modulok"). Fix: `CoreContext.add_submenu` (modkit) + `WxHost.
  add_submenu` most FIND-OR-CREATE (nem duplikál újratöltéskor) + opener
  holt-ablak érzékelés (`win.IsShown()` próba). TESZT-RÉS is javítva: mostantól
  a CoreContext-en át tesztelünk (a headless menü-teszt eddig a hostot hívta).
- **Indító nézet (Zsolt/Laci):** `hide_url_row` beállítás – induláskor elrejti a
  letöltési URL-sort; `_reveal_url_row` (Ctrl+N / Fájl→Új letöltés) előhozza; az
  induló üdvözlés az aktív letöltések számát is bemondja. (superdl_gui + settingsdialog)
- **Grok 10 logikai javítása** (átnézve+jóváhagyva): audioengine, freshvideoswin,
  manager, radiorec, search, segment, ytchannel, superdl_gui – lásd
  `C:\Users\msn\Documents\pcsuperdl.txt`.

**Nincs függő kiadási teendő.** Hírlevél kiírva a listának.

**Buildelési tanulság:** onefile + onedir NÉV-ÜTKÖZIK a `dist`-ben → SORREND:
onedir + telepítő, UTOLJÁRA onefile GUI. (Most így ment, jó.)

**Backlog (§7, csak „create maxima"-ra):** IPTV 1.1.0; hordozható önfrissítés
robusztussága (a néma csere-hiba láthatóvá tétele + hosszabb retry – Farkas István
jelezte, hogy AV mellett a hordozható frissítés csendben nem cserél).

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
