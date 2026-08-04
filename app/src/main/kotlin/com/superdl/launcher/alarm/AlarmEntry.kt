package com.superdl.launcher.alarm

import java.util.Calendar

/**
 * Egy ébresztő. Mostantól ismétlődhet (egyszeri/napi/hétköznap/hétvége/egyéni),
 * lehet saját gyári hangja (ha nincs, az alap ébresztőhang szól), és
 * ébresztőnként állítható a szundi.
 */
data class AlarmEntry(
    val id: Int,
    val hour: Int,
    val minute: Int,
    val label: String,
    val enabled: Boolean = true,
    val repeatType: AlarmRepeatType = AlarmRepeatType.ONCE,
    val weekDays: Set<Int> = emptySet(),   // Calendar.MONDAY..SUNDAY, csak CUSTOM esetén
    val toneUri: String? = null,           // null = alapértelmezett ébresztőhang
    val toneTitle: String? = null,         // a hang neve felolvasáshoz
    val snoozeEnabled: Boolean = true,

    /**
     * Hány KÖVETKEZŐ ébresztést hagyjon ki ez az ébresztő.
     *
     * Nem napokat számol, hanem ébresztéseket: ha 2, akkor a következő két
     * alkalommal néma marad (a számláló magától fogy), utána újra megszólal.
     * Így nem kell kézzel ki- majd visszakapcsolni az ébresztőket, ha például
     * pénteken és hétfőn nem kell dolgozni.
     */
    val skipRemaining: Int = 0
) {
    /** Aktív, de átmenetileg kihagyás alatt áll. */
    val isSkipping: Boolean get() = skipRemaining > 0
    fun speakTime(): String {
        val hourWord = hour.toString().padStart(2, '0')
        val minuteWord = minute.toString().padStart(2, '0')
        return "$hourWord óra $minuteWord perc"
    }

    fun speakSummary(): String {
        val name = if (label.isBlank()) "Ébresztő" else label
        return "$name, ${speakTime()}, ${repeatType.speakLabel(weekDays)}"
    }

    /** Aktív-e ez az ébresztő a megadott naptári napon (ismétlés szerint). */
    fun isActiveOnDay(dayOfWeek: Int): Boolean = when (repeatType) {
        AlarmRepeatType.ONCE -> true
        AlarmRepeatType.DAILY -> true
        AlarmRepeatType.WEEKDAYS -> dayOfWeek in Calendar.MONDAY..Calendar.FRIDAY
        AlarmRepeatType.WEEKEND -> dayOfWeek == Calendar.SATURDAY || dayOfWeek == Calendar.SUNDAY
        AlarmRepeatType.CUSTOM -> dayOfWeek in weekDays
    }

    /** Egyszeri ébresztő-e (a csörgés után kikapcsol). */
    fun isOneTime(): Boolean = repeatType == AlarmRepeatType.ONCE
}

/**
 * Ébresztő ismétlési módjai.
 */
enum class AlarmRepeatType {
    ONCE,       // egyszeri
    DAILY,      // minden nap
    WEEKDAYS,   // hétköznap (hétfő–péntek)
    WEEKEND,    // hétvége (szombat–vasárnap)
    CUSTOM;     // kiválasztott napokon

    fun speakLabel(weekDays: Set<Int> = emptySet()): String = when (this) {
        ONCE -> "egyszeri"
        DAILY -> "minden nap"
        WEEKDAYS -> "hétköznap"
        WEEKEND -> "hétvégén"
        CUSTOM -> if (weekDays.isEmpty()) {
            "egyéni napokon"
        } else {
            weekDays.sorted().joinToString(", ") { dayName(it) }
        }
    }

    companion object {
        fun dayName(calendarDay: Int): String = when (calendarDay) {
            Calendar.MONDAY -> "hétfő"
            Calendar.TUESDAY -> "kedd"
            Calendar.WEDNESDAY -> "szerda"
            Calendar.THURSDAY -> "csütörtök"
            Calendar.FRIDAY -> "péntek"
            Calendar.SATURDAY -> "szombat"
            Calendar.SUNDAY -> "vasárnap"
            else -> ""
        }
    }
}
