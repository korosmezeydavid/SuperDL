package com.superdl.launcher.calendar

import android.content.Context

/**
 * Melyik naptárba kerüljenek a SuperDL-lel felvett programok.
 *
 * MIÉRT KELL EZ:
 * A telefonokon több naptár is van. Van köztük HELYI naptár (pl. "PC Sync"),
 * ami SEHOVA NEM SZINKRONIZÁL — ami oda kerül, az csak a telefonon létezik.
 * A rendszer ezt gyakran "elsődlegesnek" jelöli, ezért a program eddig oda írt,
 * és a felvett programok nem jelentek meg a Google Naptárban.
 *
 * Mostantól a felhasználó választhat, és alapból a GOOGLE-fiók naptárát
 * részesítjük előnyben — mert az szinkronizál a webbel és a többi eszközzel.
 */
object CalendarPreferenceStore {

    private const val PREFS = "superdl_calendar"
    private const val KEY_CALENDAR_ID = "target_calendar_id"

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** A felhasználó által választott naptár, vagy null ha még nem választott. */
    fun getChosenCalendarId(context: Context): Long? {
        val id = prefs(context).getLong(KEY_CALENDAR_ID, -1L)
        return if (id > 0) id else null
    }

    fun setChosenCalendarId(context: Context, id: Long) {
        prefs(context).edit().putLong(KEY_CALENDAR_ID, id).apply()
    }

    fun clearChoice(context: Context) {
        prefs(context).edit().remove(KEY_CALENDAR_ID).apply()
    }
}
