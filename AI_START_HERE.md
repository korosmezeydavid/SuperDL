# SuperDL — OLVASD EL ELŐSZÖR (AI asszisztensnek)

**Utolsó frissítés:** 2026-07-17 | **Verzió:** 1.54.9 (versionCode 100)

Ha te egy AI vagy (Claude, Grok, egyéb), és most kapcsolódtál be a SuperDL
fejlesztésébe: ez a fájl a belépőpont. Olvasd el végig, mielőtt bármit
módosítanál. A részletek a `dokumentumok/fejlesztesi-naplo.txt`-ben vannak.

---

## 1. Mi ez a projekt

Magyar nyelvű Android **launcher vak és gyengénlátó felhasználóknak**.
Gesztusokkal (fel/le/bal/jobb swipe) és hanggal (TTS + diktálás) vezérelhető.
Natív Android app, Kotlin, minSdk 26, targetSdk 34.

A fejlesztő maga is vak, TalkBack képernyőolvasót használ. **Ez nem egy
absztrakt "accessibility feature" — ez a napi használatban lévő telefonja.**
Ebből következik minden alábbi szabály.

## 2. Tervezési alapelvek (ezeket ne sértsd meg)

- **Minden funkciónak hangosan meg kell szólalnia.** Néma sikerre/hibára
  nincs visszajelzés. Ha egy művelet nem megy, mondd ki, miért.
- **Inkább hallgat, mint téveszt.** A pénzfelismerő filozófiája az egész
  appra igaz: a téves információ rosszabb, mint a "nem tudom".
- **Egy menüpont, egy művelet, oda-vissza.** Pl. az egyéni csengőhangnál az
  "Alapértelmezett" választása = törlés. Ne csinálj külön "törlés" menüpontot,
  amit meg kell keresni.
- **Gesztusok:** fel = előző/ismétlés, le = következő, jobbra = belépés/
  megerősítés, balra = vissza/megszakítás (a diktálás is leáll).
- A kód kommentjei magyarul, gyakran a **MIÉRT**-tel kezdve. Tartsd ezt a
  szokást — a "miért" a hasznos, a "mit" látszik a kódból.

## 3. !! A LEGFONTOSABB: DEBUG vagy RELEASE?

**A telefonon a DEBUG variáns fut** (`com.superdl.launcher.debug`).
A release (`com.superdl.launcher`) **NINCS telepítve**.

Ez két külön csomagnév, külön SharedPrefs-szel. Ha release APK-t telepítesz:
- NEM frissíti a meglévőt → **második app** kerül fel, üres beállításokkal
- két launcher közül kellene választani, vakon, TalkBackkel — kellemetlen
- a beállítások (csengőhangok, ébresztők, kedvencek) nem látszanának át

**=> Fejlesztés után mindig: `assembleDebug` + `adb install -r` a debug APK-val.**
Az `install -r` megtartja az összes beállítást.

Ellenőrzés, hogy tényleg frissítés történt-e:
`firstInstallTime` régi + `lastUpdateTime` friss = valódi frissítés, adatok megvannak.

## 4. Környezet

```powershell
cd C:\Users\msn\Documents\SuperDL-Android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'   # kötelező
$adb = "C:\Users\msn\AppData\Local\Android\Sdk\platform-tools\adb.exe"  # NINCS a PATH-on
```

Telefon: Ulefone Armor 24, serial `3116TF1010002416`

Szokásos kör:
```powershell
.\gradlew.bat assembleDebug *> build_log_debug.txt; "EXIT=$LASTEXITCODE"
& $adb -s 3116TF1010002416 install -r app\build\outputs\apk\debug\SuperDL-<verzió>-debug.apk
```

## 5. Build buktatók (ezekbe bele fogsz futni)

**TTS HUROK-BUG: gesztus-kiváltott kilépésnél NE `speakThen { finish() }`!**
A `speakThen(msg) { finish() }` a finish()-t csak a TTS BEFEJEZÉSE UTÁN hívja.
Ha a felhasználó közben újra söpör (mert nem történt semmi láthatóan), a még
élő Activity ÚJRA lefuttatja, és a mondat 3-4-szer elhangzik, mielőtt tényleg
kilép. Vakon ez kritikus: a felület "elszalad" a felhasználó tempója alatt.
HELYES minta gesztus-kilépésnél: `tts.speak(msg); finish()` — a beszéd elindul,
a kilépés AZONNALI (a QUEUE_FLUSH miatt a következő képernyő beszéde úgyis
felülírja). 2026-07-18-án 13 helyen javítva (music, podcast, youtube, light,
color, hearingaid, filemanager, textreader, 2 trainer, 5 játék).
KIVÉTEL: egyszeri hibaüzenet + kilépés (pl. "nincs kamera-engedély"), ami
NEM ismételhető söpréssel — ott a speakThen maradhat, mert nem hurkol.

