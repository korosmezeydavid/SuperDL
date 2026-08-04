package com.superdl.launcher.screenreader

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.superdl.launcher.tts.TtsManager

/**
 * SUPERDL KÉPERNYŐOLVASÓ — kezdeti változat.
 *
 * Célja, hogy a megszokott NÉGY GESZTUSSAL a KÜLSŐ alkalmazások is kezelhetők
 * legyenek: fel-le lépkedés az elemeken felolvasással, jobbra aktiválás,
 * balra vissza.
 *
 * KÉT FONTOS ELV:
 *
 * 1. CSAK KÜLSŐ ALKALMAZÁSBAN AKTÍV.
 *    A SuperDL saját felületén kikapcsol, hogy ne ütközzön a launcher saját
 *    beszédével és gesztusaival. Ezt az előtérben lévő csomagnév alapján
 *    döntjük el, és a rendszer érintés-kezelését is ennek megfelelően kérjük
 *    vagy engedjük el.
 *
 * 2. BIZTONSÁGI RETESZ.
 *    Minden művelet a ScreenReaderPrefs kapcsolóitól függ. Hiba esetén a
 *    hibaszámláló nő, és sorozatos hiba után a szolgáltatás MAGÁTÓL leáll
 *    (vészleállítás), hogy semmiképp ne tegye használhatatlanná a telefont.
 */
class ScreenReaderService : AccessibilityService() {

    private var tts: TtsManager? = null
    private var sounds: ScreenReaderSounds? = null
    private var voiceInput: com.superdl.launcher.voice.VoiceInput? = null
    private var imageReader: ScreenReaderImageReader? = null
    private val handler = android.os.Handler(android.os.Looper.getMainLooper())
    private var nodes: List<AccessibilityNodeInfo> = emptyList()
    private var index = 0
    private var touchModeActive = false
    private var currentPackage: String? = null

    /** Frissíteni kell-e az elemlistát a következő gesztusnál. */
    private var nodesStale = false

    /** Szünetel-e az olvasó, mert billentyűzet van a képernyőn. */
    private var keyboardSuspended = false

    /**
     * A legutóbb felolvasott elem címkéje. A képernyő frissülése után ez alapján
     * keressük meg újra, hol álltunk — enélkül a kurzor a lista elejére ugrana
     * minden apró változásnál (óra, töltésjelző).
     */
    private var lastLabel: String? = null

    // ── TUNING: navigációs mód és olvasási részletesség ─────────────────────

    /** MIT lépkedünk végig (minden / címsor / link / gomb / mező / szöveg). */
    private var mode = NavigationMode.ALL

    /** MEKKORA egységekben olvasunk (elem / mondat / szó / betű). */
    private var granularity = ReadingGranularity.ELEMENT

    /** A módra szűrt elemlista — ezen lépked a fel-le söprés. */
    private var filtered: List<AccessibilityNodeInfo> = emptyList()

    /** Az aktuális elem szövegének darabjai és a pozíció köztük. */
    private var segments: List<String> = emptyList()
    private var segmentIndex = 0

    /** A legutóbb kimondott szöveg — az ismétléshez. */
    private var lastSpoken: String = ""

    /** Fut-e a folyamatos olvasás. */
    private var continuousReading = false

    override fun onServiceConnected() {
        super.onServiceConnected()
        android.util.Log.i(ScreenReaderPrefs.TAG, "Kepernyoolvaso szolgaltatas csatlakozott")
        tts = try {
            TtsManager(this)
        } catch (e: Exception) {
            ScreenReaderPrefs.reportFailure(this, "TTS indítás: ${e.message}")
            null
        }
        sounds = try {
            ScreenReaderSounds(this)
        } catch (e: Exception) {
            android.util.Log.w(ScreenReaderPrefs.TAG, "Hangok: ${e.message}")
            null
        }
        voiceInput = try {
            com.superdl.launcher.voice.VoiceInput(this)
        } catch (_: Exception) {
            null
        }
        imageReader = try {
            ScreenReaderImageReader(this)
        } catch (_: Exception) {
            null
        }
        // Induláskor NEM kérünk érintés-kezelést: csak akkor, ha külső app jön.
        setTouchExploration(false)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return
        if (ScreenReaderPrefs.isEmergencyDisabled(this)) {
            setTouchExploration(false)
            return
        }

        when (event.eventType) {
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED,
            AccessibilityEvent.TYPE_WINDOWS_CHANGED -> {
                // A csomagnevet NEM csak az eseményből vesszük: kilépéskor az
                // gyakran hiányzik vagy a rendszeré, ezért maradt bekapcsolva az
                // olvasó. A ténylegesen előtérben lévő ablak a megbízható forrás.
                val pkg = resolveForegroundPackage(event)
                if (pkg != null && pkg != currentPackage) {
                    currentPackage = pkg
                    onForegroundAppChanged(pkg)
                }
                // BILLENTYŰZET-ÜTKÖZÉS ELLEN: ha épp beviteli billentyűzet van a
                // képernyőn, ÁTADJUK neki az érintéseket. Enélkül az olvasó
                // elfogná őket, és a mátrix billentyűzet csúsztatásos írása nem
                // működne — az ablak ugyanis NEM vált a billentyűzet
                // megjelenésekor, tehát a csomagnév-figyelés erre vak.
                updateKeyboardSuspension()
            }
            AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED -> {
                // A képernyő tartalma változott. Ez NAGYON gyakran érkezik
                // (óra, töltésjelző, animáció), ezért nem ürítünk minden
                // alkalommal — csak megjelöljük, hogy frissíteni kell.
                nodesStale = true
            }
        }
    }

