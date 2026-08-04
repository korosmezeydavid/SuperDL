# Változások

## 1.54.9 (versionCode 100) — 2026-07-06

### Sürgős javítás – Super DL összeomlás induláskor

- **Gyökérok**: `STREAM_ACCESSIBILITY` nem használható hangcsatornaként ezen az Androidon → `IllegalArgumentException` → az app azonnal leállt, a rendszer kezdőalkalmazás-választót dobott fel.
- **Megoldás**: gesztus/swipe hangok most a **STREAM_MUSIC** csatornán szólnak (hallható, rezgés módban sem némített, kompatibilis).

## 1.54.8 (versionCode 99) — 2026-07-06

### Hangok – gyökérok javítás (rezgés mód, némított csatornák)

- **Gyökérok**: a telefon **rezgés módban** volt (`RINGER_MODE_VIBRATE`), a csengő/rendszer/értesítés csatornák **0 hangerőn** – ezért nem szólt semmi.
- **Egyszeri javítás induláskor** – ha nem néma mód, visszaállítja a csengőt normál módra és emeli a némított csatornák hangerőjét.
- **Swipe / hangtéma hangok** – most a **STREAM_ACCESSIBILITY** csatornán szólnak (nem némítja a rezgés mód).
- **Betöltési várólista** – ha a hang még töltődik, a lejátszás nem vész el.
- **Bejövő hívás** – rezgés módban is csörög (ébresztő csatornán, ami nem némított).

## 1.54.7 (versionCode 98) — 2026-07-06

### Hangok – swipe visszaállítás és hangtémák

- **Swipe hangok javítva** – a néma mód már nem némítja a fel/le/jobbra/balra gesztus hangokat.
- **Telefon csengőhang javítva** – a néma mód nem állítja rezgésre a rendszer csengőt; induláskor visszaállítja a korábbi beállítást, ha beragadt.
- **Bejövő hívás** – MediaPlayer hiba esetén Ringtone, majd beépített tartalék csengő; csengő hangerő 0 esetén automatikus emelés.
- **Swipe hangtémák** – Beállítások → Hangok → Swipe hangtéma:
  - Alapértelmezett (sípoló)
  - Kattintás és flick (apró kattintás/lapcsapás hangok)
  - Suhogás (gyors suhogó/csúszó hangok)
- **Elena parancs** – „swipe hangtéma” / „hangtéma” a menü megnyitásához.

## 1.45.4 (versionCode 77) — 2026-06-26

### GPS kitekintő – mentett hely közeledési bemondások

- **Közeledési küszöbök javítva** – a 50 m bemondás után most már szól 20, 10, 5 és 2 méternél is (korábban a ciklus hibásan megállt az első küszöbnél).
- **Gyorsabb helyfrissítés** mentett cél követésekor (2 mp).
- **Induláskor** azonnali távolság-ellenőrzés; közeledési módban nincs 18 mp-es felesleges ismétlő bemondás.

### Elena figyelő – háttérfigyelés és kikapcsolás

- **Csendes figyelés** – nincs sípszó minden ciklusnál, rövidebb, háttérben futó felismerés (mint a Google asszisztens).
- **Nem ragad be** – Elena aktiválásakor azonnal leáll a figyelő; bezáráskor automatikusan folytatja.
- **Kikapcsolás gomb** az értesítésben; menüből vagy hangparancsból azonnal leáll.

### Hotspot – közvetlen bekapcsolás (Ulefone)

- **Várakozás a rendszer visszajelzésére** (`onTetheringStarted`) – nem nyit beállításokat, ha a hotspot tényleg elindult.
- **Hosszabb hardver-ellenőrzés** és megbízhatóbb siker-jelzés olyan készülékeken, ahol az API téves állapotot ad.

## 1.45.3 (versionCode 76) — 2026-06-26

### Hotspot kapcsoló – ki-be villogás javítás

- **Nem indít újra** futó hotspotot – ha már be van kapcsolva, nem hív `startTethering`-et.
- **Kikapcsolás** – először `stopTethering`, ha kell utána `setWifiApEnabled(false)`; nem kapcsol vissza.
- **Provisioning UI kikapcsolva** – nem ugrik fel rendszerpanel kapcsoláskor.
- **1,8 mp debounce** – véletlen dupla swipe nem kapcsol kétszer.