**A PORTÁL ROUTINGJA A QUERY-T LEVÁGVA NÉZI (route, nem path).**
A `handleClient` a nyers `path`-ból csinál egy `route = path.substringBefore("?")`
változót, és a `when` ágak ezt használják (`route == "/backup"`). MIÉRT: a
GET-formok a query-be teszik a PIN-t (`?pin=1234`), és a pontos egyezés
(`path == "/x"`) elbukna, a kérés a 404-es főoldalra esne. Tünet: a gomb
"visszaugrik a főoldalra" letöltés helyett. Az AUTH viszont a nyers `path`-ot
kapja (`isAuthorized(headers, path)`), mert annak kell a `pin=`.

**SOHA ne szerkeszd a .kt fájlokat PowerShell Get-Content/WriteAllLines-szal!**
2026-07-17-én ez tönkretette a WifiPortalServer.kt teljes ékezetes tartalmát
(mojibake: minden magyar karakter elromlott, 160+ helyen). A PowerShell a
rendszer OEM-kódlapján olvas és ír, nem UTF-8-on. Helyreállítás CP1250-es
Python-dekódolással sikerült, de ez szerencse volt. HASZNÁLD a Desktop Commander
edit_block/write_file eszközét, ami helyesen kezeli az UTF-8-at.
Új portál-oldal felvételekor a fül KÉT helyre kell:
1. `PortalControlPages.header()` — a vezérlő-oldalak (SMS, Névjegyek, ...)
   fülsávja, a `tab()` segédfüggvénnyel
2. `WifiPortalServer.buildIndexPage()` (~687. sor) — a FŐOLDAL (`/`) saját,
   kézzel írt `<a class="tab">` sávja
A kettő független! A főoldal címe „SuperDL fájlportál", a vezérlő-oldalaké
„SuperDL vezérlő" — ebből lehet felismerni, melyiket látod. 2026-07-17-én a
Patika Őrangyal fül csak az 1-esbe került be, ezért a főoldalon nem látszott,
és úgy tűnt, mintha a régi kód futna.

**A PORTÁL SZERVERE TÚLÉLI A TELEPÍTÉST.** A `WifiPortalService` foreground
service. Ha a portál BE volt kapcsolva telepítéskor, a régi példány tovább fut,
és a RÉGI oldalt szolgálja ki — az új fül/útvonal nem jelenik meg, hiába jó az
APK. Megoldás: a telefonon Zene és Média → WiFi fájlportál **ki, majd be**
(új PIN-t mond be). Ellenőrzés:
`adb shell "dumpsys activity services com.superdl.launcher.debug"` — fut-e a
WifiPortalService, és mióta.

**APK-tartalom ellenőrzése: a nyers bájtokban KERESNI FÉLREVEZET.** A dex-ek
tömörítve vannak az APK-ban, így a `ReadAllBytes` + `Contains("valami")` **False**-t
ad akkor is, ha a kód benne van. Ki kell csomagolni (`ZipFile::ExtractToDirectory`),
és a `classes*.dex` fájlokban keresni. 2026-07-17-én ez a hamis negatív majdnem
oda vezetett, hogy rossz helyen keressük a hibát.

**MCP timeout ≠ a build meghalt.** A teljes release build ~6 perc, ez túllépi
az MCP hívás időkorlátját. A `start_process` timeout hibát ad, **de a build
tovább fut**. Ilyenkor: `list_sessions` → `read_process_output` a PID-del.
**Ne indíts újat.** A kimenetet fájlba irányítsd (`*> build_log.txt`) — a
`| Select-Object -Last 40` a pipeline végéig pufferel, közben nem látsz semmit.

**R8 / ProGuard hibák release buildnél.** Az R8 elhasal a hiányzó opcionális
osztályokon. A megoldás mindig ugyanaz: az R8 legenerálja a kellő sorokat ide:
`app\build\outputs\mapping\release\missing_rules.txt` → bemásolni a
`app\proguard-rules.pro` végére. Eddig így kezelve: PDFBox JPEG2000,
BouncyCastle LDAP, Tink KeysDownloader.

## 6. Architektúra — amit tudnod kell

Feature-alapú monolit, **nem** Clean Architecture. Ne próbáld annak tekinteni.

