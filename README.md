# Super Digital Launcher (Super DL)

Vak és gyengénlátó felhasználók számára készült Android launcher. Gesztusokkal és hanggal vezérelhető: hívás, üzenet, ébresztő, S.O.S., hírek, YouTube, könyvolvasás, tömegközlekedés, diktafon és több.

**Verzió:** 1.36.5 (`versionCode` 58)  
**Fejlesztő:** Kőrösmezey Dávid  
**Kapcsolat:** korosmezey.david.richard@gmail.com

## Tesztelői APK telepítése

Ez a build **belső tesztelésre** készült, nem Play Store kiadás.

### Követelmények

- Android 8.0 (API 26) vagy újabb
- Legalább 100 MB szabad tárhely
- SIM-kártya a telefonos és SMS funkciókhoz (opcionális WiFi-only teszthez)

### Telepítés lépései

1. Töltsd le az APK-t: `app/build/outputs/apk/debug/SuperDL-1.36.5-debug.apk`
2. Ha szükséges, engedélyezd a **Ismeretlen forrásból** telepítést a telefon beállításaiban.
3. Nyisd meg az APK-t, telepítsd, majd indítsd el a Super DL-t.
4. Állítsd be **alapértelmezett kezdőképernyőnek** (launchernek), ha teljes tesztet szeretnél.
5. Az első indításkor fogadd el a kért engedélyeket. Az értesítések olvasásához külön engedély kell a rendszerbeállításokban.

### Mit érdemes külön kipróbálni

| Terület | Mit nézz |
|---------|----------|
| Launcher | Alapértelmezett kezdőképernyő, gesztusok, menünavigáció |
| S.O.S. | Gyors hívásindítás, zárolt képernyőn |
| Patika Őrangyal | Gyógyszer-emlékeztető, zárolt képernyőn |
| Hívásszűrő | Rejtett számok tiltása (Beállítások → Biztonság) |
| GPS Kitekintő | Közeli helyek, mentett POI-k |
| Környezeti Kitekintő | Kamera objektumfelismerés, térhatáron belüli bemondás |
| Helyszín felismerő | Tanítás + figyelés mentett profilokkal, OCR alapú bemondás |
| Pénzfelismerő | Forint bankjegy felismerés, hangerő gomb = azonnali ellenőrzés |
| Profi diktafon | FLAC felvétel, lejátszás, megosztás |
| Hangos asszisztens | Oldalsó gomb hosszú nyomás, vagy menüből |
| YouTube | Hangos keresés és lejátszás |

### Visszajelzés küldése

Írj a fejlesztőnek e-mailben. Hasznos, ha megadod:

- Telefon típusa és Android verzió
- Mit csináltál, mit vártál, mi történt helyette
- Ha lehet, pontos lépések a hiba reprodukálásához

## Android Studio-ban megnyitás

1. File → Open → a `SuperDL` mappa kiválasztása
2. Gradle sync automatikusan lefut
3. Build → Make Project
4. Run → Run 'app' (USB debugginggal csatlakoztatott telefonon)

## APK buildelés

Windows:

```
gradlew.bat assembleDebug
```

Linux/macOS:

```
./gradlew assembleDebug
```

APK helye: `app/build/outputs/apk/debug/app-debug.apk`  
Tesztelői név: `app/build/outputs/apk/debug/SuperDL-1.36.5-debug.apk` (build után másolva)

## Mérföldkövek állapota

- [x] **M1** — Alapváz (gesztusrendszer, TTS, menüstruktúra, S.O.S.)
- [x] **M2** — Telefon és kommunikáció (névjegyek, SMS, e-mail SMTP, hívásnapló)
- [x] **M3** — Idő és szervezés (ébresztő, naptár)
- [x] **M4** — Média (zenelejátszó, YouTube hangos keresés)
- [x] **M5** — Információ (időjárás, hírek, QR olvasó, akkumulátor)
- [x] **M6** — Rendszer (értesítés olvasó, WiFi/BT, akkumulátor őrség)
- [x] **M7** — Közösség (tömegközlekedés BKK, gyalogos útvonal, helykeresés)
- [x] **M8** — Hírek bővítés (18 forrás, kategóriák) + térkép megnyitás helykeresésnél
- [x] **M9** — Napi üdvözlés (dátum, névnap, időjárás, induláskori opció)

### 1.11–1.23: Terven túli, kész funkciók

