# SuperDL – Projekt Összefoglaló

**Dátum:** 2026. július 17.
**Verzió:** 1.54.9 (versionCode 100)
**Csomagnév:** com.superdl.launcher (release) / com.superdl.launcher.debug (debug)
**Fejlesztő:** Kőrösmezey Dávid

---

## Megjegyzés a névhez

A dokumentáció készítésekor a projekt egészében rákerestem a "Verrza" névre:
**nulla találat**. Sem a kódban, sem a manifestben, sem a build-fájlokban, sem a
dokumentációban nem szerepel. A projekt neve mindenhol **SuperDL** (Super
Digital Launcher / Super Digital Lounge), a csomagnév `com.superdl.launcher`.

Ezért ez a dokumentum végig a SuperDL nevet használja. Ha a "Verrza" egy tervezett
új név vagy egy másik projekt, azt jelezd — akkor átnevezhető.

---

## 1. Mi ez?

A SuperDL egy magyar nyelvű Android **launcher** (kezdőképernyő-alkalmazás)
elsősorban **vak és gyengénlátó felhasználóknak**. A telefon teljes kezelését
átveszi: a főképernyőtől a hívásokon, üzeneteken, ébresztőkön át a kamerás
felismerőkig minden egyetlen, egységes, felolvasott menürendszerben érhető el.
Négy gesztussal (fel, le, balra, jobbra söprés) és hanggal (beszédfelismerés +
felolvasás) vezérelhető, vizuális felület nélkül is teljesen használható. A
fejlesztő maga is vak és TalkBack képernyőolvasót használ — az alkalmazás a napi
használatában él, nem elméleti akadálymentesítési gyakorlat. Külön kiemelendő a
WiFi portál: a telefon egy webszervert indít, amin keresztül a felhasználó a
saját gépéről, rendes billentyűzettel intézheti azt, amit diktálva nehéz
(például pontos gyógyszerneveket vagy hosszú jelszavakat).

---

## 2. Architektúra

### Nyelv és keretrendszer

- **Nyelv:** Kotlin (100%, 393 .kt fájl)
- **Platform:** natív Android, minSdk 26 (Android 8.0), targetSdk 34, compileSdk 34
- **UI:** vegyes — Jetpack Compose (BOM 2024.02.00) és klasszikus View/XML
- **Build:** Gradle, Groovy `build.gradle` (nem .kts), **egyetlen modul** (`:app`)
- **Aszinkron:** kotlinx-coroutines-android 1.7.3, illetve nyers `Thread`-ek

### Architektúra jellege — őszintén

Ez **feature-alapú monolit**, nem Clean Architecture. Amit tudni kell:

- `MainActivity.kt` = **12 443 sor** — menü-állapotgép, TTS, gesztusok, flow-k
- 65 csomag, lapos szerkezet (alarm, contacts, currency, gps, ...)
- **1 darab ViewModel** az egész projektben (`CurrencyRecognizerViewModel`)
- **Nincs** dependency injection (Hilt/Koin), **nincs** Room, **nincs** DataStore,
  **nincs** Retrofit, **nincs** Repository/UseCase réteg
- **Adatréteg: 44 darab `*Store.kt`** — mind SharedPreferences + JSON (`org.json`),
  közös segéd: `storage/JsonPrefsHelper.kt` (séma-verziózással, migrációval)
- Hálózat: nyers `HttpURLConnection` és `Socket` (még az SMTP/IMAP is saját kód)

Ez nem szépséghiba-lista, hanem a valóság: a mintakövetés így működik — ha új
funkciót írsz, keress egy meglévő hasonlót és kövesd azt.

### Fő mappák (app/src/main/kotlin/com/superdl/launcher/)

Zárójelben a fájlok száma.

- `alarm` (6) – ébresztők, ütemezés, riasztó képernyő, boot utáni visszaállítás
- `apps` (5) – külső alkalmazások listája, indítása, kedvencek
- `assistant` (14) – Elena hangasszisztens, felébresztő szó figyelés, rendszer-asszisztens integráció
- `battery` (5) – akkumulátor őrség, töltöttség figyelés
- `book` (8) – könyvolvasó, könyvjelzők, könyvtár
- `calculator` (1) – diktálható számológép
- `calendar` (9) – naptár olvasás, programfelvétel, emlékeztetők
- `call` (12) – hívás indítás/fogadás, tárcsázó, InCall felület, csengetés
- `callfilter` (7) – hívásszűrés (letiltott/rejtett számok)
- `calllog` (3) – hívásnapló
- `camera` (8) – arc/szelfi kamera, minőségbeállítás
- `cardorganizer` (4) – bankkártya/kártya felismerés kamerával
- `color` (2) – színfelismerő
- `contacts` (9) – névjegyzék, szinkronizálás, **egyéni csengőhang névjegyenként**
- `crash` (1) – összeomlás-kezelés
- `currency` (18) – **pénzfelismerő** (offline forint bankjegy, TFLite)
- `dictaphone` (23) – profi diktafon (formátumok, minőség, könyvtár)
- `email` (9) – **saját SMTP küldés és IMAP olvasás** (nem JavaMail!)
- `environment` (8) – környezeti kitekintő, objektumfelismerés, térbeli leírás
- `favorites` (4) – kedvenc kontaktok
- `feedback` (20) – **hangvisszajelzés-rendszer**: gesztushangok, hangtémák, riasztóhangok, eszközállapot-hangok
- `files` (5) – fájlkezelő, **WiFi portál szerver és oldalai**
- `flow` (1) – az `AppFlow` állapot-definíciók
- `games` (19) – UNO, Blackjack, Póker, Félkarú rabló, Mille Bornes
- `gestures` (1) – `SwipeGestureListener`
- `gps` (25) – helymeghatározás, POI radar, hang-iránytű, környezeti figyelő
- `hearingaid` (6) – hallás erősítő (mikrofon → fülhallgató valós időben)
- `info` (4) – napi üdvözlés, információk
- `input` (2) – számbillentyűzet, PIN-pad
- `legal` (1) – jogi szövegek
- `light` (2) – fénydetektor (hangmagassággal jelez)
- `locationwatch` (10) – helyszín-tanítás és felismerés fotóprofilokból
- `lock` (8) – saját PIN zárolás + rendszer PIN akadálymentesítő segéd
- `medication` (9) – **Patika Őrangyal** (gyógyszer emlékeztető)
- `menu` (1) – `MenuTree.kt`, a teljes menüfa egy helyen
- `music` (5) – zenelejátszó, EQ, lejátszási módok
- `navigation` (2) – navigációs segédek
- `news` (2) – RSS hírolvasó
- `notes` (2) – jegyzetek
- `notifications` (4) – értesítés-figyelő
- `patrol` (3) – őrség (idő bemondás, éjszakai csend)
- `podcast` (6) – podcast keresés, feliratkozás, letöltés, OPML
- `qr` (3) – QR-kód olvasó
- `route` (6) – GPS útvonal rögzítés és hangos követés
- `search` (4) – internetes keresés felolvasva
- `security` (3) – biztonsági segédek
- `settings` (2) – beállítás-tárolók
- `shopping` (3) – bevásárlólista
- `sms` (13) – SMS küldés/fogadás, alapértelmezett SMS-app szerep
- `sos` (3) – S.O.S. vészjelzés
- `sound` (4) – csengőhang-választó
- `storage` (1) – `JsonPrefsHelper` (az összes Store alapja)
- `summary` (2) – napi összefoglaló
- `system` (4) – rendszerkapcsolók (WiFi, BT, hotspot)
- `textreader` (7) – OCR szövegolvasó (gyógyszerdoboz, címke, folyamatos)
- `timer` (8) – időzítők
- `tools` (1) – eszköz-segédek
- `train` (5) – vonat menetrend
- `training` (2) – tanuló mód, hangok megismerése
- `transit` (5) – tömegközlekedés, megállók
- `tts` (7) – **beszédszintézis kezelése**, motor- és hangválasztás
- `util` (1) – vegyes segédek
- `voice` (6) – beszédfelismerés, diktálás, kiejtés-javítások
- `weather` (2) – időjárás
- `youtube` (5) – YouTube keresés és lejátszás

