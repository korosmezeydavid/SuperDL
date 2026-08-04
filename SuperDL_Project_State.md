# SuperDL — Projekt Állapot Riport

**Generálva:** 2026-07-03  
**Forrás:** `C:\Users\msn\Documents\SuperDL-Android`  
**Verzió (build.gradle):** 1.54.3 (versionCode 94)  
**Csomagnév:** `com.superdl.launcher`  
**Kotlin forrásfájlok:** 372 db  

---

## 1. Projekt Áttekintés

### Csomag struktúra (fő package-ek)

```
com.superdl.launcher
├── alarm, apps, assistant, battery, book, calculator, calendar
├── call, callfilter, calllog, camera, cardorganizer, color, contacts
├── crash, currency          ← pénzfelismerő (kritikus)
├── dictaphone, email, environment, favorites, feedback, flow, games
├── gestures, gps, hearingaid, info, input, legal, light, locationwatch
├── lock, medication, menu, music, navigation, news, notes, notifications
├── patrol, qr, route, search, secretary, security, settings, shopping
├── sms, sos, storage, summary, system, textreader, timer, tools
├── training, transit, tts, util, voice, weather, youtube
└── SuperDlApplication.kt, MainActivity.kt
```

**Megjegyzés:** Nincs `domain` / `data` / `presentation` réteg-szétválasztás. Feature-alapú, lapos csomagstruktúra.

### Build konfiguráció

| Paraméter | Érték |
|-----------|-------|
| Build fájl formátum | **Groovy** `build.gradle` (nem `.kts`) |
| AGP | 8.5.2 |
| Kotlin | 1.9.22 |
| compileSdk / targetSdk | 34 |
| minSdk | 26 |
| JVM target | 11 |
| Compose BOM | `2024.02.00` |
| Compose Compiler Extension | `1.5.8` |
| ViewBinding | enabled |
| Compose | enabled (részlegesen használt) |

**Projekt szint:** `build.gradle` — csak plugin deklaráció (AGP + Kotlin).  
**App szint:** `app/build.gradle` — összes dependency és android blokk egy fájlban (single-module).

### Legfontosabb függőségek (`app/build.gradle`)

| Kategória | Artifact | Verzió |
|-----------|----------|--------|
| Compose UI | `androidx.compose:compose-bom` | 2024.02.00 |
| Compose Material3 | `androidx.compose.material3:material3` | BOM-managed |
| Activity Compose | `androidx.activity:activity-compose` | 1.8.2 |
| Lifecycle Compose | `lifecycle-viewmodel-compose`, `lifecycle-runtime-compose` | 2.7.0 |
| CameraX | `camera-core/camera2/lifecycle/view/video` | 1.3.1 |
| ML Kit | barcode-scanning, face-detection, text-recognition | 17.2.0 / 16.1.7 / 16.0.1 |
| TensorFlow Lite | `tensorflow-lite` + `tensorflow-lite-support` | 2.14.0 / 0.4.4 |
| Coroutines | `kotlinx-coroutines-android` | 1.7.3 |
| PDF | `pdfbox-android` | 2.0.27.0 |
| Audio encode | `tandroidlame` (JitPack) | 1.1 |
| Hidden API | `hiddenapibypass` | 4.3 |

**Nincs:** Room, DataStore, Retrofit/OkHttp, Hilt, Koin, Navigation Compose.

### DI megoldás

**[HIÁNYZIK]** — Nincs dependency injection keretrendszer.  
Objektumok közvetlen példányosítással (`by viewModels()`, `new X()`, `object` singleton Store-ok) kezelve.

---

## 2. Clean Architecture & MVVM Állapot

### Rétegek

| Réteg | Állapot |
|-------|---------|
| `domain` | **[HIÁNYZIK]** — nincs külön domain modul/csomag |
| `data` | **[HIÁNYZIK]** — nincs formális data réteg; helyette `*Store` osztályok |
| `presentation` | Részleges — csak `currency.compose` csomagban MVVM minta |

### Architektúra modell (tényleges)

**Feature-based monolith**, nem Clean Architecture:

