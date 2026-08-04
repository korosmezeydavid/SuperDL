package com.superdl.launcher.keyboard

import android.inputmethodservice.InputMethodService
import android.view.View
import com.superdl.launcher.tts.TtsManager

/**
 * SUPERDL MÁTRIX BILLENTYŰZET — egyujjas, telefonszám-elrendezésű bevitel.
 *
 * MIÉRT LÉTEZIK: a Braille-bevitelhez hat egyidejű érintés kell, amit nem
 * minden készülék bír megbízhatóan (olcsóbb kijelzők összevonhatják a közeli
 * érintéseket, és van, ahol korlátozott az egyidejű érintések száma).
 * Ez a billentyűzet EGYETLEN ujjal működik, tehát ott is használható.
 *
 * RÁADÁS: nem kell hozzá Braille-tudás. Aki valaha nyomógombos telefonon írt,
 * annak azonnal ismerős.
 *
 * HASZNÁLAT:
 *   1. Tedd le az ujjad bárhová — oda kerül a mátrix közepe (5-ös).
 *   2. Csúsztasd a kívánt gomb felé — bemondja a gombot, majd pörgeti a betűit.
 *   3. Engedd fel — az éppen hallott betű íródik be.
 *   4. Meggondolhatod magad: felengedés előtt átcsúszhatsz másik gombra.
 */
class MatrixKeyboardService : InputMethodService(), MatrixKeypadView.Listener {

    private var tts: TtsManager? = null
    private var sounds: com.superdl.launcher.screenreader.ScreenReaderSounds? = null
    private var voiceInput: com.superdl.launcher.voice.VoiceInput? = null
    private var view: MatrixKeypadView? = null

    /** Nagybetű-mód: a következő beírt betű nagy lesz. */
    private var shiftOnce = false
    /** Tartós nagybetű (a módváltó kétszeri használatával). */
    private var shiftLock = false

    override fun onCreateInputView(): View {
        tts = try {
            TtsManager(this)
        } catch (_: Exception) {
            null
        }
        sounds = try {
            com.superdl.launcher.screenreader.ScreenReaderSounds(this)
        } catch (_: Exception) {
            null
        }
        voiceInput = try {
            com.superdl.launcher.voice.VoiceInput(this)
        } catch (_: Exception) {
            null
        }
        return MatrixKeypadView(this, this).also { view = it }
    }

    override fun onStartInputView(info: android.view.inputmethod.EditorInfo?, restarting: Boolean) {
        super.onStartInputView(info, restarting)
        if (!restarting) {
            tts?.speak(
                "Mátrix billentyűzet. Tedd le az ujjad, csúsztasd a betű felé, " +
                    "és engedd fel a beíráshoz."
            )
        }
    }

    // ── A billentyűzet visszajelzései ───────────────────────────────────────