### Belépési pontok

- **Application:** `SuperDlApplication.kt` (33 sor)
- **Fő belépő:** `MainActivity` – `HOME` + `DEFAULT` intent-filterrel (ez teszi
  launcherré, prioritás 999), továbbá `ASSIST` és `VOICE_ASSIST` filterekkel
  (asszisztensként is indul)
- **32 Activity, 24 Service, 10 BroadcastReceiver** összesen

---

## 3. Funkciók listája – Részletesen

A menüpontok a `menu/MenuTree.kt`-ből származnak, a jogosultságok a
manifestből. A formátum:
`- [Név] | Hely: ... | Működés: ... | Permission: ... | Web: Igen/Nem`

### 3.1 Telefon és Hívások

- **Névjegyből hívás** | Hely: Telefon és Hívások > Névjegyből hívás | Működés: név diktálása, találatok felolvasása, hívás indítása | Permission: READ_CONTACTS, CALL_PHONE, RECORD_AUDIO | Web: Nem
- **Névjegyzék** | Hely: Telefon és Hívások > Névjegyzék | Működés: névjegyek böngészése betűindexszel, kontextusmenüvel (hívás, SMS, egyéni csengőhang, szerkesztés, törlés) | Permission: READ_CONTACTS | Web: Igen (/contacts)
- **Egyéni csengőhang névjegyenként** | Hely: Névjegyzék > névjegy > kontextusmenü > Egyéni csengőhang | Működés: a hang a **telefonszámhoz** kötődik (normalizálva, utolsó 9 számjegy), bejövő híváskor az `IncomingCallRinger` ezt keresi először; az "Alapértelmezett" választása törli | Permission: READ_CONTACTS, READ_MEDIA_AUDIO | Web: Nem
- **Névjegyek szinkronizálása** | Hely: Telefon és Hívások > Névjegyek szinkronizálása | Működés: `ContactSyncHelper` + ütemezett `ContactSyncReceiver` | Permission: READ_CONTACTS, GET_ACCOUNTS | Web: Nem
- **Hívásnapló felolvasása** | Hely: Telefon és Hívások > Hívásnapló felolvasása | Működés: bejövő/kimenő/nem fogadott hívások felolvasása | Permission: READ_CALL_LOG | Web: Nem
- **Szám tárcsázása** | Hely: Telefon és Hívások > Szám tárcsázása | Működés: számjegyenkénti bevitel, vágólap-beillesztés fel-söpréssel | Permission: CALL_PHONE | Web: Nem
- **Kedvenc hozzáadása / hívása / törlése** | Hely: Telefon és Hívások > Kedvenc... | Működés: gyorshívó lista kezelése | Permission: READ_CONTACTS, CALL_PHONE | Web: Nem
- **Új névjegy létrehozása** | Hely: Telefon és Hívások > Új névjegy létrehozása | Működés: név és szám diktálása/bevitele | Permission: WRITE_CONTACTS | Web: Igen (/contacts, gépelve)
- **Hívás fogadása / kezelése** | Hely: automatikus (bejövő híváskor) | Működés: `SuperInCallService` (BIND_INCALL_SERVICE) + `IncomingCallActivity` / `InCallActivity`, zárolt képernyőn is megjelenik | Permission: ANSWER_PHONE_CALLS, READ_PHONE_STATE, MANAGE_OWN_CALLS | Web: Nem
- **Hívás szűrő** | Hely: Beállítások > Biztonság > Hívás szűrő mód | Működés: 4 szintű szűrés, `SuperCallScreeningService` (BIND_SCREENING_SERVICE), tartalék: `IncomingCallReceiver` a PHONE_STATE-re | Permission: READ_PHONE_STATE, READ_CONTACTS | Web: Nem
- **Alapértelmezett telefon app beállítása / állapota** | Hely: Beállítások > Biztonság > Alapértelmezett telefon... | Működés: rendszerpárbeszéd indítása, állapot felolvasása | Permission: – | Web: Nem

### 3.2 SMS írás/olvasás

- **Bejövő üzenetek olvasása** | Hely: Üzenetek és E-mail > Bejövő üzenetek olvasása | Működés: SMS-ek felolvasása, névjegy-név feloldással | Permission: READ_SMS | Web: Igen (/sms)
- **Kimenő üzenetek** | Hely: Üzenetek és E-mail > Kimenő üzenetek | Működés: elküldött SMS-ek felolvasása | Permission: READ_SMS | Web: Nem
- **Üzenet diktálása és küldése** | Hely: Üzenetek és E-mail > Üzenet diktálása és küldése | Működés: címzett + szöveg diktálása, küldés | Permission: SEND_SMS, READ_CONTACTS, RECORD_AUDIO | Web: Igen (/sms + /sms/send)
- **SMS fogadás** | Hely: automatikus | Működés: `SmsDeliverReceiver` (SMS_DELIVER, alapértelmezett SMS-appként) + tartalék `SmsReceivedReceiver` (SMS_RECEIVED, prioritás 999, OEM-eken ahol az első nem megbízható) + `SmsInboundService`; mindkettő `directBootAware` | Permission: RECEIVE_SMS, BROADCAST_SMS | Web: Nem
- **MMS fogadás** | Hely: automatikus | Működés: `MmsWapPushReceiver` (WAP_PUSH_DELIVER) | Permission: RECEIVE_MMS, RECEIVE_WAP_PUSH, BROADCAST_WAP_PUSH | Web: Nem
- **SMS írás külső appból** | Hely: rendszer megosztás/link (`smsto:`, `sms:`, `mms:`) | Működés: `SmsComposeActivity` | Permission: SEND_SMS | Web: Nem
- **Válasz üzenettel hívás közben** | Hely: automatikus | Működés: `HeadlessSmsSendService` (RESPOND_VIA_MESSAGE) | Permission: SEND_RESPOND_VIA_MESSAGE | Web: Nem
- **Alapértelmezett üzenet app beállítása / állapota** | Hely: Üzenetek és E-mail > Alapértelmezett üzenet app... | Működés: rendszerpárbeszéd, állapotjelentés | Permission: – | Web: Nem
- **SMS törlés / válasz** | Hely: csak weben | Működés: portál `/sms/delete`, `/sms/reply` | Permission: WRITE_SMS | Web: Igen