```
MainActivity (12k+ sor, menü-állapotgép, TTS, gesztusok)
    └── Activity-per-feature (28 Activity)
            └── Helper / Store / Manager osztályok
```

### ViewModel-ek

| Osztály | Csomag | Funkció |
|---------|--------|---------|
| `CurrencyRecognizerViewModel` | `currency.compose` | Pénzfelismerő állapot, frame feldolgozás, TTS eventek |

**Összesen: 1 ViewModel** az egész projektben.

### UseCase-ek

**[HIÁNYZIK]** — Nincs `UseCase` / `Interactor` osztály. Üzleti logika közvetlenül Activity/Helper/Engine osztályokban.

### Repository-k

**[HIÁNYZIK]** — Nincs `Repository` interfész/implementáció.  
Helyettesítő adatréteg: **41 db `*Store.kt`** fájl (pl. `AlarmStore`, `ContactStore`, `FavoriteAppsStore`).

### Data layer

| Technológia | Állapot |
|-------------|---------|
| Room | **[HIÁNYZIK]** |
| DataStore | **[HIÁNYZIK]** |
| SharedPreferences | **Aktív** — `*Store` osztályok + `JsonPrefsHelper` |
| Fájlrendszer | Könyvek, diktafon, voicemail, crash log |
| Hálózat | Közvetlen HTTP (`HttpURLConnection` / helper osztályok), Nominatim, Overpass, OSM, RSS |
| ContentProvider | Névjegyek, SMS, naptár (system CP) |
| ML modellek | `app/src/main/assets/*.tflite` |

---

## 3. Kamera + Pénznem Azonosító Rendszer

### Kamera implementáció

| Paraméter | Érték |
|-----------|-------|
| API | **CameraX 1.3.1** (nem natív Camera2 közvetlenül) |
| Use case-ek | `Preview` + `ImageAnalysis` |
| Felbontás | 640×480 (`CameraAnalysisConfig`) |
| Output formátum | `OUTPUT_IMAGE_FORMAT_RGBA_8888` |
| Backpressure | `STRATEGY_KEEP_ONLY_LATEST` |
| Preview mód | `PreviewView.ImplementationMode.COMPATIBLE` |
| Kamera | `CameraSelector.DEFAULT_BACK_CAMERA` |
| Frame rate cap | 260 ms / frame (`FRAME_INTERVAL_MS`) |
| Analyzer szál | `Executors.newSingleThreadExecutor()` |

**Analyzer osztály:** `CurrencyRecognizerActivity.FrameAnalyzer` (inner class, `ImageAnalysis.Analyzer`)  
**Fájl:** `app/src/main/kotlin/com/superdl/launcher/currency/CurrencyRecognizerActivity.kt`

```kotlin
// Pipeline röviden:
ImageProxy → toBitmap() → latestBitmap cache → viewModel.onFrame(bitmap)
```

### ML modell

| Stage | Modell | Technológia | Input | Állapot |
|-------|--------|-------------|-------|---------|
| Stage 1 — Detektor | `huf_banknote_detector.tflite` | YOLO11s (Ultralytics) → TFLite export | 640×640 | **[HIÁNYZIK az assets-ből]** |
| Stage 1 — Labels | `huf_banknote_detector_labels.txt` | 6 osztály (huf_500…huf_20000) | — | **Megvan** |
| Stage 2 — Classifier | `huf_banknote_classifier.tflite` | MobileNet (224×224, 7 osztály incl. `none`) | 224×224 | **Megvan** |
| Stage 2 — Labels | `huf_banknote_labels.txt` | none + 6 címlet | — | **Megvan** |

**Training pipeline:** `tools/train_banknote_full_pipeline.py`  
**YOLO training:** `tools/train_banknote_yolo.py` — alapmodell `yolo11s.pt`, imgsz=640  
**Utolsó training run:** `tools/runs/banknote/huf_detect-2/` — `best.pt` / `last.pt` létezik, de **TFLite export nincs bemásolva assets-be**.

**TensorFlow Lite runtime:** 2.14.0, NNAPI engedélyezve (detektor), 2 szál.