- **Kommunikáció:** kedvenc hívás/törlés, új névjegy létrehozása, hívás közbeni képernyő, hívásszűrő (rejtett számok)
- **Idő és szervezés:** mentett időzítők (háttérszolgáltatás), naptár-emlékeztetők
- **Eszközök:** profi diktafon (FLAC, könyvtár, megosztás, e-mail), Patika Őrangyal (gyógyszer-emlékeztető), színfelismerő, fénydetektor, zseblámpa, számológép, QR olvasó
- **Közösség:** GPS Kitekintő (közeli POI radar, mentett helyek), Környezeti Kitekintő (offline kamera objektumfelismerés)
- **Biztonság:** PIN zárolás zárolt képernyőn, S.O.S. számok hanggal és ADB-vel
- **Asszisztens:** hangos asszisztens (helyi kulcsszó-felismerés), digitális asszisztens szerepkör, tanuló mód, hangok betanítása
- **Rendszer:** akkumulátor őrség (részletes patrol beállítások), rendszerállapot hangok, külső alkalmazások listája
- **Média:** könyvolvasó (TXT, EPUB, PDF, DOCX) könyvjelzőkkel, egyéni könyvmappa
- **Jogi:** névjegy, adatvédelem, felhasználási feltételek, jogi nyilatkozat

Részletes változások: [CHANGELOG.md](CHANGELOG.md)

## Fő modulok

```
app/src/main/kotlin/com/superdl/launcher/
├── MainActivity.kt          ← fő vezérlő, menü, flow-k
├── menu/MenuTree.kt         ← magyar menüstruktúra
├── flow/AppFlow.kt          ← belső UI állapotok
├── gestures/                ← swipe navigáció
├── tts/                     ← felolvasás, motorválasztás
├── assistant/               ← hangos asszisztens, digitális asszisztens
├── call/, callfilter/, calllog/  ← hívás, szűrő, napló
├── sms/, email/, contacts/  ← kommunikáció
├── alarm/, calendar/, timer/    ← időzítés
├── medication/              ← Patika Őrangyal
├── dictaphone/              ← profi diktafon
├── gps/                     ← GPS Kitekintő
├── environment/             ← Környezeti Kitekintő (TFLite objektumfelismerés)
├── music/, youtube/, book/  ← média
├── news/, weather/, transit/, navigation/
├── qr/, light/, color/, calculator/
├── lock/                    ← PIN zárolás
├── sos/, notifications/, patrol/, battery/
├── favorites/               ← kedvenc hívások
├── training/                ← tanuló mód
└── legal/, settings/, feedback/
```

## Gesztusok (fő képernyő)

| Gesztus | Menüben | Folyamatban |
|---------|---------|-------------|
| Fel | Előző elem | Navigálás / ismétlés |
| Le | Következő elem | Navigálás / következő |
| Jobbra | Megnyitás / megerősítés | Művelet |
| Balra | Vissza / kilépés | Mégse |

Tanuló módban kilépés: **két gyors balra swipe**.

## S.O.S. számok

A Beállítások → S.O.S. paraméterek menüben hanggal állíthatók (S.O.S. szám 1–4), vagy ADB-vel:

```
adb shell am broadcast -a com.superdl.launcher.SET_SOS --es sos_1 "+36201234567" --permission com.superdl.launcher.permission.SET_SOS
```

## Engedélyek

Az alkalmazás induláskor kéri a szükséges engedélyeket (telefon, SMS, hely, mikrofon, naptár, értesítések, média Android 13+-on). Az értesítések olvasásához külön Notification Listener engedély szükséges a rendszerbeállításokban. A hívásszűrőhöz a rendszer „Hívásazonosító és spam” szerepkört kell engedélyezni (ha elérhető).

## Ismert korlátok

- A hangos asszisztens helyi kulcsszó-felismerés (nem felhő AI).
- A menüpontok többsége hangból is elérhető; a pontos kulcsszavakat a „segítség” parancs sorolja fel.
- Az e-mail küldés SMTP-n keresztül működik; a beállítás Gmail-re optimalizált.
- A YouTube lejátszás külső stream-szolgáltatóktól függ.
- A tömegközlekedés elsősorban Budapest (BKK FUTÁR) és OSM fallback.
- A régi `.doc` formátum a könyvolvasóban nem támogatott megbízhatóan.