### 3.3 E-mail

Fontos: **nincs JavaMail könyvtár**. Az SMTP és IMAP nyers `Socket`/`SSLSocket`
alapú **saját implementáció** (`email/SmtpSender.kt`, `email/ImapReader.kt`).

- **E-mail diktálása és küldése** | Hely: Üzenetek és E-mail > E-mail diktálása és küldése | Működés: címzett, tárgy, szöveg diktálása, küldés saját SMTP-vel | Permission: INTERNET, RECORD_AUDIO | Web: Nem
- **E-mailek olvasása** | Hely: Üzenetek és E-mail > E-mailek olvasása | Működés: IMAP-on beolvasás, felolvasás | Permission: INTERNET | Web: Nem
- **E-mail küldő beállítása / felolvasása / törlése** | Hely: Üzenetek és E-mail > E-mail küldő... | Működés: SMTP-fiók adatai; a jelszó **titkosítva** tárolva (androidx.security-crypto, hardveres Keystore) | Permission: INTERNET | Web: Nem
- **E-mail címek importálása / hozzáadása / mentett címek** | Hely: Üzenetek és E-mail > E-mail cím... | Működés: címjegyzék kezelése, import a fiókokból | Permission: GET_ACCOUNTS | Web: Nem

### 3.4 Névjegyzék szerkesztés

- **Böngészés** | `ContactBookItem`, `ContactLetterIndex` (betűugrás) | Permission: READ_CONTACTS | Web: Igen (/contacts)
- **Létrehozás** | `ContactHelper` + `WRITE_CONTACTS` | Web: Igen (/contacts/add)
- **Törlés** | telefonon: kontextusmenü, egyesével; weben: **egyesével és tömegesen, checkboxszal, megerősítő oldallal** | Permission: WRITE_CONTACTS | Web: Igen (/contacts/delete-confirm → /contacts/delete)
- **Névjegy küldése SMS-ben** | csak weben | Web: Igen (/contacts/share)
- **Szerkesztés** | telefonon van (kontextusmenü > Névjegy szerkesztése); **weben NINCS** — ez a hiányzó negyedik mérföldkő

### 3.5 Fájlkezelés

- **Fájlkezelő** | Hely: Eszközök > Fájlkezelő | Működés: `FileManagerActivity`, böngészés, műveletek | Permission: READ_MEDIA_AUDIO, READ_EXTERNAL_STORAGE (max SDK 32) | Web: Nem
- **Fájlátvitel géppel (USB)** | Hely: Zene és Média > Fájlátvitel géppel | Működés: a rendszer USB-képernyőjének megnyitása | Permission: – | Web: Nem
- **WiFi fájlportál be és ki** | Hely: Zene és Média > WiFi fájlportál be és ki | Működés: `WifiPortalService` (foreground, dataSync) indít egy HTTP-szervert; a telefon bemondja a címet és a PIN-t | Permission: INTERNET, ACCESS_WIFI_STATE, FOREGROUND_SERVICE | Web: **ez maga a web**
- **Fájlmegosztás appok felé** | `FileProvider` (`${applicationId}.fileprovider`) | Web: Nem

### 3.6 Idő és Szervezés

- **Pontos idő felolvasása** | Hely: Idő és Szervezés > Pontos idő | Permission: – | Web: Nem (de az /status oldalon látszik)
- **Új ébresztő beállítása** | Hely: Idő és Szervezés > Új ébresztő | Működés: diktálás, ismétlés, egyéni hang; `AlarmScheduler` + `AlarmService` (foreground, mediaPlayback) + `AlarmAlertActivity` (zárolt képernyőn, képernyőt bekapcsolja) | Permission: SCHEDULE_EXACT_ALARM, USE_EXACT_ALARM, USE_FULL_SCREEN_INTENT, POST_NOTIFICATIONS | Web: Igen (/alarms)
- **Következő ébresztő / Ébresztők listája / Ébresztő törlése** | Hely: Idő és Szervezés > ... | Web: Igen (lista + törlés: /alarms, /alarms/delete)
- **Ébresztők újraindítás után** | `BootReceiver` (BOOT_COMPLETED, MY_PACKAGE_REPLACED) | Permission: RECEIVE_BOOT_COMPLETED | Web: Nem
- **Mai / Holnapi / Heti program** | Hely: Idő és Szervezés > ... program | Permission: READ_CALENDAR | Web: Igen, csak olvasás (/calendar)
- **Új program beállítása** | Hely: Idő és Szervezés > Új program | Permission: WRITE_CALENDAR | Web: Nem
- **Naptár emlékeztető** | automatikus: `CalendarAlarmReceiver` + `CalendarAlarmService` (specialUse) + `CalendarAlertActivity` | Permission: READ_CALENDAR, SCHEDULE_EXACT_ALARM | Web: Nem
- **Jegyzetek (lista / új / törlés)** | Hely: Idő és Szervezés > ... jegyzet | Permission: – | Web: Igen (/notes, /notes/add — törlés weben nincs)
- **Időzítők (mentés, lista, indítás, leállítás, módosítás, törlés)** | Hely: Idő és Szervezés > Időzítő... | Működés: `TimerService` (foreground, specialUse) — háttérben mondja az eltelt/hátralévő időt | Permission: FOREGROUND_SERVICE, POST_NOTIFICATIONS | Web: Nem

### 3.7 Patika Őrangyal (gyógyszer emlékeztető)

- **Aktuális emlékeztetők felolvasása** | Hely: Eszközök > Mindennapi > Patika Őrangyal > Aktuális emlékeztetők | Permission: – | Web: Igen (/medication)
- **Új gyógyszer rögzítése** | Hely: ...Patika Őrangyal > Új gyógyszer rögzítése | Működés: név diktálása, napszakok (Reggel 8:00 / Dél 12:00 / Este 18:00 / Lefekvés 22:00, több is), ismétlés (Naponta/Hetente/Egyéni napok), opcionális kúra-vég dátum | Permission: RECORD_AUDIO, SCHEDULE_EXACT_ALARM | Web: **Igen (/medication/add) — gépelve, ez a webes oldal fő indoka**
- **Gyógyszerkereső** | Hely: ...Patika Őrangyal > Gyógyszerkereső | Működés: `MedicationSearchHelper` — tájékoztató lekérése névből | Permission: INTERNET | Web: Nem
- **Emlékeztető törlése** | Hely: ...Patika Őrangyal > Emlékeztető törlése | Web: Igen (/medication/delete-confirm → /medication/delete), tömegesen is
- **Be/ki kapcsolás** | csak weben | Web: Igen (/medication/toggle)
- **Riasztás** | automatikus: `MedicationAlarmReceiver` → `MedicationAlertService` (foreground, specialUse) → `MedicationAlertActivity` (zárolt képernyőn, képernyőt bekapcsolja); bevétel megerősítése naplózódik (`logIngestion`), szundi 1 óra | Permission: SCHEDULE_EXACT_ALARM, USE_FULL_SCREEN_INTENT, WAKE_LOCK | Web: Nem
- **Gyógyszerdoboz olvasó** | Hely: Eszközök > Olvasók > Gyógyszerdoboz olvasó | Működés: kamera + OCR (ML Kit) | Permission: CAMERA | Web: Nem