    /**
     * Fut-e éppen beviteli billentyűzet? Ha igen, az olvasó elengedi az
     * érintéseket, hogy a billentyűzet kaphassa meg őket.
     */
    private fun updateKeyboardSuspension() {
        val keyboardShowing = try {
            windows.any { it.type == android.view.accessibility.AccessibilityWindowInfo.TYPE_INPUT_METHOD }
        } catch (_: Exception) {
            false
        }
        if (keyboardShowing == keyboardSuspended) return
        keyboardSuspended = keyboardShowing
        android.util.Log.i(
            ScreenReaderPrefs.TAG,
            "billentyuzet ${if (keyboardShowing) "MEGJELENT -> olvaso szunetel" else "eltunt -> olvaso folytatja"}"
        )
        // Ha billentyűzet van, elengedjük az érintéseket; ha eltűnt, és külső
        // appban vagyunk, visszavesszük.
        setTouchExploration(!keyboardShowing && shouldRunInCurrentApp())
    }

    /** Kell-e most futnia az olvasónak a jelenlegi alkalmazásban? */
    private fun shouldRunInCurrentApp(): Boolean {
        val pkg = currentPackage ?: return false
        val own = pkg.startsWith(packageName.removeSuffix(".debug"))
        return !own && pkg !in SYSTEM_PACKAGES && ScreenReaderPrefs.isEnabled(this)
    }

    /**
     * Melyik alkalmazás van TÉNYLEGESEN előtérben?
     *
     * Elsőként az aktív ablakot kérdezzük (ez akkor is helyes, ha az esemény
     * csomagneve hiányzik), és csak tartalékként használjuk az eseményt.
     */
    private fun resolveForegroundPackage(event: AccessibilityEvent): String? {
        val fromWindow = try {
            rootInActiveWindow?.packageName?.toString()
        } catch (_: Exception) {
            null
        }
        if (!fromWindow.isNullOrBlank()) return fromWindow
        return event.packageName?.toString()?.takeIf { it.isNotBlank() }
    }

    /**
     * Előtérbe került egy másik alkalmazás. Ha SAJÁT (SuperDL), kikapcsolunk;
     * ha külső, és a felhasználó engedélyezte, bekapcsolunk.
     */
    private fun onForegroundAppChanged(pkg: String) {
        val own = pkg.startsWith(packageName.removeSuffix(".debug"))
        // A rendszer saját felületei (értesítési sáv, legutóbbiak, engedélykérő
        // ablakok) NEM külső alkalmazások: ott hagyjuk a megszokott működést,
        // nehogy a felhasználó ne tudja kezelni őket.
        val systemUi = pkg in SYSTEM_PACKAGES
        val shouldRun = !own && !systemUi && ScreenReaderPrefs.isEnabled(this)

        android.util.Log.i(
            ScreenReaderPrefs.TAG,
            "elterben: $pkg (sajat=$own, rendszer=$systemUi) -> olvaso ${if (shouldRun) "BE" else "KI"}"
        )

        val wasRunning = touchModeActive
        setTouchExploration(shouldRun)
        clearNodes()
        index = 0
        lastLabel = null      // új alkalmazás: a régi pozíció érvénytelen

        when {
            shouldRun && !wasRunning -> {
                sounds?.play(ScreenReaderSounds.Sound.ON)
                // ALKALMAZÁSONKÉNTI BEÁLLÍTÁS: ott folytatjuk, ahol legutóbb
                // abbahagytuk ebben az alkalmazásban (pl. böngészőben címsorok).
                restoreAppSettings(pkg)
                tts?.speak("${appLabelOf(pkg)}. Képernyőolvasó bekapcsolva.")
                ScreenReaderPrefs.reportSuccess(this)
                // AUTOMATIKUS FELOLVASÁS: mondja el, mi van a képernyőn, hogy
                // ne kelljen vakon tapogatózni.
                if (ScreenReaderPrefs.isAutoRead(this)) {
                    handler.postDelayed({ autoReadScreen() }, 900L)
                }
            }
            // Kilépéskor is jelezzük — enélkül nem lehet tudni, hogy már nem
            // az olvasó kezeli az érintéseket.
            !shouldRun && wasRunning && own -> {
                sounds?.play(ScreenReaderSounds.Sound.OFF)
                tts?.speak("Képernyőolvasó kikapcsolva.")
            }
        }
    }

    /** Az alkalmazáshoz mentett mód és részletesség visszaállítása. */
    private fun restoreAppSettings(pkg: String) {
        val (savedMode, savedGran) = ScreenReaderPrefs.loadAppMode(this, pkg)
        mode = savedMode?.let { name ->
            NavigationMode.entries.firstOrNull { it.name == name }
        } ?: NavigationMode.ALL
        granularity = savedGran?.let { name ->
            ReadingGranularity.entries.firstOrNull { it.name == name }
        } ?: ReadingGranularity.ELEMENT
        if (mode != NavigationMode.ALL || granularity != ReadingGranularity.ELEMENT) {
            android.util.Log.i(
                ScreenReaderPrefs.TAG,
                "$pkg beallitasa visszaallitva: ${mode.name} / ${granularity.name}"
            )
        }
    }

    /** A jelenlegi mód és részletesség megjegyzése ehhez az alkalmazáshoz. */
    private fun rememberAppSettings() {
        val pkg = currentPackage ?: return
        ScreenReaderPrefs.saveAppMode(this, pkg, mode.name, granularity.name)
    }

    /**
     * AUTOMATIKUS FELOLVASÁS: új képernyőre lépve elmondja, mi van rajta —
     * a képernyő címét és az első pár elemet.
     */
    private fun autoReadScreen() {
        if (!touchModeActive || keyboardSuspended) return
        nodesStale = true
        ensureNodes()
        if (filtered.isEmpty()) return

        val title = screenTitle()
        val firstFew = filtered.take(3).mapNotNull { ScreenReaderNavigator.labelOf(it) }
        val parts = mutableListOf<String>()
        if (!title.isNullOrBlank()) parts += title
        parts += "${filtered.size} elem"
        if (firstFew.isNotEmpty()) parts += firstFew.joinToString(", ")
        say(parts.joinToString(". "))
    }