### Inference pipeline (`BanknoteClassifierEngine`)

```
Bitmap
  ├─ [Stage 1] BanknoteYoloDetector.detect() → bestDetection()
  │     └─ YoloOutputParser (NMS, conf≥0.55, IoU≥0.45)
  ├─ [Stage 2] BanknoteBitmapCropper.crop(+6% pad) → BanknoteDenominationClassifier.classify()
  ├─ reconcileStages() — YOLO vs classifier egyeztetés (eltérés + magas conf → abstain)
  ├─ Fallback: center-ROI classify (BanknotePipelineMode.ROI_FALLBACK)
  └─ Fallback: full-frame classify (BanknotePipelineMode.FULL_FRAME_FALLBACK)
```

**Jelenlegi működés:** Mivel `huf_banknote_detector.tflite` hiányzik, `BanknoteYoloDetector.tryCreate()` → `null` → **`isTwoStageEnabled = false`** → csak ROI + full-frame fallback fut.

### Eredénykezelés (ViewModel réteg)

| Komponens | Szerep |
|-----------|--------|
| `BanknoteFrameGate` | Üres járat / gyenge fény detektálás (luminance, variance, edge, saturation) |
| `BanknoteTorchController` | Automatikus vaku <0.26 luminance |
| `BanknoteConsensusFilter` | 4 frame ablak, 3/4 egyezés kell stabil eredményhez |
| `BanknoteScanDebouncer` | 3200 ms cooldown, 6 frame absence → „bankjegy eltávolítva" |
| `BanknoteColorVerifier` | Domináns hue vs. címlet-szín → AGREE/NEUTRAL/DISAGREE |
| `BanknoteClassificationResult` | Küszöbök: conf≥0.52, margin≥0.10, detection≥0.55 (two-stage) |

**Megbízhatósági filozófia:** Inkább hallgat (`null`), mint téves címletet mond.

**Kimenet → felhasználó:**
- `FrameEvent.Announce` → `TtsManager.speak(denomination.speechHu)`
- `FrameEvent.PlayWorkingTick` → `ScanBeepPlayer` (halk kattintás)
- `FrameEvent.PlayEntryBeep` → bejegyzés hang
- Manuális: hangerő gomb / swipe fel-jobbra → `manualVerify()`

### TalkBack / accessibility integráció (pénzfelismerő)

| Mechanizmus | Állapot |
|-------------|---------|
| TalkBack integráció | **Nincs** — saját TTS (`TtsManager`, `USAGE_ASSISTANCE_ACCESSIBILITY` stream) |
| Compose `liveRegion` | Status szöveg: `LiveRegionMode.Assertive` ✓ |
| `contentDescription` | Status + Kilépés gomb ✓ |
| PreviewView a11y | **[HIÁNYZIK]** Compose verzióban nincs `contentDescription` / `importantForAccessibility` (XML layout-ban volt: `currency_preview_desc`, `importantForAccessibility=no`) |
| Gesztus navigáció | Swipe fel/jobbra: verify, le: help, bal: exit ✓ |
| Hangerő gomb | Azonnali manuális ellenőrzés ✓ |
| Vissza gomb | Dupla nyomás kilépés + TTS figyelmeztetés ✓ |
| OOM kezelés | TTS: „Memória elfogyott…" + scanning stop ✓ |

**TalkBackHelper:** Létezik (`apps/TalkBackHelper.kt`), de **MainActivity-ben importálva, de nem használva** (dead import).

---

## 4. Compose UI + Accessibility Állapot

### UI technológia megoszlás

| Réteg | Technológia | Terjedelem |
|-------|-------------|------------|
| Fő launcher | XML + ViewBinding (`activity_main.xml`) | ~99% UI |
| Pénzfelismerő | **Jetpack Compose** (`CurrencyRecognizerScreen`) | 1 képernyő |
| Egyéb feature-ök | XML layout-ok (28 Activity) | 27 képernyő |

### Fő képernyők