Korlátok a kódból: legfeljebb **48 emlékeztető** (`MAX_REMINDERS`), **500 bevételi
naplóbejegyzés** (`MAX_HISTORY`). Szerkesztés nincs (a Store-ban sincs update).

### 3.8 Zene és Média

- **Zene a telefonon** | Hely: Zene és Média > Zene | Működés: `MusicPlayerActivity`, EQ, lejátszási módok, tekerés | Permission: READ_MEDIA_AUDIO | Web: Nem
- **Zene beállítások (lejátszási mód / tekerés egység / hangszínprofil)** | Hely: Zene és Média > Zene beállítások | Web: Nem
- **Podcast (népszerű, keresés, feliratkozásaim, letöltéseim, ország, OPML import/export)** | Hely: Zene és Média > Podcast | Működés: `PodcastPlayerActivity` | Permission: INTERNET | Web: Igen, részben (/podcast, /podcast/add)
- **YouTube hangos keresés** | Hely: Zene és Média > YouTube | Működés: `YoutubePlayerActivity` | Permission: INTERNET | Web: Nem
- **Profi Diktafon (felvétel, minőség, könyvtár)** | Hely: Eszközök > Mindennapi > Profi Diktafon | Működés: `DictaphoneService` (foreground, microphone), MP3 kódolás (tandroidlame) | Permission: RECORD_AUDIO, FOREGROUND_SERVICE_MICROPHONE | Web: Nem
- **Csengőhang választása** | Hely: Beállítások > Hangok > Csengőhang választása | Működés: `RingtonePickerActivity` | Permission: READ_MEDIA_AUDIO | Web: Nem

### 3.9 Kamerás felismerők és olvasók

- **QR kód olvasó** | Hely: Eszközök > Olvasók > QR kód olvasó | Működés: `QrScanActivity`, ML Kit barcode | Permission: CAMERA | Web: Nem
- **Gyógyszerdoboz / Címke / Szöveg olvasó / Folyamatos szövegolvasó** | Hely: Eszközök > Olvasók > ... | Működés: `TextReaderActivity`, ML Kit text-recognition | Permission: CAMERA | Web: Nem
- **Fénydetektor** | Hely: Eszközök > Felismerők > Fénydetektor | Működés: `LightDetectorActivity` — a fényerőt **hangmagassággal** jelzi | Permission: CAMERA | Web: Nem
- **Színfelismerő** | Hely: Eszközök > Felismerők > Színfelismerő | Működés: `ColorDetectorActivity` | Permission: CAMERA | Web: Nem
- **Mi van előttem? / Környezeti Kitekintő** | Hely: Közlekedés > Mi van előttem?, illetve Eszközök > Felismerők | Működés: `EnvironmentScannerActivity` + `SpatialDescriber` (térbeli leírás) + `AnnouncementDebouncer` (ne ismételje magát) | Permission: CAMERA | Web: Nem
- **Super DL Pénzfelismerő** | Hely: Eszközök > Felismerők > Pénzfelismerő | Működés: offline forint bankjegy-felismerés TensorFlow Lite-tal; `BanknoteFrameGate` (képkocka-szűrés), `BanknoteColorVerifier` (szín-ellenőrzés); **az egyetlen ViewModel-t használó funkció** | Permission: CAMERA | Web: Nem
- **Kártya rendszerező (hozzáadás, felismerés, lista, törlés)** | Hely: Eszközök > Felismerők > Kártya rendszerező | Működés: `CardTrainerActivity` / `CardRecognizerActivity` — kártya eleje+hátulja tanítható | Permission: CAMERA | Web: Nem
- **Kamera és szelfi / Kamera minőség** | Hely: Eszközök > Kamera | Működés: `FaceCameraActivity`, ML Kit face-detection (arc a képen) | Permission: CAMERA | Web: Nem
- **Helyszín felismerő (tanítás, figyelő, mentett helyszínek, leállítás)** | Hely: Közlekedés > Helyszín felismerő | Működés: `LocationTrainerActivity`, `LocationWatchActivity`, `LocationProfilePhotosActivity` — fotóprofil alapján ismer fel helyszínt | Permission: CAMERA | Web: Nem

### 3.10 Közlekedés és GPS

- **Hol vagyok?** | Hely: Közlekedés > Hol vagyok? | Permission: ACCESS_FINE_LOCATION | Web: Nem
- **Gyalogos útvonal / Cím vagy hely keresése** | Hely: Közlekedés > ... | Permission: ACCESS_FINE_LOCATION, INTERNET | Web: Nem
- **GPS Kitekintő (közeli helyek)** | Hely: Közlekedés > GPS Kitekintő > Közeli helyek | Működés: `GpsRadarService` (foreground, specialUse: gps_radar), OpenStreetMap/Overpass | Permission: ACCESS_FINE_LOCATION, INTERNET | Web: Nem
- **Hang-iránytű** | Hely: Közlekedés > GPS Kitekintő > Hang-iránytű | Működés: `CompassScanService` (specialUse: compass_scan) — forgatásra élő térbeli tájékozódás | Permission: ACCESS_FINE_LOCATION | Web: Nem
- **Egyéni helyek (mentett POI-k)** | Hely: Közlekedés > GPS Kitekintő > Egyéni helyek | Működés: `SavedPoiStore` | Web: Igen (/places, /places/delete)
- **GPS Környezeti figyelő** | `GpsSurroundingsService` (foreground, location) — Voice Vista / Soundscape-szerű utcabemondás | Permission: ACCESS_FINE_LOCATION | Web: Nem
- **GPS útvonal (rögzítés, leállítás, mentett útvonalak, útmutatás, törlés)** | Hely: Közlekedés > GPS útvonal | Működés: `GpsRouteRecorderService` + `GpsRouteGuideService` (specialUse), `RouteEventDetector` (kanyar-felismerés) | Permission: ACCESS_FINE_LOCATION | Web: Nem
- **Közeli megállók / Megálló keresése / Kedvenc megállók / Útvonal tömegközlekedéssel** | Hely: Közlekedés > ... | Működés: `transit` csomag, OSM-alapú | Permission: ACCESS_FINE_LOCATION, INTERNET | Web: Nem
- **Vonat (közeli állomások, állomás keresése, kedvenc állomások)** | Hely: Közlekedés > Vonat | Permission: ACCESS_FINE_LOCATION, INTERNET | Web: Nem

### 3.11 Információ