    override fun onCalibrated() {
        sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.ON)
    }

    override fun onKeyEntered(key: MatrixKey) {
        // SZÖVEGTÁR MÓDBAN a gomb TARTALMÁT mondjuk be, nem a betűit — így
        // csúsztatás közben hallod, melyik helyen mi van.
        if (view?.textBankMode == true) {
            sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.NEXT)
            tts?.speak(MatrixTextBank.speakPreview(this, key))
            return
        }
        // A gomb nevét NEM mondjuk ki külön: rögtön a karakterek jönnek, mert
        // gyors gépelésnél a gombnév csak lassítana. A rövid hang elég jelzés.
        sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.NEXT)
    }

    /**
     * SZÖVEGTÁR: a kiválasztott helyre engedték fel az ujjat.
     * Ha van rajta szöveg, BEÍRJUK. Ha üres, felajánljuk a feltöltést
     * diktálással — így egy mozdulattal fel is tölthető.
     */
    override fun onTextBankKeyReleased(slot: MatrixKey) {
        val saved = MatrixTextBank.get(this, slot)
        if (saved != null) {
            commitDictated(saved)
            // Beillesztés után visszatérünk a normál íráshoz.
            view?.setTextBank(false)
            tts?.speakAdd("Vissza a betűkhöz.")
            return
        }
        // ÜRES HELY: felajánljuk a feltöltést.
        val vi = voiceInput
        if (vi == null || !vi.isAvailable()) {
            tts?.speak("Ez a hely üres, és a hangfelismerés most nem érhető el.")
            return
        }
        sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.FIELD)
        vi.listenPrompt(
            prompt = "${slot.label}: üres. Mondd a szöveget, amit ide mentsek.",
            onResult = { raw ->
                val text = com.superdl.launcher.voice.SpeechPunctuation.apply(raw)
                if (text.isBlank()) {
                    tts?.speak("Nem értettem.")
                } else {
                    MatrixTextBank.set(this, slot, text)
                    sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.ACTIVATE)
                    tts?.speak("Elmentve a ${slot.label} helyre: $text")
                }
            },
            onError = {
                sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.ERROR)
                tts?.speak("Nem sikerült a mentés.")
            }
        )
    }

    override fun onCharCycled(ch: Char) {
        // A pörgetés közben KIMONDJUK az aktuális karaktert — ebből tudja a
        // felhasználó, mikor engedje fel az ujját.
        tts?.speak(speakChar(ch))
    }

    override fun onCharCommitted(ch: Char) {
        val out = applyShift(ch)
        currentInputConnection?.commitText(out.toString(), 1)
        sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.ACTIVATE)
        if (MatrixKeyboardPrefs.isSpeakChars(this)) {
            tts?.speak(speakChar(out))
        }
        // Az egyszeri nagybetű elhasználódott.
        if (shiftOnce) shiftOnce = false
    }

    override fun onReleasedWithoutChar() {
        sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.EDGE)
    }

    /** A kettőskereszt: nagybetű-mód váltása (egyszeri / tartós / ki). */
    override fun onModeKeyReleased() {
        when {
            !shiftOnce && !shiftLock -> {
                shiftOnce = true
                tts?.speak("Nagybetű a következő betűre.")
            }
            shiftOnce && !shiftLock -> {
                shiftOnce = false
                shiftLock = true
                tts?.speak("Tartós nagybetű.")
            }
            else -> {
                shiftLock = false
                tts?.speak("Kisbetű.")
            }
        }
        sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.LONG_PRESS)
    }

    /** Két ujjas parancsok — ezek nem keverednek az egyujjas írással. */
    override fun onTwoFingerGesture(gesture: MatrixKeypadView.Gesture) {
        when (gesture) {
            MatrixKeypadView.Gesture.BACKSPACE -> {
                currentInputConnection?.deleteSurroundingText(1, 0)
                sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.BACK)
                tts?.speak("törölve")
            }
            MatrixKeypadView.Gesture.ENTER -> {
                currentInputConnection?.commitText("\n", 1)
                sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.ACTIVATE)
                tts?.speak("új sor")
            }
            MatrixKeypadView.Gesture.CLOSE -> {
                sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.OFF)
                tts?.speak("Billentyűzet bezárva.")
                requestHideSelf(0)
            }
            MatrixKeypadView.Gesture.HELP -> {
                tts?.speak(speakGestureHelp())
            }
            MatrixKeypadView.Gesture.DICTATE -> startDictation()
            MatrixKeypadView.Gesture.SWITCH_KEYBOARD -> showKeyboardPicker()
            MatrixKeypadView.Gesture.TEXT_BANK -> toggleTextBank()
        }
    }

    /** A szövegtár be- és kikapcsolása. */
    private fun toggleTextBank() {
        val v = view ?: return
        val on = !v.textBankMode
        v.setTextBank(on)
        sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.RECENTS)
        if (on) {
            val count = MatrixTextBank.count(this)
            tts?.speak(
                if (count == 0) {
                    "Szövegtár. Még üres. Csúsztass egy helyre és engedd fel — ott mondhatod be, mit mentsek oda."
                } else {
                    "Szövegtár. $count mentett szöveg. Csúsztass a helyekre, és engedd fel a beillesztéshez."
                }
            )
        } else {
            tts?.speak("Vissza a betűkhöz.")
        }
    }

    /**
     * A rendszer billentyűzet-választója.
     * Három ujjal hívható — így bármikor átválthatsz másik billentyűzetre
     * (pl. a megszokott Gboardra), ha épp az kényelmesebb.
     */
    private fun showKeyboardPicker() {
        try {
            sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.RECENTS)
            tts?.speak("Billentyűzet választása.")
            val imm = getSystemService(INPUT_METHOD_SERVICE)
                as android.view.inputmethod.InputMethodManager
            imm.showInputMethodPicker()
        } catch (e: Exception) {
            tts?.speak("A választó nem nyitható meg.")
        }
    }

    /**
     * DIKTÁLÁS a billentyűzetből.
     *
     * A SuperDL saját hangbevitelét használja — azt, amelyik a KÖZPONTOZÁST is
     * érti ("pont", "vessző", "kérdőjel"), és a magyar felismerési hibákat is
     * javítja. Így a billentyűzet nemcsak betűnként, hanem egész mondatokkal is
     * használható.
     */
    private fun startDictation() {
        val vi = voiceInput ?: run {
            tts?.speak("A diktálás most nem érhető el.")
            return
        }
        if (!vi.isAvailable()) {
            tts?.speak("A hangfelismerés nem érhető el ezen a készüléken.")
            return
        }
        sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.FIELD)
        vi.listenPrompt(
            prompt = "Mondd a szöveget.",
            onResult = { raw ->
                // KÖZPONTOZÁS: a nyers felismerés a "vessző" szót BEÍRJA szóként.
                // A SuperDL saját feldolgozása alakítja át valódi írásjellé,
                // rendezi a szóközöket, és nagybetűvel kezdi a mondatokat.
                val text = com.superdl.launcher.voice.SpeechPunctuation.apply(raw)
                if (text.isBlank()) {
                    tts?.speak("Nem értettem.")
                } else {
                    commitDictated(text)
                }
            },
            onError = {
                sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.ERROR)
                tts?.speak("A diktálás nem sikerült.")
            }
        )
    }

    /**
     * A diktált szöveg beírása, a KÖRNYEZETHEZ IGAZÍTVA.
     *
     * Ha már van szöveg a mezőben, és nem szóközzel vagy sortöréssel végződik,
     * automatikusan teszünk elé szóközt — így a diktált részek nem tapadnak
     * össze. Írásjellel kezdődő szöveg elé viszont nem kell szóköz.
     */
    private fun commitDictated(text: String) {
        val ic = currentInputConnection
        val before = ic?.getTextBeforeCursor(1, 0)?.toString().orEmpty()
        val needsSpace = before.isNotEmpty() &&
            !before.last().isWhitespace() &&
            text.firstOrNull()?.isLetterOrDigit() == true
        ic?.commitText(if (needsSpace) " $text" else text, 1)
        sounds?.play(com.superdl.launcher.screenreader.ScreenReaderSounds.Sound.ACTIVATE)
        tts?.speak("Beírva: $text")
    }

    companion object {
        /**
         * A mátrix billentyűzet mozdulatai — felolvasható súgó.
         * A billentyűzetből két ujjal felfelé söpörve is lekérhető, és a
         * menüből is elérhető, hogy meg lehessen tanulni.
         */
        fun speakGestureHelp(): String = listOf(
            "Mátrix billentyűzet mozdulatai.",
            "Egy ujjal: tedd le bárhová, ott lesz az ötös gomb.",
            "Csúsztasd a kívánt gomb felé, és hallgasd a betűket.",
            "Engedd fel, amikor a kívánt betűt hallod.",
            "Két ujjal balra: törlés. Két ujjal jobbra: új sor.",
            "Csípő mozdulat: a billentyűzet bezárása.",
            "SZÉTHÚZÓ mozdulat: diktálás — mondhatsz egész mondatot, írásjelekkel.",
            "HÁROM ujjal: billentyűzet választása (váltás másikra).",
            "Két ujjal HÁRMAS KOPPINTÁS: SZÖVEGTÁR — előre elmentett szövegek. " +
                "Csúsztass egy helyre és engedd fel: beilleszti. Üres helynél " +
                "bemondhatod, mit mentsen oda.",
            "Két ujjal felfelé: ez a súgó."
        ).joinToString(" ")
    }

    // ── Segédek ─────────────────────────────────────────────────────────────

    private fun applyShift(ch: Char): Char =
        if ((shiftOnce || shiftLock) && ch.isLetter()) ch.uppercaseChar() else ch

    /**
     * A karakter felolvasható alakja. A szóközt és az írásjeleket néven
     * mondjuk, különben a beszélő elnyelné őket.
     */
    private fun speakChar(ch: Char): String = when (ch) {
        ' ' -> "szóköz"
        '.' -> "pont"
        ',' -> "vessző"
        '?' -> "kérdőjel"
        '!' -> "felkiáltójel"
        '-' -> "kötőjel"
        ':' -> "kettőspont"
        ';' -> "pontosvessző"
        '(' -> "nyitó zárójel"
        ')' -> "csukó zárójel"
        '"' -> "idézőjel"
        '\'' -> "aposztróf"
        else -> ch.toString()
    }

    override fun onDestroy() {
        try {
            sounds?.release()
        } catch (_: Exception) {
        }
        sounds = null
        try {
            tts?.shutdown()
        } catch (_: Exception) {
        }
        tts = null
        super.onDestroy()
    }
}