| Képernyő | Activity / Composable | UI stack |
|----------|----------------------|----------|
| Főmenü (launcher) | `MainActivity` | XML |
| Pénzfelismerő | `CurrencyRecognizerActivity` → `CurrencyRecognizerScreen` | Compose |
| Környezeti kitekintő | `EnvironmentScannerActivity` | XML |
| Arc kamera | `FaceCameraActivity` | XML |
| Szövegolvasó (OCR) | `TextReaderActivity` | XML |
| QR szkenner | `QrScanActivity` | XML |
| Helyszín felismerő | `LocationWatchActivity` / `LocationTrainerActivity` | XML |
| Hívás közben | `InCallActivity` | XML (fejlett a11y) |
| Záróképernyő | `LockScreenActivity` | XML |
| Elena / hangos asszisztens | `MainActivity` menü + `ElenaWakeListenService` | XML + Service |
| + 18 további Activity | games, music, youtube, sms, stb. | XML |

### Compose komponensek — accessibility audit

#### `CurrencyRecognizerScreen` (root)

| Szempont | Állapot |
|----------|---------|
| `contentDescription` | Nincs root szinten |
| `semantics` | Nincs |
| Focus order | **[HIÁNYZIK]** — nincs explicit traversal |
| 48 dp touch target | N/A (nincs interaktív elem) |

#### `CurrencyStatusBar` → `Text` (status)

| Szempont | Állapot |
|----------|---------|
| `contentDescription` | `statusText` ✓ |
| `semantics` | `liveRegion = Assertive` ✓ |
| Focus order | Default (első) |
| 48 dp | N/A (nem interaktív) |

#### `CurrencyStatusBar` → `Button` (Kilépés)

| Szempont | Állapot |
|----------|---------|
| `contentDescription` | „Kilépés a pénzfelismerőből" ✓ |
| `semantics` | Csak contentDescription |
| Focus order | Default (második) |
| 48 dp | **[NINCS explicit]** — Material3 default, nincs `minimumInteractiveComponentSize` |

#### `AndroidView(PreviewView)`

| Szempont | Állapot |
|----------|---------|
| `contentDescription` | **[HIÁNYZIK]** |
| `importantForAccessibility` | **[HIÁNYZIK]** (XML-ben `no` volt) |
| Gesztus | `setOnTouchListener` → swipe handler ✓ |

#### `Text` (hint, alsó)

| Szempont | Állapot |
|----------|---------|
| `contentDescription` | **[HIÁNYZIK]** |
| `semantics` | **[HIÁNYZIK]** |
| TalkBack | Vizual-only hint, TTS nem olvassa automatikusan |

#### `DetectionOverlay` (Canvas, debug)

| Szempont | Állapot |
|----------|---------|
| Láthatóság | Csak debug build + `showDetectionOverlay` |
| Accessibility | Dekoráció, nincs semantics (elfogadható) |

### XML-alapú accessibility (nem-Compose)

| Képernyő | contentDescription | Egyéb |
|----------|-------------------|-------|
| `activity_main.xml` | **[HIÁNYZIK]** minden TextView-n | Fő navigáció TTS-en keresztül, nem TalkBack-en |
| `activity_in_call.xml` | 5 elem ✓ | `AccessibilityPaneTitle`, custom actions (`InCallActivity`) |
| `activity_environment_scanner.xml` | 9 elem ✓ | Scan toggle dinamikus desc |
| `activity_currency_recognizer.xml` | 3 elem ✓ | **Legacy** — Compose migráció után nem használt |

### TalkBack tesztelés állapota

| Típus | Állapot |
|-------|---------|
| Automatizált teszt (`androidTest`) | **[HIÁNYZIK]** — nincs test forrás |
| Espresso Accessibility Checks | **[HIÁNYZIK]** |
| Manuális tesztprotokoll dokumentálva | **[HIÁNYZIK]** |
| Tényleges tesztelés | Fejlesztői napló szerint Ulefone Armor 24-en manuális teszt (nem TalkBack-specifikus) |

**Következtetés:** Az app **TTS-first** accessibility modellt követ, nem TalkBack-first. A Compose migráció accessibility regressziót okozott a PreviewView-nél.