- **Napi üdvözlés** | Hely: Információ > Napi üdvözlés | Működés: dátum, névnap, időjárás | Web: Nem
- **Napi összefoglaló** | Hely: Információ > Napi összefoglaló | Működés: `DaySummaryHelper` — naptár, üzenetek, **következő gyógyszer**, időjárás | Permission: READ_CALENDAR, READ_SMS | Web: Nem
- **Időjárás most / város szerint** | Hely: Információ > Időjárás | Permission: INTERNET, ACCESS_COARSE_LOCATION | Web: Nem
- **Hírek felolvasása / Hírforrások kezelése / OPML import** | Hely: Információ > Hírek | Működés: RSS | Permission: INTERNET | Web: Nem
- **Internet kereső** | Hely: Információ > Internet kereső | Működés: találatok felolvasva | Permission: INTERNET | Web: Nem
- **Akkumulátor állapot** | Hely: Információ > Akkumulátor állapot | Web: Igen (/status)
- **Gyors helyzetjelentés** | `STATUS_REPORT` — offline: idő, akku, térerő, hívások, üzenetek, ébresztő, naptár | Web: Igen (/status)

### 3.12 Játékok

Mind teljesen hangalapú, `games` csomag (19 fájl):

- **UNO kártyajáték** | `UnoActivity` | Web: Nem
- **Blackjack** | `BlackjackActivity` | Web: Nem
- **Póker (ötlapos húzás)** | `PokerActivity` | Web: Nem
- **Félkarú rabló** | `SlotActivity` | Web: Nem
- **Mille Bornes** | `MilleBornesActivity` | Web: Nem

### 3.13 Könyvek

- **Könyvtár / Könyv keresése / Nem rég olvasott / Könyvjelzők / Könyvjelző törlése / Olvasás folytatása / Könyvmappa beállítása-felolvasása-törlése** | Hely: Könyvek > ... | Működés: `BookReader`, PDF-támogatás (PdfBox-Android) | Permission: READ_EXTERNAL_STORAGE (max SDK 32) | Web: Nem

### 3.14 Asszisztens (Elena)

- **Elena** | Hely: Asszisztens > Elena | Működés: helyi hangparancsok, `ElenaKnowledgeBase` (saját tudásbázis az appról) | Permission: RECORD_AUDIO | Web: Nem
- **Elena figyelő (be/ki)** | Hely: Asszisztens > Elena figyelő | Működés: `ElenaWakeListenService` (foreground, microphone) — felébresztő mondatra figyel háttérben | Permission: RECORD_AUDIO, FOREGROUND_SERVICE_MICROPHONE | Web: Nem
- **Elena felébresztő tanítása / Saját felébresztő mondatok** | Hely: Asszisztens > ... | Web: Nem
- **Rendszer-asszisztensként** | `SuperVoiceInteractionService` (BIND_VOICE_INTERACTION) + `SuperVoiceInteractionSessionService` + `SuperRecognitionService` (BIND_SPEECH_RECOGNITION_SERVICE) — a SuperDL beállítható a telefon alapértelmezett asszisztensének | Web: Nem
- **Alapértelmezett asszisztens beállítása / állapota** | Hely: Asszisztens > ... | Web: Nem
- **Bluetooth gomb asszisztens** | Hely: Asszisztens > Bluetooth gomb | Működés: a headset gombja indítja | Permission: BLUETOOTH_CONNECT | Web: Nem

### 3.15 S.O.S.

- **S.O.S. Vészjelzés** | Hely: főmenü > S.O.S. Vészjelzés (azonnali) | Működés: `SosService` (foreground, phoneCall) — akár 4 szám hívása sorban | Permission: CALL_PHONE, SEND_SMS, ACCESS_FINE_LOCATION | Web: Nem
- **S.O.S. számok 1-4 beállítása / felolvasása** | Hely: Beállítások > S.O.S. paraméterek | Web: Nem
- **S.O.S. beállítás ADB-ből** | `SosConfigReceiver` — **saját signature-szintű jogosultsággal védve** (`com.superdl.launcher.permission.SET_SOS`) | Web: Nem

### 3.16 Beállítások, testreszabás

- **Teljes őrség ki-be** | Hely: Beállítások > Teljes őrség | Működés: `BatteryPatrolService` (specialUse: battery_monitoring) | Web: Nem
- **Őrség beállítások**: akkumulátor figyelés, hívás értesítés, üzenet értesítés, egyéb értesítés, idő bemondás + gyakorisága, **éjszakai csend** (kezdet/vég), bekapcsoló gomb idő bemondás | Hely: Beállítások > Őrség beállítások | Web: Nem
- **Biztonság**: PIN zárolás ki-be, PIN beállítása, állapot (`LockScreenActivity`); **Rendszer PIN segéd** (`KeyguardPinAccessibilityService`, BIND_ACCESSIBILITY_SERVICE — a rendszer zárolási PIN akadálymentes bevitele); hívás szűrő mód/állapot; alapértelmezett telefon app | Web: Nem
- **Hangok**: Söpörj hangtéma, csengőhang, csengőhang hangerő, néma mód, és **kategóriánként külön riasztóhang**: program emlékeztető, gyógyszer emlékeztető, ébresztő, SMS, e-mail, egyéb értesítés | Hely: Beállítások > Hangok | Web: Nem
- **Hangerő növelése / csökkentése** | Hely: Beállítások | Permission: MODIFY_AUDIO_SETTINGS | Web: Nem
- **Beszéd gyorsítása / lassítása / TTS hang választása / aktuális TTS hang** | Hely: Beállítások | Működés: `tts` csomag (7 fájl), motor- és hangkatalógus | Web: Nem
- **Értesítések olvasása** | Hely: Beállítások > Értesítések olvasása | Működés: `SuperNotificationListener` (BIND_NOTIFICATION_LISTENER_SERVICE) | Web: Nem
- **WiFi / Bluetooth be-kikapcsolás** | Hely: Beállítások | Permission: CHANGE_WIFI_STATE, BLUETOOTH_CONNECT | Web: Nem
- **Hotspot kapcsoló** | `HOTSPOT_TOGGLE` — a `libs/framework*.jar` + hiddenapibypass ehhez kell | Web: Nem
- **Kilépés a launcherből** | Hely: Beállítások > Kezdőképernyő váltás > Kilépés | Web: Nem
- **Minden alkalmazás / Kedvenc alkalmazások (indítás, hozzáadás, törlés)** | Hely: főmenü | Permission: QUERY_ALL_PACKAGES | Web: Nem

### 3.17 Egyéb eszközök

- **Zseblámpa** | Hely: Eszközök > Zseblámpa | Permission: CAMERA, FLASHLIGHT | Web: Nem
- **Hallás erősítő** | Hely: Eszközök > Mindennapi > Hallás erősítő | Működés: `HearingAidService` (foreground, microphone) — mikrofon → fülhallgató valós időben, mikrofonforrás választható | Permission: RECORD_AUDIO, FOREGROUND_SERVICE_MICROPHONE | Web: Nem
- **Számológép** | Hely: Eszközök > Mindennapi > Számológép | Működés: diktálható, `CalculatorHelper` (shunting-yard algoritmus) | Web: Nem
- **Bevásárlólista** | Hely: Eszközök > Mindennapi > Bevásárlólista | Web: Nem

