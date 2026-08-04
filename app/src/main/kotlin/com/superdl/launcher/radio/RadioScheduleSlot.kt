package com.superdl.launcher.radio

/**
 * Egy időzített felvételi slot: "vedd fel [állomás] adását [kezdés]-től [vég]-ig".
 *
 * Az idők a nap perceiben értendők (0–1439): pl. 20:00 = 1200, 22:00 = 1320.
 * A repeatDaily jelzi, hogy minden nap ismétlődjön-e, vagy csak a legközelebbi
 * alkalommal fusson.
 */
data class RadioScheduleSlot(
    val id: String,
    val stationName: String,
    val streamUrl: String,
    val startMinuteOfDay: Int,
    val endMinuteOfDay: Int,
    val repeatDaily: Boolean = true,
    val enabled: Boolean = true
) {
    /** A felvétel hossza percben (ha a vég a következő napra nyúlik, +24 óra). */
    fun durationMinutes(): Int {
        val raw = endMinuteOfDay - startMinuteOfDay
        return if (raw > 0) raw else raw + 24 * 60
    }

    fun startLabel(): String = minuteLabel(startMinuteOfDay)
    fun endLabel(): String = minuteLabel(endMinuteOfDay)

    private fun minuteLabel(m: Int): String {
        val h = (m / 60) % 24
        val min = m % 60
        return "%02d:%02d".format(h, min)
    }
}