---

## 5. Kritikus Osztályok és Fájlok

| # | Fájl | Szerep |
|---|------|--------|
| 1 | `app/src/main/kotlin/com/superdl/launcher/currency/CurrencyRecognizerActivity.kt` | CameraX binding, `FrameAnalyzer`, gesztus/hangerő kezelés, Compose host, TTS event routing |
| 2 | `app/src/main/kotlin/com/superdl/launcher/currency/compose/CurrencyRecognizerViewModel.kt` | MVVM állapotgép: frame mutex, engine lifecycle, consensus/debounce, overlay state |
| 3 | `app/src/main/kotlin/com/superdl/launcher/currency/compose/CurrencyRecognizerScreen.kt` | Egyetlen Compose UI: PreviewView, status bar, debug overlay |
| 4 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteClassifierEngine.kt` | Kétlépcsős inference orchestrator + fallback lánc |
| 5 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteYoloDetector.kt` | Stage 1 YOLO TFLite interpreter (jelenleg nem töltődik be — hiányzó asset) |
| 6 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteDenominationClassifier.kt` | Stage 2 MobileNet 224×224 classifier |
| 7 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteClassificationResult.kt` | Küszöbök, `isReliable()`, fused confidence, pipeline mode |
| 8 | `app/src/main/kotlin/com/superdl/launcher/camera/CameraAnalysisConfig.kt` | ImageAnalysis builder: 640×480, RGBA, KEEP_ONLY_LATEST |
| 9 | `app/src/main/kotlin/com/superdl/launcher/MainActivity.kt` | Launcher HOME activity, menü-állapotgép (~12k sor), összes feature belépési pont |
| 10 | `app/src/main/kotlin/com/superdl/launcher/menu/MenuTree.kt` | Teljes menüfa definíció, `CURRENCY_RECOGNIZER` action |
| 11 | `app/src/main/kotlin/com/superdl/launcher/tts/TtsManager.kt` | Központi TTS: `USAGE_ASSISTANCE_ACCESSIBILITY`, speak queue, runWhenReady |
| 12 | `tools/train_banknote_full_pipeline.py` | ML pipeline: YOLO train → TFLite export → classifier → assets másolás |

**Támogató kritikus fájlok:**
- `currency/BanknoteConsensusFilter.kt` — temporal stability
- `currency/BanknoteScanDebouncer.kt` — announce cooldown
- `currency/BanknoteFrameGate.kt` — empty slot / low light
- `currency/YoloOutputParser.kt` — Ultralytics output parsing + NMS
- `app/src/main/assets/huf_banknote_classifier.tflite` — production classifier modell

---

## 6. Ismert Problémák / TODO / Technikai Adósság

### Blokkoló / kritikus

| # | Probléma | Hatás |
|---|----------|-------|
| 1 | **`huf_banknote_detector.tflite` hiányzik** az `assets/`-ből | Kétlépcsős pipeline kikapcsolva; csak ROI/full-frame fallback. Pontosság jelentősen csökken. |
| 2 | YOLO training kész (`best.pt`), TFLite export **nincs deployolva** | Training erőforrás kihasználatlan |
| 3 | **`ImageProxy.toBitmap()` frame-enként** 260 ms-enként | OOM kockázat (kezelve, de scanning leáll) — Armor 24-en tapasztalt |

### Accessibility hiányosságok

| # | Probléma |
|---|----------|
| 1 | Compose `PreviewView` — nincs `importantForAccessibility="no"` (XML-ből elveszett) |
| 2 | `TalkBackHelper` importálva, de **sehol nem hívva** |
| 3 | `activity_main.xml` — nincs `contentDescription` / `accessibilityLiveRegion` |
| 4 | Nincs TalkBack teszt, nincs `androidTest` |
| 5 | Hint szöveg Compose-ban vizuális only — screen reader nem kapja |
| 6 | Kilépés gomb — nincs explicit 48 dp minimum méret |

### Architektúra / kódminőség