## 1.45.2 (versionCode 75) — 2026-06-26

### Hotspot státusz – Ulefone / Android 13 javítás

- **sysfs ellenőrzés** (`ap0` operstate) – nem bízik a hibás `getWifiApState()` API-ban.
- **Szigorúbb tethering szűrés** – `wlan0` kliens WiFi már nem számít hotspotnak.
- **Kapcsolás után** a tényleges célállapotot jelzi, ha a rendszer API tévesen „bekapcsolva”-t ad.

## 1.45.1 (versionCode 74) — 2026-06-26

### Hotspot státusz javítás

- **Pontosabb hotspot-állapot** – csak a WiFi hotspot állapotát olvassa (`getWifiApState`, rendszerbeállítás), nem keveri USB/Bluetooth tetheringgel.
- **Kapcsolás után** rövid várakozással frissül a bemondott állapot.

## 1.45.0 (versionCode 73) — 2026-06-26

### Elena tudásbázis – SUPERDL.TXT import

- **SUPERDL.TXT beépítve** az appba (`assets/elena_tudas_superdl.txt`) – teljes képességjegyzék.
- **Szekció-kereső** – a dokumentum fejezeteiből automatikus, rövidített válasz (pl. telefon, könyvek, hírek, engedélyek).
- **35+ rögzített tudásbejegyzés** – S O S visszaszámlálás, SMS lépések, SMTP, hírforrások, könyvformátumok, korlátok, stb.
- **Bővített témalista** – „tudásbázis” parancsra több témakör felolvasása.

## 1.44.0 (versionCode 72) — 2026-06-26

### Elena tudásbázis + Hotspot kapcsoló

- **Helyi tudásbázis** – Elena internet nélkül is válaszol gyakori kérdésekre (Super DL, gesztusok, S O S, PIN, telefon, navigáció, kamera eszközök, hibaelhárítás).
- **Tudásbázis parancsok:** „mi az a Super DL”, „hogyan működnek a gesztusok”, „ki vagy”, „nincs internet”, stb.
- **Hotspot be- és kikapcsolás** – Beállítások menüben új kapcsoló; hangparancs: „hotspot”.
- Ha a hotspot közvetlen kapcsolás nem engedélyezett, megnyitja a rendszer hotspot beállításait.

## 1.43.0 (versionCode 71) — 2026-06-26

### Elena – személyesebb hangos asszisztens

- **Átnevezés:** a hangos asszisztens neve mostantól **Elena** (menü, TTS, rendszer-asszisztens címke).
- **Felébresztő mondatok:** „Szia Elena”, „Kérlek Elena” és további beépített variánsok; parancs egy mondatban is (pl. „Szia Elena, hány óra van?”).
- **Saját felébresztő tanítás:** a felhasználó diktálással menthet egyéni felébresztő mondatot (Asszisztens → Elena felébresztő tanítása).
- **Elena figyelő:** opcionális háttér-figyelés előtérben (értesítéssel); felébresztőre automatikusan indul Elena.
- **Bővített kulcsszavak:** több természetes parancs (dátum, névjegy szinkron, YouTube, gyalogos útvonal, SMS/telefon beállítás, TTS hang, stb.).
- **ASR javítások:** gyakori „Elena” tévesztések (Helena, Ilona) automatikus korrekciója.

## 1.42.0 (versionCode 70) — 2026-06-25

### Pénzfelismerő – valódi bankjegy fotókkal tanítva

- **62 Wikimedia Commons referencia fotó** letöltve és betanítva (minden címlet, több évjárat).
- **Szigorúbb felismerés** – magasabb bizalmi küszöb, 3 egyező képkocka kell a bemondáshoz (kevesebb téves találat).
- Letöltő script: `tools/download_banknote_dataset.py`

## 1.41.0 (versionCode 69) — 2026-06-25

### Pénzfelismerő és kamera

