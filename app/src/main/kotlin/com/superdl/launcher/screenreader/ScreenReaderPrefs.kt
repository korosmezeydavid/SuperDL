package com.superdl.launcher.screenreader

import android.content.Context

/**
 * A SuperDL képernyőolvasó beállításai és BIZTONSÁGI RETESZE.
 *
 * A képernyőolvasó a telefon egészének érintés-kezelését befolyásolja, ezért
 * kell egy hely, ahonnan EGY MOZDULATTAL leállítható, ha bármi rosszul sülne el.
 *
 * Három szint van:
 *  1. enabled          — a felhasználó ki/be kapcsolója (menüből)
 *  2. emergencyDisable — VÉSZLEÁLLÍTÁS: ha ez be van kapcsolva, a szolgáltatás
 *                        semmit nem csinál, akkor sem, ha a rendszerben
 *                        engedélyezve van.
 *  3. failureCount     — hibaszámláló: több egymást követő hiba után magától
 *                        vészleállítás lép életbe.
 */
object ScreenReaderPrefs {

    const val TAG = "SDL_SCREENREADER"

    private const val PREFS = "superdl_screenreader"
    private const val KEY_ENABLED = "enabled"
    private const val KEY_EMERGENCY = "emergency_disable"
    private const val KEY_FAILURES = "failure_count"

    /** Ennyi egymást követő hiba után magától leáll. */
    private const val MAX_FAILURES = 3

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    // ── Fő kapcsoló ─────────────────────────────────────────────────────────

    fun isEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_ENABLED, false) && !isEmergencyDisabled(context)

    fun setEnabled(context: Context, on: Boolean) {
        prefs(context).edit().putBoolean(KEY_ENABLED, on).apply()
        // Kézi bekapcsoláskor a vészleállítást és a hibaszámlálót nullázzuk:
        // a felhasználó tudatosan újra megpróbálja.
        if (on) clearEmergency(context)
    }

    // ── Vészleállítás (a "biztonsági retesz") ───────────────────────────────

    fun isEmergencyDisabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_EMERGENCY, false)

    /**
     * Azonnali leállítás. Ezt hívja a menü vészkapcsolója, és ezt hívja a
     * szolgáltatás is, ha sorozatos hibába fut.
     */
    fun emergencyStop(context: Context, reason: String) {
        android.util.Log.w(TAG, "VESZLEALLITAS: $reason")
        prefs(context).edit()
            .putBoolean(KEY_EMERGENCY, true)
            .putBoolean(KEY_ENABLED, false)
            .apply()
    }

    fun clearEmergency(context: Context) {
        prefs(context).edit()
            .putBoolean(KEY_EMERGENCY, false)
            .putInt(KEY_FAILURES, 0)
            .apply()
    }

    // ── Hibaszámláló ────────────────────────────────────────────────────────

    /** Hiba történt. Ha túl sok egymás után, magától vészleállítás jön. */
    fun reportFailure(context: Context, reason: String) {
        val next = prefs(context).getInt(KEY_FAILURES, 0) + 1
        prefs(context).edit().putInt(KEY_FAILURES, next).apply()
        android.util.Log.w(TAG, "Hiba ($next/$MAX_FAILURES): $reason")
        if (next >= MAX_FAILURES) {
            emergencyStop(context, "tul sok egymast koveto hiba")
        }
    }

    /** Sikeres működés — a hibaszámláló nullázódik. */
    fun reportSuccess(context: Context) {
        if (prefs(context).getInt(KEY_FAILURES, 0) != 0) {
            prefs(context).edit().putInt(KEY_FAILURES, 0).apply()
        }
    }

    fun speakStatus(context: Context): String = when {
        isEmergencyDisabled(context) ->
            "A képernyőolvasó vészleállítás alatt van. A bekapcsolással újraindíthatod."
        prefs(context).getBoolean(KEY_ENABLED, false) ->
            "A képernyőolvasó bekapcsolva. Csak külső alkalmazásokban működik."
        else ->
            "A képernyőolvasó kikapcsolva."
    }

    // ── OLVASÁSI BEÁLLÍTÁSOK ────────────────────────────────────────────────

    private const val KEY_COUNTER = "speak_counter"
    private const val KEY_PHONETIC = "phonetic_alphabet"

    /**
     * Bemondja-e a pozíciót ("3 / 47") minden elemnél.
     * Tanuláskor hasznos, gyakorlott használatnál viszont lassít — ezért
     * kikapcsolható.
     */
    fun isSpeakCounter(context: Context): Boolean =
        prefs(context).getBoolean(KEY_COUNTER, true)

    fun toggleSpeakCounter(context: Context): Boolean {
        val next = !isSpeakCounter(context)
        prefs(context).edit().putBoolean(KEY_COUNTER, next).apply()
        return next
    }

    /**
     * Betűnkénti olvasásnál a betűző ábécét használja ("Aladár, Béla, Cecil").
     * Kódoknál, rendszámoknál életmentő, egyébként lassít — ezért választható.
     */
    fun isPhonetic(context: Context): Boolean =
        prefs(context).getBoolean(KEY_PHONETIC, false)

    fun togglePhonetic(context: Context): Boolean {
        val next = !isPhonetic(context)
        prefs(context).edit().putBoolean(KEY_PHONETIC, next).apply()
        return next
    }

    // ── ALKALMAZÁSONKÉNT MEGJEGYZETT BEÁLLÍTÁS ──────────────────────────────

    /**
     * Minden alkalmazáshoz KÜLÖN megjegyezzük, milyen módban és milyen
     * részletességgel olvastál benne utoljára.
     *
     * MIÉRT HASZNOS: a böngészőben jellemzően "címsorok" módban akarsz
     * tájékozódni, a beállításokban "minden elem", egy üzenetküldőben pedig
     * "szöveg". Enélkül minden belépéskor újra át kellene állítanod.
     */
    fun saveAppMode(context: Context, packageName: String, mode: String, granularity: String) {
        prefs(context).edit()
            .putString("mode_$packageName", mode)
            .putString("gran_$packageName", granularity)
            .apply()
    }

    fun loadAppMode(context: Context, packageName: String): Pair<String?, String?> {
        val p = prefs(context)
        return p.getString("mode_$packageName", null) to p.getString("gran_$packageName", null)
    }

    // ── AUTOMATIKUS FELOLVASÁS ÚJ KÉPERNYŐNÉL ──────────────────────────────

    private const val KEY_AUTO_READ = "auto_read_screen"

    /**
     * Új képernyőre lépve magától elmondja a képernyő címét és az első pár
     * elemet — így nem kell "vakon" tapogatózni, hogy hova kerültél.
     */
    fun isAutoRead(context: Context): Boolean =
        prefs(context).getBoolean(KEY_AUTO_READ, true)

    fun toggleAutoRead(context: Context): Boolean {
        val next = !isAutoRead(context)
        prefs(context).edit().putBoolean(KEY_AUTO_READ, next).apply()
        return next
    }
}