- `MainActivity.kt` — **13000+ sor**, menü-állapotgép, TTS, gesztusok
- ~372 Kotlin fájl, lapos csomagstruktúra (`alarm`, `contacts`, `currency`, ...)
- **1 db ViewModel** az egész projektben (`CurrencyRecognizerViewModel`)
- **Nincs** DI, Room, DataStore, Retrofit, Repository, UseCase
- Adatréteg: **41 db `*Store.kt`** — SharedPrefs + JSON
- Build: Groovy `build.gradle` (nem `.kts`), single-module

**Minta-követés:** ha új funkciót kötsz be, keress egy meglévő hasonlót és
kövesd. Pl. az `alarmTonePickerLauncher` volt a minta a névjegy-csengőhanghoz.

## 7. Hol tartunk most

**Kész és telepítve (1.54.9):** névjegyenkénti egyéni csengőhang — a hang a
telefonszámhoz kötve (normalizálva, utolsó 9 számjegy), bejövő híváskor az
`IncomingCallRinger` keresi.

**Kész és telepítve (1.54.9):** WiFi portál — névjegyek tömeges törlése
(checkbox + megerősítő oldal) és a **Patika Őrangyal** oldal (gyógyszer-
emlékeztetők: hozzáadás gépelve, be/ki, törlés, tömeges törlés).

**Következő lépés:** tesztelés a telefonon.
- Csengőhang: Névjegyzék → névjegy → context menü → „Egyéni csengőhang"
- Portál: Névjegyek fül → tömeges törlés; Patika Őrangyal fül → új emlékeztető

**A csengőhang-munka egy 4 lépéses tervvel indult** — egy maradt:
1. Portál: hangmappák — ✅ kész
2. Telefon: névjegyenkénti csengőhang — ✅ kész (1.54.9)
3. Portál: névjegy-szerkesztés — ❌ **el sem kezdődött**
4. Portál: checkbox + tömeges névjegy-törlés — ✅ kész

**Nagy nyitott téma:** `huf_banknote_detector.tflite` **hiányzik** az
assets-ből. A YOLO training lefutott (`tools/runs/banknote/huf_detect-2/best.pt`),
de a TFLite export nincs bemásolva → a two-stage pénzfelismerő pipeline ki van
kapcsolva, csak fallback fut.

A teljes lista: `dokumentumok/fejlesztesi-naplo.txt` 9. szakasz.

## 8. Munkamódszer

- **A hosszú session betelik, és mindig rossz helyen.** Ez a projekt sok
  fájl-tartalmat és buildnaplót termel, ami megtölti a kontextusablakot.
  2026-07-17 előtt pontosan így szakadt meg a névjegy-csengőhang munka: négy
  fájl készen állt, csak a MainActivity-bekötés hiányzott — és semmi nem
  őrizte meg, hogy hol tartunk. **Ezért van ez a fájl.** Írj bele, mielőtt
  betelik, ne utána.
- **Több AI is dolgozhat a projekten** (Claude, Grok) — a fejlesztő eszköz
  szerint vált. A terminálos munkát Claude + Desktop Commander viszi, mert a
  PowerShell kézi használata vakon kényelmetlen.
- **Nézd meg, mi van a lemezen, mielőtt hiszel a leírásnak.** A kód az igazság.
  Új funkció előtt keress rá: létezik-e már a `*Store.kt`, be van-e kötve
  (`start_search` a HASZNÁLATRA, ne csak a fájl létére).
- **Átvételkor a bekötést ellenőrizd először.** A leggyakoribb félbemaradás:
  az osztály kész, az enum-érték kész, de a `when` ág hiányzik. Vakon ez a
  legrosszabb hibafajta: a menüpont kimondja magát, aztán néma.
- **Terminál parancsokat futtasd le magad** Desktop Commanderrel, ne add oda
  kézi futtatásra.
- **Minden fejlesztési kör után frissítsd a naplót** (`fejlesztesi-naplo.txt`
  2., 9., 10. szakasz) **és ezt a fájlt**, ha a fentiek bármelyike változott.
  Ez nem formalitás: enélkül a következő session vakon indul.

## 9. Fájlok

| Fájl | Mit tartalmaz |
|------|---------------|
| `AI_START_HERE.md` | **ez a fájl** — belépőpont, mindig ezzel kezdd |
| `dokumentumok/fejlesztesi-naplo.txt` | fő napló: állapot, tervek, fejlesztési körök |
| `SuperDL_Project_State.md` | mély technikai riport (2026-07-03, részben elavult) |
| `CHANGELOG.md` | verzió-változások |
| `dokumentumok/javitas.txt` | pénzfelismerő javítás napló |
| `dokumentumok/osszefoglalom.txt` | korábbi összefoglalók (1.36.x–1.37.x) |
| `app/src/main/assets/elena_tudas_superdl.txt` | Elena asszisztens tudásbázis |