- **Modell újratanítás** – fejlesztett szintetikus tanítás + valódi fotók támogatása (`tools/banknote_dataset/`).
- **Munkajelző kattintás** – halk click hang jelzi, hogy a pénzfelismerő aktívan dolgozik.
- **Kamera app** – jobbra swipe: fénykép mentés; lefelé swipe: utolsó fénykép megosztása/küldése.

## 1.40.0 (versionCode 68) — 2026-06-25

### Helyszín felismerő, GPS útvonal, OCR és hívás

- **Helyszín tanítás** – több képkocka rögzítése; vizuális ujjlenyomat (VisualFingerprint) OCR mellett; fel swipe = tanítás befejezése.
- **GPS útvonal útmutató** – automatikus visszafelé haladás észlelése; hangos irányváltás; fordított útmutatás.
- **Folyamatos szövegolvasó** – OOM védelem; egymás utáni OCR hibák számlálása és hangos figyelmeztetés.
- **Hívás befejezés** – megbízhatóbb bontás többszöri próbálkozással; balra swipe közvetlenül befejezi a hívást.

## 1.39.0 (versionCode 67) — 2026-06-25

### Hangos asszisztens – szövegértés finomhangolás

- **Több felismerési jelölt** (5 hipotézis) + bizalmi pontszám alapú választás.
- **ASR javítások:** gyakori tévesztések (ébresztő, üzenet, névjegy, WiFi, stb.) automatikus korrekciója.
- **Kontextus-hintek:** menüparancsok és gyakori kifejezések átadása a felismerőnek (Android 14+).
- **Hosszabb csend-idő** (2,8 s) és 2 újrapróbálkozás asszisztens módban.
- **Jobb hibaszövegek:** külön üzenet timeout, nincs találat, hálózat, mikrofon hibára.
- **„Ezt hallottam: …”** visszajelzés, ha a parancs nem érthető.
- **Névjegykeresés** normalizált névvel (ékezet nélkül is talál).

## 1.38.0 (versionCode 66) — 2026-06-25

### Névjegyzék és hívásnapló

- **Hívásnapló:** SMS küldés művelet a hívás kontextusmenüben (pl. utolsó hívó számára).
- **Névjegyzék menü:** fel-le söpréssel böngészés; hívás, SMS, szerkesztés, törlés műveletek.
- **Szinkronizálás:** lista tetején manuális szinkron gomb; Google névjegyzék frissítése; napi automatikus szinkron (~04:15).

## 1.37.2 (versionCode 65) — 2026-06-25

### Sürgős javítás – csengőhangok visszaállítva

- **Gyökérok**: a rendszer csengő MediaPlayere „sikeresen” elindult, de néma maradt, és a tartalék hang nem kapcsolt be
- **Megoldás**: minden emlékeztető most **beépített ébresztő sípolást** használ (ToneGenerator, STREAM_ALARM) – nem függ a telefon csengőhangjától
- **Ébresztő hangerő 0** esetén automatikus emelés (MODIFY_AUDIO_SETTINGS engedély)
- Minden hangpreset kapott beépített sípolás mintát (ALARM, NOTIFICATION, RINGTONE is)

## 1.37.1 (versionCode 64) — 2026-06-25

### Sürgős javítás – csengőhangok

- **Néma hiba javítva** – ha a rendszer csengő nem indult el, az ALARM/NOTIFICATION/RINGTONE presetek teljesen némaak maradtak (nincs fallback); most mindig van tartalék hang
- **Ébresztő stream** – csengőhangok `STREAM_ALARM` / `USAGE_ALARM` csatornán, audio focus kéréssel
- **Csengőhang hangerő** – Beállítások → Hangok → 25/50/75/100% léptetés + előnézet
- **Néma mód** – Beállítások → Hangok → ki-be kapcsoló (emlékeztető hangok némítása)

## 1.37.0 (versionCode 63) — 2026-06-25

### Új funkciók

- **Naptár – tiszta diktálás** – program dátuma és kezdési ideje közvetlen hanggal (nem számbillentyűzet-átmenet); offline bevitel swipe lefelével
- **Saját jegyzetek** – listázás, diktálással létrehozás, törlés, felolvasás; menü: Idő és Szervezés
- **Internet kereső → jegyzet** – találatnál swipe lefelé mentés; cikk olvasás közben is menthető jegyzetként
- **Hangos asszisztens** – „saját jegyzetek”, „új jegyzet”, „jegyzet törlése” parancsok

