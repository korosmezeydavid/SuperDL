package com.superdl.launcher.screenreader

import android.content.Context
import android.media.AudioAttributes
import android.media.SoundPool
import com.superdl.launcher.R

/**
 * A képernyőolvasó HANGVISSZAJELZÉSEI.
 *
 * Minden művelethez tartozik egy rövid, jellegzetes hang, hogy a felhasználó
 * FÜLLEL is kövesse, mi történik — ne csak a felolvasott szövegből.
 *
 * MIÉRT SOUNDPOOL: a rövid hangokat előre betölti a memóriába, és késleltetés
 * nélkül szólaltatja meg. A MediaPlayer minden lejátszásnál újra megnyitná a
 * fájlt, ami a gyors navigálásnál érezhetően késne.
 *
 * A hangok hossza szándékosan a művelet gyakoriságához igazodik: a legtöbbször
 * használt lépkedés kapja a legrövidebb koppanást (55 ms), az állapotváltozás
 * (be- és kikapcsolás) a hosszabb, jellegzetesebb hangot.
 */
class ScreenReaderSounds(context: Context) {

    private val pool: SoundPool = SoundPool.Builder()
        .setMaxStreams(4)
        .setAudioAttributes(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build()
        )
        .build()

    private val ids = mutableMapOf<Sound, Int>()

    /**
     * Hány hang töltődött be eddig. A betöltés ASZINKRON: a szolgáltatás
     * indulása után pár tizedmásodperccel készül el. Enélkül az első néhány
     * hang némán elmaradna, mert még nincs a memóriában.
     */
    private var loadedCount = 0
    private val ready: Boolean get() = loadedCount > 0

    enum class Sound {
        NEXT,           // következő elem
        PREV,           // előző elem
        EDGE,           // lista széle, nincs több
        ERROR,          // nem nyomható meg, hiba
        BACK,           // vissza
        SCROLL_UP,      // görgetés felfelé
        SCROLL_DOWN,    // görgetés lefelé
        FIRST,          // első elem
        LAST,           // utolsó elem
        FIELD,          // szövegmező kiválasztva
        LONG_PRESS,     // hosszan nyomás
        ACTIVATE,       // aktiválás, gombnyomás
        NOTIFICATIONS,  // értesítések
        RECENTS,        // legutóbbi alkalmazások
        HOME,           // kezdőképernyő
        ON,             // olvasó bekapcsol
        OFF             // olvasó kikapcsol
    }

    init {
        try {
            ids[Sound.NEXT] = pool.load(context, R.raw.snd_sr_next, 1)
            ids[Sound.PREV] = pool.load(context, R.raw.snd_sr_prev, 1)
            ids[Sound.EDGE] = pool.load(context, R.raw.snd_sr_edge, 1)
            ids[Sound.ERROR] = pool.load(context, R.raw.snd_sr_error, 1)
            ids[Sound.BACK] = pool.load(context, R.raw.snd_sr_back, 1)
            ids[Sound.SCROLL_UP] = pool.load(context, R.raw.snd_sr_scroll_up, 1)
            ids[Sound.SCROLL_DOWN] = pool.load(context, R.raw.snd_sr_scroll_down, 1)
            ids[Sound.FIRST] = pool.load(context, R.raw.snd_sr_first, 1)
            ids[Sound.LAST] = pool.load(context, R.raw.snd_sr_last, 1)
            ids[Sound.FIELD] = pool.load(context, R.raw.snd_sr_field, 1)
            ids[Sound.LONG_PRESS] = pool.load(context, R.raw.snd_sr_longpress, 1)
            ids[Sound.ACTIVATE] = pool.load(context, R.raw.snd_sr_activate, 1)
            ids[Sound.NOTIFICATIONS] = pool.load(context, R.raw.snd_sr_notifications, 1)
            ids[Sound.RECENTS] = pool.load(context, R.raw.snd_sr_recents, 1)
            ids[Sound.HOME] = pool.load(context, R.raw.snd_sr_home, 1)
            ids[Sound.ON] = pool.load(context, R.raw.snd_sr_on, 1)
            ids[Sound.OFF] = pool.load(context, R.raw.snd_sr_off, 1)
            pool.setOnLoadCompleteListener { _, _, status ->
                if (status == 0) loadedCount++
            }
        } catch (e: Exception) {
            android.util.Log.w(ScreenReaderPrefs.TAG, "Hangok betoltese sikertelen: ${e.message}")
        }
    }

    /**
     * Egy visszajelző hang megszólaltatása.
     * Ha a betöltés még tart, csendben kihagyjuk — jobb egy hiányzó koppanás,
     * mint egy akadó vagy hibás lejátszás.
     */
    fun play(sound: Sound) {
        if (!ready) return
        val id = ids[sound] ?: return
        try {
            pool.play(id, 0.7f, 0.7f, 1, 0, 1f)
        } catch (_: Exception) {
        }
    }

    /**
     * HELYZETJELZŐ HANG — a magasság mutatja, hol tartasz a listában.
     *
     * MIÉRT HASZNOS: egy hosszú listában szavakkal lassú lenne folyton közölni a
     * pozíciót ("37 / 210"), de a HANG MAGASSÁGÁT azonnal érzed. Mély hang a
     * lista elején, egyre magasabb a vége felé — így görgetés közben is tudod,
     * mennyi van még hátra, anélkül hogy bármit meg kellene hallgatnod.
     *
     * @param position 0.0 = a lista eleje, 1.0 = a vége
     */
    fun playAtPosition(sound: Sound, position: Float) {
        if (!ready) return
        val id = ids[sound] ?: return
        // A lejátszási sebesség egyben a hangmagasság is. A 0.75–1.6 tartomány
        // jól hallható különbséget ad, de nem torzítja el a hangot.
        val rate = (0.75f + position.coerceIn(0f, 1f) * 0.85f).coerceIn(0.5f, 2.0f)
        try {
            pool.play(id, 0.7f, 0.7f, 1, 0, rate)
        } catch (_: Exception) {
        }
    }

    fun release() {
        try {
            pool.release()
        } catch (_: Exception) {
        }
    }
}