### 3.18 Névjegy és jogi információk

- **Program hangjainak megismerése** | Hely: Névjegy > Program hangjainak megismerése | Működés: minden rendszerhang bemutatása | Web: Nem
- **Tanuló mód** | Hely: Névjegy > Tanuló mód | Működés: funkciók bemutatása kockázat nélkül | Web: Nem
- **Az alkalmazásról / Fejlesztő / Kapcsolat e-mailben / Adatvédelmi tájékoztató / Felhasználási feltételek / Jogi nyilatkozat** | Hely: Névjegy > ... | Web: Nem

### 3.19 Akadálymentesítési megoldások

Ez nem egy funkció, hanem az egész app működési elve.

- **Teljes TTS-vezérlés**: minden művelet felolvasásra kerül. `tts` csomag:
  `TtsManager`, `TtsEngineHelper`, `TtsVoiceCatalog` — motor és hang szabadon
  választható, sebesség állítható.
- **Négyirányú gesztusvezérlés**: `gestures/SwipeGestureListener` — fel =
  előző/ismétlés, le = következő, jobbra = belépés/megerősítés, balra =
  vissza/megszakítás (a diktálás is leáll).
- **Hangvisszajelzés-rendszer** (`feedback`, 20 fájl): `SoundFeedback`,
  `SoundTheme` + `SoundThemeStore` (választható hangtémák), `GestureSoundHelper`,
  `AlertSoundPlayer` + `AlertSoundCategory` (kategóriánként külön hang),
  `DeviceStateSoundService` (képernyő be/ki, teljes töltés hangjelzés),
  `DevicePowerReceiver` (töltő csatlakozás/leválasztás), `ToggleAnnouncement`.
- **Haptika**: `VIBRATE` jogosultság, rezgés-visszajelzés.
- **Beszédfelismerés-javítás**: `voice/SpeechCorrections.kt` — a félrehallott
  szavak javítása (a gyógyszernevek miatt is), `VoiceAssistantHelper.normalize()`
  ékezet- és kisbetű-független egyeztetéshez.
- **PIN-bevitel akadálymentesen**: `input/NumberPadHelper`, `PinPadMode`,
  továbbá a `KeyguardPinAccessibilityService` a **rendszer** zárolási PIN-jéhez.
- **Zárolt képernyőn is működő riasztások**: `showWhenLocked` + `turnScreenOn`
  az ébresztő, gyógyszer, naptár és hívás Activity-knél.
- **Vágólap-beillesztés**: a telefonos bevitelnél fel-söprésre, a portálon
  gombbal — a 16 karakteres app-jelszavakat diktálni gyakorlatilag lehetetlen.
- **WiFi portál mint akadálymentesítés**: nem képernyőtükrözés, hanem tiszta
  szemantikus HTML (címkék, `aria-live`, `role="status"`/`role="alert"`,
  fieldset/legend, "Ugrás a tartalomra" link) — a gép billentyűzetéről és
  képernyőolvasójáról használható.
- **Tanuló mód** és **hangok megismerése**: veszélytelen gyakorlás.

---

## 4. WiFi Server Portál API

**Szerver:** `files/WifiPortalServer.kt` (nyers `ServerSocket`, saját HTTP-kezelés),
`files/WifiPortalService.kt` (foreground service, dataSync típus).
**Oldalak:** `files/PortalControlPages.kt`.

### Hitelesítés

Minden útvonal PIN-védett, kivéve a `/login`-t. A PIN **négyjegyű, minden
indításkor újragenerált véletlen szám** (`(1000..9999).random()`), amit a telefon
számjegyenként bemond. Ellenőrzés: `superdl_pin=<PIN>` cookie, **vagy** a
query-ben `pin=<PIN>` (első belépéskor). Ha nincs érvényes PIN → belépő oldal.

Ez nem HTTPS és nem session-kezelés — helyi WiFi-re szánt, egyszerű védelem.

### Endpointok

**Fájlok**

- `GET /` – főoldal, fájllista és feltöltő űrlap. Válasz: HTML.
- `GET /?pin=1234` – belépés PIN-nel a query-ből.
- `GET /login...` – belépő oldal kezelése.
- `GET /download/<fájlnév>` – fájl letöltése. Válasz: a fájl bináris tartalma.
- `POST /upload` – fájl feltöltése (multipart). A cél mappa választható:
  általános, **csengőhangok, értesítési hangok, ébresztő hangok** — az utóbbi
  háromnál `markAudioKind()` bejelenti a MediaStore-nak, hogy a rendszer
  hangválasztói is lássák. Válasz: HTML a főoldalra.

**SMS**

- `GET /sms` – legutóbbi 30 üzenet, névfeloldással + küldő űrlap.
- `POST /sms/send` – üzenet küldése. Mezők: `phone`, `body`.
- `POST /sms/delete` – üzenet törlése. Mező: `id`. Megerősítés **nincs**.
- `POST /sms/reply` – válasz-űrlap megnyitása. Mező: `phone`.

**Névjegyek**

- `GET /contacts` – legfeljebb 300 névjegy, névjegyenkénti küldés/törlés + tömeges törlő űrlap.
- `POST /contacts/add` – új névjegy. Mezők: `name`, `phone`.
- `POST /contacts/share` – névjegy küldése SMS-ben. Mezők: `name`, `phone`, `to`.
- `POST /contacts/delete-confirm` – **megerősítő oldal**. Mező: `id` (többször is!). Válasz: a törlendők név szerinti felsorolása + "Igen, töröljem" gomb.
- `POST /contacts/delete` – tényleges törlés. Mező: `id` (többször is). Válasz: "7 névjegy törölve." / "1 névjegyet nem sikerült törölni."

Példa (tömeges törlés megerősítése):
```
POST /contacts/delete-confirm
Cookie: superdl_pin=3729
Content-Type: application/x-www-form-urlencoded

id=12&id=15&id=31
```
Válasz: HTML, benne a három név felsorolva, `role="alert"` figyelmeztetéssel.

**Patika Őrangyal**

- `GET /medication` – emlékeztetők listája + új felvétele űrlap. Ha a pontos ébresztő engedély hiányzik, figyelmeztetés a lap tetején.
- `POST /medication/add` – új emlékeztető. Mezők: `name` (kötelező), `tod` (napszak, többször is: MORNING/NOON/EVENING/BEDTIME), `time` (egyéni időpont, HH:MM), `cycle` (DAILY/WEEKLY/CUSTOM), `weekday` (naptári napszám, többször is), `courseEnd` (ÉÉÉÉ-HH-NN). A napszakok és az egyéni időpont **összeadódnak**.
- `POST /medication/toggle` – be/ki. Mezők: `id`, `enabled` (true/false).
- `POST /medication/delete-confirm` – megerősítő oldal. Mező: `id` (többször is).
- `POST /medication/delete` – tényleges törlés. Mező: `id` (többször is).