    /** A képernyő címe, ha az alkalmazás megadja. */
    private fun screenTitle(): String? = try {
        windows.firstOrNull { it.isActive }?.title?.toString()?.takeIf { it.isNotBlank() }
    } catch (_: Exception) {
        null
    }

    /** Az alkalmazás emberi neve a csomagnévből (pl. "WhatsApp"). */
    private fun appLabelOf(pkg: String): String = try {
        val pm = packageManager
        pm.getApplicationLabel(pm.getApplicationInfo(pkg, 0)).toString()
    } catch (_: Exception) {
        "Külső alkalmazás"
    }

    companion object {
        /**
         * Ezeken NEM vesszük át az érintés-kezelést.
         *
         * MEGJEGYZÉS: a rendszerfelület (systemui) SZÁNDÉKOSAN NEM szerepel itt.
         * Az értesítési sáv ugyanis ahhoz tartozik — ha kizárnánk, az olvasó
         * lekapcsolna, és a lehúzott értesítéseket nem lehetne felolvasni.
         * Az engedélykérő ablakokat viszont meghagyjuk a rendszernek.
         */
        private val SYSTEM_PACKAGES = setOf(
            "com.android.permissioncontroller",
            "com.google.android.permissioncontroller"
        )

        /**
         * A képernyőolvasó gesztusai — felolvasható súgó.
         * A menüből is lekérhető, hogy ne kelljen fejből tudni.
         */
        fun speakGestureHelp(): String = listOf(
            "A képernyőolvasó mozdulatai.",
            "EGY UJJAL — mozgás.",
            "Söprés le: következő. Söprés fel: előző.",
            "Söprés jobbra: megnyomás. Söprés balra: vissza.",
            "Le majd fel: görgetés lefelé. Fel majd le: görgetés felfelé.",
            "Balra majd jobbra: első elem. Jobbra majd balra: utolsó elem.",
            "Fel majd balra: kezdőképernyő. Fel majd jobbra: legutóbbi alkalmazások.",
            "Le majd balra: értesítések. Le majd jobbra: hosszan nyomás.",
            "KÉT UJJAL — mit olvasunk.",
            "Jobbra és balra: váltás a módok között. Minden elem, címsorok, " +
                "hivatkozások, gombok, beviteli mezők, szöveg.",
            "Lefelé: folyamatos olvasás. Felfelé: az utolsó mondat megismétlése.",
            "Két ujjal DUPLA KOPPINTÁS: keresés a képernyőn — kimondod, mit keresel.",
            "HÁROM UJJAL — hogyan olvassuk.",
            "Jobbra: részletesebb. Balra: durvább. Elem, mondat, szó, betű.",
            "Lefelé: hol vagyok. Felfelé: ez a súgó.",
            "Három ujjal DUPLA KOPPINTÁS: a kép felolvasása — mi van rajta írva.",
            "Három ujjal HÁRMAS KOPPINTÁS: a névtelen elem elnevezése — kimondod, " +
                "minek hívjuk, és a program megjegyzi.",
            "Két ujjal HÁRMAS KOPPINTÁS: a színek felolvasása — piros, zöld, szürke.",
            "NÉGY UJJAL — táblázatban: fel-le sorváltás, jobbra-balra oszlopváltás."
        ).joinToString(" ")
    }