| # | Probléma |
|---|----------|
| 1 | `MainActivity` ~12 000 sor — single point of failure |
| 2 | Clean Architecture **[HIÁNYZIK]** |
| 3 | DI **[HIÁNYZIK]** |
| 4 | Csak 1 ViewModel az egész appban |
| 5 | Legacy `activity_currency_recognizer.xml` — halott kód |
| 6 | Dokumentáció verzió eltérés: `fejlesztesi-naplo.txt` → 1.48.0, `build.gradle` → 1.54.3 |

### Teljesítmény / memória

| # | Probléma |
|---|----------|
| 1 | Bitmap másolás minden frame-nél (`copyFrame` ARGB_8888) + `latestBitmap` cache |
| 2 | Két TFLite interpreter párhuzamosan (ha detektor meglenne) — memória nyomás |
| 3 | NNAPI fallback silent catch — nincs telemetria mely backend fut |
| 4 | Nincs frame pooling / reusable buffer |

### Nyitott fejlesztési tételek (fejlesztési napló)

- [ ] Saját bankjegyfotók begyűjtése + újratanítás
- [ ] YOLO pipeline finomhangolás / TFLite deploy
- [ ] Elena tudásbázis verzió frissítés
- [ ] README verzió szinkron

---

## 7. Következő Lépések Javaslata

### Azonnali (P0 — ma/holnap)

1. **YOLO TFLite deploy:** Futtatni `python tools/train_banknote_yolo.py --export-tflite` (vagy `finish_banknote_pipeline.py --copy-only`), majd `huf_banknote_detector.tflite` bemásolása `app/src/main/assets/`-be. Enélkül a kétlépcsős pipeline halott kód.

2. **Compose a11y regresszió javítás** (`CurrencyRecognizerScreen.kt`):
   - `PreviewView`: `importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO`
   - Kilépés gomb: `Modifier.minimumInteractiveComponentSize()` vagy explicit `48.dp` min méret

3. **Smoke test** Ulefone Armor 24-en: mind a 6 címlet, gyenge fény, üres járat, hangerő gomb verify.

### Rövid táv (P1 — 1–2 hét)

4. **Memória optimalizálás:** Frame buffer pool; `RGB_565` vizsgálat classifier inputhoz; csökkenteni `copyFrame` szükségességét.

5. **Telemetry:** Pipeline mode (`TWO_STAGE` vs fallback) és confidence logging debug buildben — training feedback loop.

6. **TalkBack integrációs réteg:** `TalkBackHelper.isEnabled()` → dinamikus viselkedés (pl. vizuális hint elrejtése ha TalkBack aktív).

7. **Halott kód takarítás:** `activity_currency_recognizer.xml` törlése vagy visszaállítás fallback-ként.

### Közép táv (P2 — architektúra)

8. **Currency modul szétválasztás:** `CurrencyRecognizerActivity` → kamera/usecase/engine rétegek; Activity max. wiring.

9. **DI bevezetés** (Hilt) legalább a `currency` feature-re: `BanknoteClassifierEngine`, `TtsManager` injection.

10. **androidTest baseline:** Legalább `CurrencyRecognizerScreen` semantics snapshot teszt + manuális TalkBack checklist dokumentum.

11. **MainActivity dekompozíció:** Menü-állapotgép kivitele külön `MenuController` / feature router osztályba.

---

## Függelék: Assets állapot

```
app/src/main/assets/
├── huf_banknote_classifier.tflite     ✓ (Stage 2)
├── huf_banknote_labels.txt            ✓
├── huf_banknote_detector_labels.txt   ✓
├── huf_banknote_detector.tflite       ✗ [HIÁNYZIK]
├── mobilenet_ssd_v1.tflite            ✓ (környezeti kitekintő)
├── coco_labels.txt                    ✓
└── elena_tudas_superdl.txt            ✓
```

## Függelék: Verzió inkonzisztencia

| Forrás | Verzió |
|--------|--------|
| `app/build.gradle` | 1.54.3 (94) |
| `dokumentumok/fejlesztesi-naplo.txt` | 1.48.0 (85) — **elavult** |

---

*Riport készítette: kódbázis statikus analízis, 2026-07-03.*