Példa (új gyógyszer, reggel és este, naponta, 7 napos kúra):
```
POST /medication/add
Content-Type: application/x-www-form-urlencoded

name=Dedaxin&tod=MORNING&tod=EVENING&cycle=DAILY&courseEnd=2026-07-24
```
Válasz: "Emlékeztető létrehozva: Dedaxin, 08:00, 18:00."

**Jegyzetek**

- `GET /notes` – jegyzetek listája + új jegyzet űrlap.
- `POST /notes/add` – új jegyzet. Mezők: `title`, `body`. (Törlés weben nincs.)

**Ébresztők**

- `GET /alarms` – ébresztők listája + új űrlap.
- `POST /alarms/add` – új ébresztő. Mezők: `time` (HH:MM), `label`, `repeat` (ONCE/DAILY/WEEKDAYS/WEEKEND).
- `POST /alarms/delete` – törlés. Mező: `id`. Megerősítés **nincs**.

**Naptár**

- `GET /calendar` – mai és holnapi program. Csak olvasás.

**Emlékhelyek (mentett POI-k)**

- `GET /places` – mentett helyek listája.
- `POST /places/delete` – törlés. Mező: `id`. Megerősítés **nincs**.

**Podcast**

- `GET /podcast` – podcast oldal.
- `POST /podcast/add` – feliratkozás hozzáadása.

**Állapot**

- `GET /status` – akkumulátor, szabad tárhely, Android verzió, eszköz.

**Egyéb**

- Bármi más → `404 Not Found`, de a főoldal HTML-jével válaszol.

### Fontos technikai részlet

`parseForm()` a `.toMap()` miatt azonos kulcsnál **csak az utolsót** tartja meg.
A checkboxos tömeges műveletekhez ezért van külön `parseFormMulti()`, ami
kulcsonként listát ad vissza. Aki új tömeges funkciót ír, ezt használja.

---

## 5. Függőségek

Az `app/build.gradle`-ból, mindegyikhez a valódi felhasználással.

**AndroidX / alap**

- `androidx.security:security-crypto:1.1.0-alpha06` – **titkosított tárolás** érzékeny adatnak (e-mail jelszó); a kulcsot a hardveres Keystore védi
- `androidx.core:core-ktx:1.12.0` – Kotlin kiterjesztések
- `androidx.appcompat:appcompat:1.6.1` – visszafelé kompatibilitás
- `com.google.android.material:material:1.11.0` – Material komponensek
- `androidx.constraintlayout:constraintlayout:2.1.4` – XML elrendezés
- `org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3` – aszinkron futtatás

**Compose** (BOM 2024.02.00)

- `androidx.compose.ui:ui`, `ui-tooling-preview`, `material3` – Compose felület
- `androidx.activity:activity-compose:1.8.2`
- `androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0`
- `androidx.lifecycle:lifecycle-runtime-compose:2.7.0`

**Kamera** (CameraX 1.3.1)

- `androidx.camera:camera-core`, `camera-camera2`, `camera-lifecycle`,
  `camera-view`, `camera-video` – az összes kamerás funkció alapja (pénzfelismerő,
  OCR, QR, fény, szín, arc, kártya, helyszín)

**ML Kit**

- `com.google.mlkit:barcode-scanning:17.2.0` – QR-kód olvasó
- `com.google.mlkit:face-detection:16.1.7` – arc kamera
- `com.google.mlkit:text-recognition:16.0.1` – OCR (gyógyszerdoboz, címke, szöveg)

**TensorFlow Lite**

- `org.tensorflow:tensorflow-lite:2.14.0` – **pénzfelismerő** és környezeti kitekintő modellek
- `org.tensorflow:tensorflow-lite-support:0.4.4` – kép-előfeldolgozás

**Egyéb**

- `com.tom-roush:pdfbox-android:2.0.27.0` – PDF-olvasás (könyvek)
- `com.github.naman14:tandroidlame:1.1` – **MP3 kódolás** a diktafonhoz (a régi support-lib függőségei kizárva)
- `org.lsposed.hiddenapibypass:hiddenapibypass:4.3` – rejtett Android API-k elérése (hotspot kapcsoló)

**Helyi jar-ok** (`app/libs/`)

- `framework.jar`, `framework-wifi.jar`, `framework-connectivity.jar`,
  `framework-tethering.jar` – rendszer-API-k fordítási időben (hotspot vezérlés)

**Amit NEM használ, pedig gondolnád**

- **Nincs JavaMail / Jakarta Mail** – az SMTP küldés (`SmtpSender.kt`) és az IMAP
  olvasás (`ImapReader.kt`) **nyers `Socket`/`SSLSocket` alapú saját kód**
- Nincs Retrofit/OkHttp – `HttpURLConnection`
- Nincs Room – SharedPreferences + JSON (44 Store)
- Nincs Hilt/Koin/Dagger – nincs DI
- Nincs Glide/Coil – nincs képbetöltő könyvtár

**ProGuard/R8**: a `-dontwarn` szabályok a PDFBox JPEG2000, BouncyCastle LDAP és
Tink KeysDownloader opcionális osztályaira vonatkoznak (release buildhez kellenek).

---

## 6. TODO / Hiányosságok / Ötletek

### A kódban lévő TODO/FIXME kommentek

**Nulla darab.** Rákerestem a TODO, FIXME, HACK, XXX mintákra az összes .kt
fájlban: **egyetlen valódi találat sincs**. (Ami előjött, az mind `toDouble()`
hívás volt, kis/nagybetű-érzéketlen keresés miatt.) A kód kommentjei magyarul,
általában a MIÉRT-tel kezdve magyaráznak — nem hátralévő munkát jelölnek.

Ez azt jelenti, hogy a hátralévő munka **nem a kódban**, hanem a
`dokumentumok/fejlesztesi-naplo.txt` 9. szakaszában van nyilvántartva.

### Ismert hiányosságok (a naplóból és a kód átnézéséből)

- **`huf_banknote_detector.tflite` HIÁNYZIK az assets-ből.** A YOLO tréning
  lefutott (`tools/runs/banknote/huf_detect-2/best.pt` létezik), de a TFLite
  export nincs bemásolva. Emiatt a kétlépcsős pénzfelismerő pipeline **ki van
  kapcsolva**, csak a ROI + teljes képkockás tartalék fut. Ez a legnagyobb
  nyitott tétel.
- **Portál: névjegy-szerkesztés nincs.** Ez a négy mérföldkőből az egyetlen, ami
  el sem kezdődött. (Törlés, hozzáadás, küldés van.)
- **Portál: jegyzet-törlés nincs** (csak lista és hozzáadás).
- **Gyógyszer-emlékeztető szerkesztés nincs** – a `MedicationStore`-ban nincs
  `update`, csak add/delete/setEnabled. Módosítás = törlés + újrafelvétel.
- **Az SMS-, ébresztő- és hely-törlés a portálon megerősítés nélkül fut**
  egyetlen kattintásra. A névjegy és a gyógyszer törlésénél már van megerősítő
  oldal — a többinél nincs. Ez tudatos aszimmetria (egy SMS kisebb tét), de
  érdemes tudni róla.