    /**
     * Az érintés-kezelés átvétele a rendszertől. Csak akkor kérjük, amikor
     * tényleg dolgozunk — így a SuperDL saját felületén és kikapcsolt állapotban
     * semmit nem változtatunk a telefon megszokott működésén.
     */
    private fun setTouchExploration(on: Boolean) {
        if (touchModeActive == on) return
        try {
            val info = serviceInfo ?: return
            // FONTOS: a TÖBB UJJAS gesztusokat KÜLÖN kérni kell! Enélkül a
            // rendszer el sem küldi a két- és háromujjas söpréseket, hiába
            // kezeljük őket a kódban — ezért nem működött a mód- és a
            // részletesség-váltás. (Android 11 / API 30 felett érhető el.)
            val multiFinger =
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
                    AccessibilityServiceInfo.FLAG_REQUEST_MULTI_FINGER_GESTURES
                } else 0

            info.flags = if (on) {
                info.flags or
                    AccessibilityServiceInfo.FLAG_REQUEST_TOUCH_EXPLORATION_MODE or
                    multiFinger
            } else {
                info.flags and
                    AccessibilityServiceInfo.FLAG_REQUEST_TOUCH_EXPLORATION_MODE.inv() and
                    multiFinger.inv()
            }
            serviceInfo = info
            touchModeActive = on
            android.util.Log.i(
                ScreenReaderPrefs.TAG,
                "erintes-kezeles ${if (on) "BE" else "KI"}, tobb ujjas gesztusok=${multiFinger != 0}"
            )
        } catch (e: Exception) {
            ScreenReaderPrefs.reportFailure(this, "érintés-kezelés váltás: ${e.message}")
        }
    }

    // ── GESZTUSOK ───────────────────────────────────────────────────────────

    override fun onGesture(gestureId: Int): Boolean {
        // AZONNALI KIKAPCSOLÁS: ha közben letiltották (vagy vészleállítás jött),
        // engedjük vissza az érintéseket a rendszernek. Enélkül a telefon
        // "halottnak" tűnne: az olvasó elfogná a mozdulatokat, de nem csinálna
        // semmit — egészen a következő alkalmazás-váltásig.
        if (!ScreenReaderPrefs.isEnabled(this)) {
            setTouchExploration(false)
            return false
        }
        if (!touchModeActive || keyboardSuspended) return false
        return try {
            when (gestureId) {
                // ── ALAP NÉGY GESZTUS ──────────────────────────────────────
                GESTURE_SWIPE_DOWN -> { move(+1); true }
                GESTURE_SWIPE_UP -> { move(-1); true }
                GESTURE_SWIPE_RIGHT -> { activateCurrent(); true }
                GESTURE_SWIPE_LEFT -> {
                    sounds?.play(ScreenReaderSounds.Sound.BACK)
                    performGlobalAction(GLOBAL_ACTION_BACK); true
                }

                // ── GÖRGETÉS (hosszú listákhoz) ────────────────────────────
                // Le-fel: görgetés előre. Fel-le: görgetés vissza.
                GESTURE_SWIPE_DOWN_AND_UP -> { scrollPage(forward = true); true }
                GESTURE_SWIPE_UP_AND_DOWN -> { scrollPage(forward = false); true }

                // ── UGRÁS A LISTA ELEJÉRE / VÉGÉRE ────────────────────────
                GESTURE_SWIPE_LEFT_AND_RIGHT -> { jumpTo(first = true); true }
                GESTURE_SWIPE_RIGHT_AND_LEFT -> { jumpTo(first = false); true }

                // ── RENDSZERGOMBOK ────────────────────────────────────────
                GESTURE_SWIPE_UP_AND_LEFT -> { goHome(); true }
                GESTURE_SWIPE_UP_AND_RIGHT -> { openRecents(); true }
                GESTURE_SWIPE_DOWN_AND_LEFT -> { openNotifications(); true }

                // ── RÉSZLETEK / HOSSZAN NYOMÁS ────────────────────────────
                GESTURE_SWIPE_DOWN_AND_RIGHT -> { longPressCurrent(); true }

                // ── KÉT UJJAL: MIT olvasunk ───────────────────────────────
                // (Android 11 felett érkeznek ilyen események; régebbin a
                //  menüből érhetők el ugyanezek a funkciók.)
                GESTURE_2_FINGER_SWIPE_RIGHT -> { switchMode(forward = true); true }
                GESTURE_2_FINGER_SWIPE_LEFT -> { switchMode(forward = false); true }
                GESTURE_2_FINGER_SWIPE_DOWN -> { startContinuousReading(); true }
                GESTURE_2_FINGER_SWIPE_UP -> { repeatLast(); true }

                // ── HÁROM UJJAL: HOGYAN olvassuk ──────────────────────────
                GESTURE_3_FINGER_SWIPE_RIGHT -> { switchGranularity(finer = true); true }
                GESTURE_3_FINGER_SWIPE_LEFT -> { switchGranularity(finer = false); true }
                GESTURE_3_FINGER_SWIPE_DOWN -> { whereAmI(); true }
                GESTURE_3_FINGER_SWIPE_UP -> { say(speakGestureHelp()); true }

                // ── KERESÉS a képernyőn (kimondod, mit keresel) ───────────
                GESTURE_2_FINGER_DOUBLE_TAP -> { searchByVoice(); true }

                // ── KÉP FELOLVASÁSA és SAJÁT ELNEVEZÉS ────────────────────
                GESTURE_3_FINGER_DOUBLE_TAP -> { readImageAtCursor(); true }
                GESTURE_3_FINGER_TRIPLE_TAP -> { labelCurrentElement(); true }

                // ── SZÍNFELISMERÉS ────────────────────────────────────────
                GESTURE_2_FINGER_TRIPLE_TAP -> { readColorsAtCursor(); true }

                // ── TÁBLÁZAT: sor- és oszlop-navigáció ────────────────────
                GESTURE_4_FINGER_SWIPE_DOWN -> { moveInGrid(byRow = true, forward = true); true }
                GESTURE_4_FINGER_SWIPE_UP -> { moveInGrid(byRow = true, forward = false); true }
                GESTURE_4_FINGER_SWIPE_RIGHT -> { moveInGrid(byRow = false, forward = true); true }
                GESTURE_4_FINGER_SWIPE_LEFT -> { moveInGrid(byRow = false, forward = false); true }

                else -> false
            }
        } catch (e: Exception) {
            ScreenReaderPrefs.reportFailure(this, "gesztus: ${e.message}")
            false
        }
    }

    // ── MŰVELETEK ───────────────────────────────────────────────────────────

    /** Görgetés egy "képernyőnyit", majd az új tartalom első elemére állás. */
    private fun scrollPage(forward: Boolean) {
        val node = nodes.getOrNull(index)
        var ok = ScreenReaderNavigator.scroll(node, forward)
        if (!ok) {
            // Az aktuális elem szülői közt nincs görgethető: keressünk a fában.
            val root = try { rootInActiveWindow } catch (_: Exception) { null }
            val scrollable = ScreenReaderNavigator.findScrollable(root)
            ok = scrollable != null && ScreenReaderNavigator.scroll(scrollable, forward)
        }
        if (!ok) {
            sounds?.play(ScreenReaderSounds.Sound.EDGE)
            tts?.speak(if (forward) "A lista végén vagy." else "A lista elején vagy.")
            return
        }
        // A tartalom változott: friss beolvasás, és az első elemre állunk.
        clearNodes()
        index = 0
        nodesStale = true
        ensureNodes()
        // HELYZETJELZŐ: a hang magassága mutatja, hol tartunk, és a százalék is
        // elhangzik — így görgetés közben végig tudod, mennyi van még hátra.
        val percent = positionPercent()
        sounds?.playAtPosition(
            if (forward) ScreenReaderSounds.Sound.SCROLL_DOWN
            else ScreenReaderSounds.Sound.SCROLL_UP,
            positionRatio()
        )
        tts?.speak(
            if (forward) "Görgetés lefelé, $percent százalék."
            else "Görgetés felfelé, $percent százalék."
        )
        handler.postDelayed({
            ensureNodes()
            filtered.getOrNull(index)?.let {
                tts?.speakAdd(ScreenReaderNavigator.describe(it))
            }
        }, 350L)
    }

    /** Ugrás a lista első vagy utolsó elemére. */
    private fun jumpTo(first: Boolean) {
        stopContinuousReading()
        ensureNodes()
        if (filtered.isEmpty()) {
            sounds?.play(ScreenReaderSounds.Sound.EDGE)
            say("Nincs felolvasható elem.")
            return
        }
        index = if (first) 0 else filtered.lastIndex
        sounds?.play(
            if (first) ScreenReaderSounds.Sound.FIRST else ScreenReaderSounds.Sound.LAST
        )
        val node = filtered[index]
        lastLabel = ScreenReaderNavigator.labelOf(node)
        prepareSegments(node, fromEnd = false)
        say(
            (if (first) "Első elem. " else "Utolsó elem. ") +
                "${ScreenReaderNavigator.describe(node)}. ${index + 1} / ${filtered.size}"
        )
    }

    private fun goHome() {
        sounds?.play(ScreenReaderSounds.Sound.HOME)
        tts?.speak("Kezdőképernyő.")
        performGlobalAction(GLOBAL_ACTION_HOME)
        clearNodes()
        index = 0
    }

    private fun openRecents() {
        sounds?.play(ScreenReaderSounds.Sound.RECENTS)
        tts?.speak("Legutóbbi alkalmazások.")
        performGlobalAction(GLOBAL_ACTION_RECENTS)
        clearNodes()
        index = 0
    }

    private fun openNotifications() {
        sounds?.play(ScreenReaderSounds.Sound.NOTIFICATIONS)
        tts?.speak("Értesítések.")
        performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
        clearNodes()
        index = 0
        lastLabel = null
        // A sáv lehúzása után ELOLVASSUK az első értesítést — enélkül csak
        // annyit hallanál, hogy "Értesítések", és magadnak kellene keresgélni.
        handler.postDelayed({
            nodesStale = true
            ensureNodes()
            if (filtered.isEmpty()) {
                say("Nincs értesítés.")
            } else {
                say("${filtered.size} elem. ${ScreenReaderNavigator.describe(filtered[0])}")
            }
        }, 700L)
    }

    /** Hosszan nyomás: a rejtett lehetőségek (törlés, megosztás) előhívása. */
    private fun longPressCurrent() {
        ensureNodes()
        val node = filtered.getOrNull(index)
        if (node == null) {
            tts?.speak("Nincs kiválasztott elem.")
            return
        }
        val ok = ScreenReaderNavigator.longPress(node)
        if (ok) {
            sounds?.play(ScreenReaderSounds.Sound.LONG_PRESS)
            tts?.speak("Hosszan megnyomva.")
            clearNodes()
        } else {
            sounds?.play(ScreenReaderSounds.Sound.ERROR)
            tts?.speak("Ezen az elemen nincs hosszan nyomás.")
        }
    }

    // ── TUNING MŰVELETEK ────────────────────────────────────────────────────

    /**
     * Navigációs mód váltása. Bemondja a módot ÉS azt, hány elem van benne —
     * így rögtön tudod, van-e értelme ott lépkedni.
     */
    fun switchMode(forward: Boolean) {
        stopContinuousReading()
        mode = if (forward) NavigationMode.next(mode) else NavigationMode.previous(mode)
        rememberAppSettings()   // ehhez az alkalmazáshoz megjegyezzük
        nodesStale = true
        ensureNodes()
        index = 0
        segments = emptyList()
        segmentIndex = 0
        sounds?.play(ScreenReaderSounds.Sound.RECENTS)
        if (filtered.isEmpty()) {
            // ÜRES MÓD: ezt meg KELL mondani, különben a felhasználó azt hinné,
            // elromlott valami. Natív alkalmazásokban a "címsor" és a
            // "hivatkozás" fogalom gyakran nem is létezik.
            say("${mode.label}: nincs ilyen elem ezen a képernyőn.")
        } else {
            say("${mode.label}. ${filtered.size} darab.")
            filtered.firstOrNull()?.let {
                lastLabel = ScreenReaderNavigator.labelOf(it)
                prepareSegments(it, fromEnd = false)
                tts?.speakAdd(ScreenReaderNavigator.describe(it))
            }
        }
    }

    /** Olvasási részletesség váltása (elem > mondat > szó > betű). */
    fun switchGranularity(finer: Boolean) {
        stopContinuousReading()
        val previous = granularity
        granularity = if (finer) {
            ReadingGranularity.finer(granularity)
        } else {
            ReadingGranularity.coarser(granularity)
        }
        sounds?.play(ScreenReaderSounds.Sound.FIELD)
        if (granularity == previous) {
            say(
                if (finer) "Ez a legrészletesebb: betűnként."
                else "Ez a legdurvább: elemenként."
            )
            return
        }
        say("Olvasás: ${granularity.label}.")
        rememberAppSettings()   // ehhez az alkalmazáshoz megjegyezzük
        // Az aktuális elem szövegét újra felbontjuk az új részletességre.
        filtered.getOrNull(index)?.let { prepareSegments(it, fromEnd = false) }
    }

    /**
     * FOLYAMATOS OLVASÁS: az aktuális elemtől végigolvassa a képernyőt.
     * Bármely gesztus megállítja.
     */
    fun startContinuousReading() {
        ensureNodes()
        if (filtered.isEmpty()) {
            say("Nincs mit felolvasni.")
            return
        }
        continuousReading = true
        sounds?.play(ScreenReaderSounds.Sound.SCROLL_DOWN)
        say("Folyamatos olvasás.")
        readNextContinuous()
    }

    private fun readNextContinuous() {
        if (!continuousReading) return
        val node = filtered.getOrNull(index)
        if (node == null) {
            stopContinuousReading()
            say("A képernyő végére értem.")
            return
        }
        val text = ScreenReaderNavigator.describe(node)
        lastSpoken = text
        tts?.speakThen(text) {
            if (!continuousReading) return@speakThen
            if (index >= filtered.lastIndex) {
                stopContinuousReading()
                tts?.speak("A képernyő végére értem.")
            } else {
                index++
                readNextContinuous()
            }
        }
    }

    private fun stopContinuousReading() {
        if (!continuousReading) return
        continuousReading = false
        android.util.Log.i(ScreenReaderPrefs.TAG, "folyamatos olvasas megallitva")
    }

    /** "Hol vagyok?" — alkalmazás, mód, pozíció egy mozdulattal. */
    fun whereAmI() {
        stopContinuousReading()
        ensureNodes()
        val app = currentPackage?.let { appLabelOf(it) } ?: "ismeretlen alkalmazás"
        val position = if (filtered.isEmpty()) {
            "nincs felolvasható elem"
        } else {
            "${index + 1}. elem a ${filtered.size}-ből, ${positionPercent()} százaléknál"
        }
        sounds?.play(ScreenReaderSounds.Sound.HOME)
        say("$app. Mód: ${mode.label}. Olvasás: ${granularity.label}. $position.")
    }

    /** Az utolsó kimondott szöveg megismétlése — ha nem értetted. */
    fun repeatLast() {
        stopContinuousReading()
        if (lastSpoken.isBlank()) {
            say("Nincs mit megismételni.")
        } else {
            sounds?.play(ScreenReaderSounds.Sound.PREV)
            tts?.speak(lastSpoken)
        }
    }

    /**
     * KERESÉS A KÉPERNYŐN — kimondod, mit keresel, és odaugrik.
     *
     * Hosszú listákban (névjegyek, beállítások, weboldal) sokkal gyorsabb, mint
     * végiglépkedni. A SuperDL saját hangbevitelét használja.
     */
    fun searchByVoice() {
        stopContinuousReading()
        val vi = voiceInput ?: run {
            say("A keresés most nem érhető el.")
            return
        }
        if (!vi.isAvailable()) {
            say("A hangfelismerés nem érhető el ezen a készüléken.")
            return
        }
        sounds?.play(ScreenReaderSounds.Sound.FIELD)
        vi.listenPrompt(
            prompt = "Mit keresel a képernyőn?",
            onResult = { text -> jumpToText(text) },
            onError = {
                sounds?.play(ScreenReaderSounds.Sound.ERROR)
                say("Nem értettem.")
            }
        )
    }

    /** Az első olyan elemre ugrik, ami tartalmazza a keresett szöveget. */
    private fun jumpToText(query: String) {
        val needle = query.trim().lowercase()
        if (needle.isBlank()) {
            say("Nem értettem, mit keresel.")
            return
        }
        // A kereséshez a TELJES listát nézzük, ne csak a szűrt módot — különben
        // a találat "eltűnne", ha épp gomb-módban vagy.
        nodesStale = true
        ensureNodes()
        val target = nodes.indexOfFirst {
            ScreenReaderNavigator.labelOf(it)?.lowercase()?.contains(needle) == true
        }
        if (target < 0) {
            sounds?.play(ScreenReaderSounds.Sound.ERROR)
            say("Nincs találat erre: $query.")
            return
        }
        // Ha a találat nem szerepel az aktuális módban, visszaváltunk MINDEN
        // elemre — így a felhasználó biztosan eljut hozzá.
        val node = nodes[target]
        if (!ScreenReaderFilter.matches(node, mode)) {
            mode = NavigationMode.ALL
            applyFilter()
            tts?.speak("Váltás minden elemre.")
        }
        index = filtered.indexOf(node).coerceAtLeast(0)
        lastLabel = ScreenReaderNavigator.labelOf(node)
        prepareSegments(node, fromEnd = false)
        sounds?.play(ScreenReaderSounds.Sound.FIRST)
        say("Találat: ${ScreenReaderNavigator.describe(node)}")
    }

    /**
     * KÉPFELOLVASÁS: mi van a kiválasztott képen?
     * A telefon lefényképezi a képernyőt, kivágja az elemet, és HELYBEN
     * elolvassa a rajta lévő szöveget — a kép nem megy sehova.
     */
    fun readImageAtCursor() {
        stopContinuousReading()
        val reader = imageReader
        if (reader == null || !reader.isAvailable()) {
            say("A képfelolvasás ezen a rendszeren nem érhető el.")
            return
        }
        ensureNodes()
        val node = filtered.getOrNull(index)
        sounds?.play(ScreenReaderSounds.Sound.FIELD)
        say("Kép olvasása.")
        reader.readImage(node) { text ->
            handler.post {
                if (text.isNullOrBlank()) {
                    sounds?.play(ScreenReaderSounds.Sound.EDGE)
                    say("Ezen a képen nincs olvasható szöveg.")
                } else {
                    sounds?.play(ScreenReaderSounds.Sound.ACTIVATE)
                    say("A képen ez olvasható: $text")
                }
            }
        }
    }

    /**
     * SAJÁT ELNEVEZÉS: a névtelen gomb elnevezése, hogy legközelebb tudd, mi az.
     * Kimondod a nevet, és a program megjegyzi — alkalmazásonként külön.
     */
    fun labelCurrentElement() {
        stopContinuousReading()
        ensureNodes()
        val node = filtered.getOrNull(index)
        if (node == null) {
            say("Nincs kiválasztott elem.")
            return
        }
        val vi = voiceInput
        if (vi == null || !vi.isAvailable()) {
            say("Az elnevezéshez hangfelismerés kell, ami most nem érhető el.")
            return
        }
        val pkg = currentPackage ?: return
        val existing = ScreenReaderLabels.labelFor(this, node, pkg)
        sounds?.play(ScreenReaderSounds.Sound.FIELD)
        vi.listenPrompt(
            prompt = if (existing != null) {
                "Jelenlegi neve: $existing. Mondd az új nevet."
            } else {
                "Mondd, minek nevezzem ezt az elemet."
            },
            onResult = { spoken ->
                handler.post {
                    val name = spoken.trim()
                    if (name.isBlank()) {
                        say("Nem értettem.")
                    } else if (ScreenReaderLabels.setLabel(this, node, pkg, name)) {
                        sounds?.play(ScreenReaderSounds.Sound.ACTIVATE)
                        say("Elmentve: $name. Mostantól így fogom nevezni.")
                        nodesStale = true
                    } else {
                        say("Ezt az elemet nem tudom megjegyezni.")
                    }
                }
            },
            onError = {
                handler.post {
                    sounds?.play(ScreenReaderSounds.Sound.ERROR)
                    say("Nem sikerült az elnevezés.")
                }
            }
        )
    }

    /**
     * SZÍNFELISMERÉS: milyen színű a kurzor alatti elem?
     * A hibaüzenet piros, a siker zöld, az inaktív szürke — ez az információ
     * eddig teljesen rejtve maradt.
     */
    fun readColorsAtCursor() {
        stopContinuousReading()
        val reader = imageReader
        if (reader == null || !reader.isAvailable()) {
            say("A színfelismerés ezen a rendszeren nem érhető el.")
            return
        }
        ensureNodes()
        val node = filtered.getOrNull(index)
        sounds?.play(ScreenReaderSounds.Sound.FIELD)
        reader.sampleColors(node) { reading ->
            handler.post {
                if (reading == null) {
                    sounds?.play(ScreenReaderSounds.Sound.ERROR)
                    say("A színt nem sikerült megállapítani.")
                } else {
                    sounds?.play(ScreenReaderSounds.Sound.ACTIVATE)
                    say(reading.speak())
                }
            }
        }
    }

    /**
     * TÁBLÁZAT-NAVIGÁCIÓ: mozgás sor vagy oszlop szerint.
     * Egy tíz oszlopos táblázatban a soronkénti lépkedés használhatatlan lenne.
     */
    fun moveInGrid(byRow: Boolean, forward: Boolean) {
        stopContinuousReading()
        ensureNodes()
        val current = filtered.getOrNull(index)
        if (current == null) {
            say("Nincs kiválasztott elem.")
            return
        }
        if (!ScreenReaderTable.isInGrid(current)) {
            sounds?.play(ScreenReaderSounds.Sound.EDGE)
            say("Ez a tartalom nem táblázat, itt a szokásos mozgás használható.")
            return
        }
        val target = ScreenReaderTable.findNeighbour(filtered, current, byRow, forward)
        if (target < 0) {
            sounds?.play(ScreenReaderSounds.Sound.EDGE)
            say(
                when {
                    byRow && forward -> "Ez az utolsó sor."
                    byRow -> "Ez az első sor."
                    forward -> "Ez az utolsó oszlop."
                    else -> "Ez az első oszlop."
                }
            )
            return
        }
        index = target
        val node = filtered[index]
        lastLabel = ScreenReaderNavigator.labelOf(node)
        prepareSegments(node, fromEnd = false)
        sounds?.play(ScreenReaderSounds.Sound.NEXT)
        say("${describeWithCustomLabel(node)}. ${ScreenReaderTable.speakPosition(node)}")
    }

    /**
     * HOL TARTUNK a listában, 0.0-tól 1.0-ig — a helyzetjelző hang magasságához.
     *
     * FONTOS: elsősorban a VALÓDI lista-pozíciót használjuk (hányadik sor a
     * hányból), nem a képernyőn látható elemek sorrendjét. Egy 200 elemű
     * listából ugyanis egyszerre csak tíz látszik — a látható sorrend alapján
     * a hang végig ugyanazt mutatná, és semmit nem érne.
     */
    private fun positionRatio(): Float {
        val node = filtered.getOrNull(index)
        if (node != null) {
            try {
                val item = node.collectionItemInfo
                val total = ScreenReaderTable.gridSizeOf(node)?.first ?: 0
                if (item != null && total > 1) {
                    return (item.rowIndex.toFloat() / (total - 1)).coerceIn(0f, 1f)
                }
            } catch (_: Exception) {
            }
        }
        // Tartalék: a képernyőn látható elemek szerinti helyzet.
        if (filtered.size <= 1) return 0f
        return index.toFloat() / (filtered.size - 1)
    }

    /** Az aktuális pozíció százalékban, felolvasáshoz. */
    private fun positionPercent(): Int = (positionRatio() * 100).toInt()

    private fun ensureNodes() {
        // Csak akkor olvasunk újra, ha üres a lista VAGY jelezték, hogy elavult.
        if (nodes.isNotEmpty() && !nodesStale) return
        val previousLabel = lastLabel
        clearNodes()
        val root = try {
            rootInActiveWindow
        } catch (_: Exception) {
            null
        }
        nodes = ScreenReaderNavigator.collectNodes(root)
        nodesStale = false
        applyFilter()

        // POZÍCIÓ VISSZAKERESÉSE: a képernyő apró változásai (óra, töltésjelző)
        // után ugyanazon az elemen maradjunk, ne ugorjunk a lista elejére.
        if (previousLabel != null && filtered.isNotEmpty()) {
            val found = filtered.indexOfFirst {
                ScreenReaderNavigator.labelOf(it) == previousLabel
            }
            if (found >= 0) {
                index = found
                return
            }
        }
        index = index.coerceIn(0, (filtered.size - 1).coerceAtLeast(0))
    }

    /** A módra szűrt lista előállítása a teljes elemlistából. */
    private fun applyFilter() {
        filtered = if (mode == NavigationMode.ALL) {
            nodes
        } else {
            nodes.filter { ScreenReaderFilter.matches(it, mode) }
        }
    }

    /**
     * Kimondás ÉS megjegyzés — az utolsó mondat így bármikor megismételhető.
     */
    private fun say(text: String) {
        lastSpoken = text
        tts?.speak(text)
    }

    /**
     * Az elemlista ürítése — a rendszer-objektumokat EL KELL ENGEDNI.
     *
     * Enélkül minden képernyőváltásnál ottmaradtak a régi elemek a memóriában
     * (300 elem képernyőnként), ami hosszú használat mellett lassuláshoz
     * vezetett volna.
     */
    private fun clearNodes() {
        if (nodes.isEmpty()) return
        ScreenReaderNavigator.recycleAll(nodes)
        nodes = emptyList()
    }

    private fun move(delta: Int) {
        stopContinuousReading()
        ensureNodes()
        if (filtered.isEmpty()) {
            sounds?.play(ScreenReaderSounds.Sound.EDGE)
            say(
                if (mode == NavigationMode.ALL) "Nincs felolvasható elem ezen a képernyőn."
                else "Ebben a módban nincs elem: ${mode.label}."
            )
            return
        }

        // RÉSZLETESSÉG: ha nem elem-szinten olvasunk, előbb a jelenlegi elem
        // szövegén belül lépkedünk, és csak a végén megyünk tovább.
        if (granularity != ReadingGranularity.ELEMENT && segments.isNotEmpty()) {
            val nextSeg = segmentIndex + delta
            if (nextSeg in segments.indices) {
                segmentIndex = nextSeg
                speakSegment()
                return
            }
            // A szöveg végére (vagy elejére) értünk: jöhet a következő elem.
        }

        index = (index + delta + filtered.size) % filtered.size
        val node = filtered[index]

        // Ha az elem közben eltűnt (az alkalmazás átrajzolta a képernyőt),
        // frissen olvassuk be a listát, és onnan lépünk tovább.
        if (!ScreenReaderNavigator.refresh(node)) {
            nodesStale = true
            ensureNodes()
            if (filtered.isEmpty()) {
                sounds?.play(ScreenReaderSounds.Sound.EDGE)
                say("A képernyő megváltozott, nincs felolvasható elem.")
                return
            }
            index = index.coerceIn(0, filtered.lastIndex)
        }

        sounds?.playAtPosition(
            if (delta > 0) ScreenReaderSounds.Sound.NEXT else ScreenReaderSounds.Sound.PREV,
            positionRatio()
        )
        val current = filtered[index]
        lastLabel = ScreenReaderNavigator.labelOf(current)
        prepareSegments(current, fromEnd = delta < 0)

        if (granularity == ReadingGranularity.ELEMENT || segments.size <= 1) {
            val counter = if (ScreenReaderPrefs.isSpeakCounter(this)) {
                ". ${index + 1} / ${filtered.size}"
            } else ""
            say("${describeWithCustomLabel(current)}$counter")
        } else {
            speakSegment()
        }
        ScreenReaderPrefs.reportSuccess(this)
    }

    /**
     * Az elem leírása, a SAJÁT ELNEVEZÉST előnyben részesítve.
     * Ha egyszer elnevezted, az a név a legjobb — jobb, mint bármi, amit a
     * program kitalálhatna.
     */
    private fun describeWithCustomLabel(node: AccessibilityNodeInfo): String {
        val pkg = currentPackage
        if (pkg != null) {
            ScreenReaderLabels.labelFor(this, node, pkg)?.let { custom ->
                val extra = if (node.isCheckable) {
                    if (node.isChecked) ", bekapcsolva" else ", kikapcsolva"
                } else ""
                return "$custom$extra"
            }
        }
        return ScreenReaderNavigator.describe(node)
    }

    /** Az aktuális elem szövegének felbontása a kért részletességre. */
    private fun prepareSegments(node: AccessibilityNodeInfo, fromEnd: Boolean) {
        val text = ScreenReaderNavigator.labelOf(node).orEmpty()
        segments = ScreenReaderFilter.segments(text, granularity)
        segmentIndex = if (fromEnd && segments.isNotEmpty()) segments.lastIndex else 0
    }

    /** A szöveg aktuális darabjának kimondása. */
    private fun speakSegment() {
        val seg = segments.getOrNull(segmentIndex) ?: return
        sounds?.play(ScreenReaderSounds.Sound.NEXT)
        val spoken = if (granularity == ReadingGranularity.CHARACTER) {
            ScreenReaderFilter.speakCharacter(seg, ScreenReaderPrefs.isPhonetic(this))
        } else {
            seg
        }
        say(spoken)
    }

    private fun activateCurrent() {
        stopContinuousReading()
        ensureNodes()
        val node = filtered.getOrNull(index)
        if (node == null) {
            sounds?.play(ScreenReaderSounds.Sound.ERROR)
            tts?.speak("Nincs kiválasztott elem.")
            return
        }
        // SZÖVEGMEZŐ: nem "megnyomni" kell, hanem beleállni — ilyenkor jön elő a
        // billentyűzet, amivel be lehet írni (a rendszer hangbevitele is onnan
        // érhető el). A jelenlegi tartalmat felolvassuk, hogy tudd, mi van benne.
        if (node.isEditable) {
            val focused = try {
                node.performAction(AccessibilityNodeInfo.ACTION_FOCUS) ||
                    node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            } catch (_: Exception) {
                false
            }
            if (focused) {
                sounds?.play(ScreenReaderSounds.Sound.FIELD)
                tts?.speak("Szövegmező kiválasztva. ${ScreenReaderNavigator.describeFieldContent(node)}")
            } else {
                sounds?.play(ScreenReaderSounds.Sound.ERROR)
                tts?.speak("A szövegmező nem választható ki.")
            }
            return
        }

        val ok = ScreenReaderNavigator.activate(node)
        if (ok) {
            sounds?.play(ScreenReaderSounds.Sound.ACTIVATE)
        } else {
            sounds?.play(ScreenReaderSounds.Sound.ERROR)
            tts?.speak("Ez az elem nem nyomható meg.")
        }
        // Aktiválás után a képernyő valószínűleg változik — és a pozíció is
        // értelmét veszti, hiszen új tartalom jön.
        clearNodes()
        lastLabel = null
    }

    override fun onInterrupt() {
        // A rendszer megszakította a felolvasást.
    }

    override fun onDestroy() {
        setTouchExploration(false)
        handler.removeCallbacksAndMessages(null)
        clearNodes()
        try {
            sounds?.release()
        } catch (_: Exception) {
        }
        sounds = null
        try {
            imageReader?.release()
        } catch (_: Exception) {
        }
        imageReader = null
        try {
            tts?.shutdown()
        } catch (_: Exception) {
        }
        tts = null
        super.onDestroy()
    }
}
