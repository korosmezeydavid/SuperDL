package com.superdl.launcher.assistant

import android.content.Context

/**
 * Az Elena hangasszisztens viselkedési beállításai.
 */
object AssistantPrefs {

    private const val PREFS = "superdl"
    private const val KEY_CONTINUOUS = "assistant_continuous_mode"

    /**
     * Folyamatos beszélgetés: a parancs végrehajtása után az asszisztens
     * TOVÁBB HALLGAT, és újabb utasítást vár.
     *
     * ALAPBÓL KIKAPCSOLVA. Korábban ez volt az egyetlen működés, és "beragadás"
     * érzetet keltett: a feladat elkészült, a válasz elhangzott, az asszisztens
     * mégis tovább várakozott. Kikapcsolva a parancs után csendben visszatér a
     * menübe — aki viszont több parancsot szeretne egymás után, bekapcsolhatja.
     */
    fun isContinuousMode(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_CONTINUOUS, false)

    fun setContinuousMode(context: Context, on: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putBoolean(KEY_CONTINUOUS, on).apply()
    }
}