## 1.36.9 (versionCode 62) — 2026-06-25

### Stabilitás – rendbetétel 3. kör

- **Kamera modulok lifecycle** – szövegolvasó, helyszín figyelő/tanító, arc kamera: `postWhenAlive`, Handler törlés bezáráskor
- **Értesítő képernyők** – gyógyszer és naptár emlékeztető: időzített feladatok leállítása bezáráskor

### Stabilitás – teljes rendbetétel (2. kör)

- **Összeomlás napló** – `SuperDlApplication` + `crash_log.txt` a telefon belső tárhelyén
- **Adattárolók védelme** – ébresztő, időzítő, könyv, e-mail, bevásárlólista JSON sérülés esetén üresre áll (nem crashel)
- **Főmenü hálózati visszahívások** – időjárás, hírek, GPS kitekintő, navigáció, tömegközlekedés `postWhenAlive`-vel
- **Hívás képernyők** – `TelephonyCallback` (Android 12+), leállított Handler-ek bezáráskor
- **Környezeti kitekintő és pénzfelismerő** – alacsony felbontású előnézet, lifecycle-biztos UI
- **Szín/fény detektor** – OOM védelem képfeldolgozáskor

## 1.36.7 (versionCode 60) — 2026-06-25

### Stabilitás

- **Kamera modulok** – egységes alacsony felbontású előnézet (320×240), biztonságos executor leállítás minden kamera/OCR képernyőn
- **Memóriavédelem** – helyszín tanító és szövegolvasó OOM esetén leáll és hangban jelzi
- **Főmenü háttérszálak** – könyv betöltés, könyvjelző ugrás és TTS hangválasztás nem frissít UI-t bezárt képernyőn (`postWhenAlive`)
- **Új segédosztály** – `CameraStabilityHelper` közös kamera konfiguráció és leállítás

## 1.36.6 (versionCode 59) — 2026-06-25

### Javítások

- **Arc/szelfi kamera** – egyesített „Kamera és szelfi” menüpont; alacsony felbontás, késleltetett arc-felismerés, OOM védelem (nem omlik össze induláskor)
- **Gesztusok** – fel swipe: előlapi/hátoldali váltás, le swipe: kamera bemondás / videó leállítás

## 1.36.5 (versionCode 58) — 2026-06-24

### Javítások

- **Főmenü gesztusok** – eltávolítva a dupla gesztus-feldolgozás (`onTouchEvent` + `rootLayout` touch listener); swipe műveletek nem futnak kétszer
- **YouTube lejátszó** – stream betöltés közbeni gyors kilépés nem indít lejátszást bezárt képernyőn
- **Helyszín figyelő** – kamera szál biztonságos leállítása bezáráskor (memóriaszivárgás ellen)
- **Hívás DTMF** – balra swipe hangjelzés a billentyűzetből való kilépéskor (konzisztens visszajelzés)
- **Dokumentáció** – README APK útvonal és verziószám frissítve

## 1.36.4 (versionCode 57) — 2026-06-24

### Javítások

- **Pénzfelismerő** – lazább küszöbök, színellenőrzés kikapcsolva automatikus módban, stabilabb frame-feldolgozás
- **Arc/szelfi kamera** – ML Kit sorompó, biztonságosabb kamera újrakötés, lassabb képfeldolgozás (befagyás ellen)
- **Hívás DTMF** – balra swipe kilép a billentyűzetből (nem ragad be), dupla gesztus-feldolgozás megszüntetve
- **Számbevitel** – diktálás először (jobbra swipe), offline billentyűzet le swipe-pal (ébresztő, tárcsázás, időzítő, naptár, számológép, S.O.S., bevásárlólista)

## 1.36.3 (versionCode 56) — 2026-06-24

### Javítások

- **Fordítási hiba javítva** – BanknoteTorchController.kt update() függvény visszatérési értéke helyesen lett kezelve (return when).
- Build pipeline stabilizálva, debug APK generálható.