- **`MainActivity.kt` 12 443 sor** – hosszú távon kezelhetetlen (lásd 7. fejezet).
- **A portál nem HTTPS**, a PIN a query-ben is utazhat. Helyi WiFi-re tervezve.
- **Elavult dokumentáció**: `elena_tudas_superdl.txt` verziószáma 1.10.0,
  `README.md`-é 1.36.5, `SuperDL_Project_State.md` 2026-07-03-i — mind régebbi a
  jelenlegi 1.54.9-nél.
- **Nincsenek automatizált tesztek** (nem találtam teszt-forrásmappát).

### Ötletek (a naplóból)

- Saját bankjegyfotók begyűjtése és újratanítás (ez adná a legjobb pontosságot)
- YOLO tanítási pipeline általános tárgyfelismeréshez ("jajdejolo"), első cél:
  ajtó-felismerés
- Windows SuperDL asztali verzió (külön projekt, párhuzamosan fejlődik)

---

## 7. Hogyan tovább – Moduláris terv

Ez javaslat, nem sürgős feladat. A jelenlegi monolit **működik**, és a
mintakövetés jól viszi. A szétbontás akkor éri meg, ha a MainActivity mérete már
akadályozza a munkát.

### A valódi probléma

Nem a 393 fájl a baj — a csomagszerkezet valójában rendben van, funkció szerint
tagolt. A baj **egyetlen fájl: `MainActivity.kt`, 12 443 sor.** Ez tartalmazza a
menü-állapotgépet, az összes flow-t, a TTS-hívásokat, a gesztuskezelést és a
launcher-eredmények feldolgozását. Minden új funkció ide is bekötést igényel —
és pont itt szakadt félbe a névjegy-csengőhang munka is.

### Első lépés: a MainActivity felbontása (a legnagyobb nyereség)

Ne modulokkal kezdd, hanem ezzel. A flow-k már most külön `AppFlow` típusok
(`flow` csomag) — ez a fogódzó:

1. **Flow-kezelők kiemelése**: minden funkcióterület flow-logikája a saját
   csomagjába, egy-egy `XxxFlowHandler` osztályba (pl.
   `medication/MedicationFlowHandler.kt`). A MainActivity csak delegál.
2. **A `when (action)` blokkok kiváltása**: a menü-akciók kezelése kerüljön a
   handlerekbe, hogy egy új funkció bekötése egy helyen történjen.
3. **A launcher-eredmények (ActivityResult) csoportosítása** funkció szerint.

Ez önmagában a MainActivity-t nagyságrendekkel csökkentené, **modulok nélkül**,
és megszüntetné a "bekötés kimaradt" hibatípust.

### Második lépés: modulhatárok (ha az első után is indokolt)

A csomagok már most is jó határvonalakat rajzolnak. Reális modulbontás:

- `:core:tts` – `tts` + `feedback` (beszéd és hangvisszajelzés)
- `:core:storage` – `storage/JsonPrefsHelper` + a Store-ok közös alapja
- `:core:voice` – `voice` + `input` (beszédfelismerés, bevitel)
- `:core:ui` – gesztusok, közös témák
- `:feature:communication` – `call`, `sms`, `contacts`, `email`, `callfilter`
- `:feature:vision` – `currency`, `environment`, `textreader`, `color`, `light`,
  `cardorganizer`, `camera`, `locationwatch` (mind CameraX + ML Kit/TFLite)
- `:feature:navigation` – `gps`, `route`, `transit`, `train`
- `:feature:health` – `medication`
- `:feature:media` – `music`, `podcast`, `youtube`, `dictaphone`, `book`
- `:feature:organizer` – `alarm`, `calendar`, `timer`, `notes`, `shopping`
- `:feature:games` – `games`
- `:feature:portal` – `files` (a WiFi portál)

### Mit nyernél, és mit veszítenél

**Nyerne**: gyorsabb inkrementális build (a `:feature:vision` ML-függőségei nem
fordulnak újra, ha az SMS-hez nyúlsz), tisztább határok, könnyebb tesztelhetőség.

**Veszítene**: a modulosítás Gradle-konfigurációval és rengeteg
`api`/`implementation` döntéssel jár, és a jelenlegi "keress egy mintát, kövesd"
munkamódszert megnehezíti, amíg be nem áll. Egyszemélyes projektnél ez valós ár.

### Amit előbb csinálnék, mint a modulosítást

1. A MainActivity felbontása flow-handlerekre (fent).
2. **Tesztek a kockázatos helyekre**: a `MedicationScheduler` sorrend-függősége
   (cancel → delete), a `parseFormMulti`, a telefonszám-normalizálás. Ezek
   olyanok, ahol a hiba csendes és a következménye komoly (kimaradt gyógyszer,
   törölt névjegyek).
3. A `huf_banknote_detector.tflite` bemásolása — ez felhasználói értéket ad,
   nem architektúrát.

Az architektúra átszabása ne előzze meg azt, ami a felhasználónak számít.

---

## TL;DR (10 sor)

1. A projekt neve a kódban végig **SuperDL**, `com.superdl.launcher` — "Verrza" néven **nulla találat** van, ilyen nevű dolog nem létezik a repóban.
2. Magyar nyelvű Android **launcher vak felhasználóknak**: minden gesztussal és hanggal vezérelhető, minden megszólal.
3. Kotlin, 393 fájl, 65 csomag, minSdk 26 — **feature-alapú monolit**, nem Clean Architecture: nincs DI, nincs Room, 1 db ViewModel.
4. **`MainActivity.kt` = 12 443 sor** — ez a projekt legnagyobb technikai adóssága; minden funkció ide is bekötést igényel.
5. Adatréteg: **44 db `*Store.kt`**, mind SharedPreferences + JSON, séma-verziózással.
6. **32 Activity, 24 Service, 10 Receiver** — köztük saját InCall, SMS-app, asszisztens, hívásszűrő és akadálymentesítési szolgáltatás.
7. A **WiFi portál** (nyers socket HTTP-szerver, 4 jegyű véletlen PIN) a gépről engedi intézni, amit diktálni nehéz: SMS, névjegyek, jegyzetek, ébresztők, **Patika Őrangyal**.
8. Az e-mail **saját SMTP/IMAP socket-implementáció** — nincs JavaMail. A jelszó hardveres Keystore-ral titkosítva.
9. **Nulla TODO/FIXME komment** a kódban; a hátralévő munka a fejlesztési naplóban van. A legnagyobb hiány: a `huf_banknote_detector.tflite` nincs az assets-ben, ezért a kétlépcsős pénzfelismerő ki van kapcsolva.
10. Következő lépésnek a MainActivity flow-handlerekre bontását javaslom — modulosítás nélkül is ez adná a legtöbbet, és megszüntetné a "bekötés kimaradt" hibatípust.

---

*Ez a dokumentum a kód 2026-07-17-i állapotából készült, kizárólag a tényleges
forrásból (AndroidManifest.xml, build.gradle, MenuTree.kt, és a hivatkozott
osztályok). Ahol valami hiányzik vagy bizonytalan, azt külön jeleztem.*
