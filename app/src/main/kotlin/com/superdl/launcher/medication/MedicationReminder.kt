package com.superdl.launcher.medication

import java.util.Calendar

enum class MedicationCycleType(val label: String) {
    DAILY("Naponta"),
    WEEKLY("Hetente"),
    CUSTOM("Egyéni napok");

    fun speakSummary(): String = label
}

/**
 * Tipikus napszakok a gyógyszer-emlékeztetőhöz, alapértelmezett időpontokkal.
 * A felhasználó többet is bepipálhat (pl. reggel + este), és mindegyikből
 * külön emlékeztető lesz, azonos gyógyszernévvel.
 */
enum class MedicationTimeOfDay(
    val label: String,
    val hour: Int,
    val minute: Int
) {
    MORNING("Reggel", 8, 0),
    NOON("Dél", 12, 0),
    EVENING("Este", 18, 0),
    BEDTIME("Lefekvés", 22, 0);

    fun speakLabel(): String {
        val h = hour.toString().padStart(2, '0')
        val m = minute.toString().padStart(2, '0')
        return "$label, $h óra $m perc"
    }
}

data class MedicationReminder(
    val id: Int,
    val name: String,
    val hour: Int,
    val minute: Int,
    val cycleType: MedicationCycleType,
    val weekDays: Set<Int> = emptySet(),
    val enabled: Boolean = true,
    // Kúra vége: ha nem null, ez az utolsó nap (nap végi millis), ameddig
    // az emlékeztető aktív. Utána magától leáll (pl. antibiotikum 7 nap).
    // null = folyamatos (nincs záró dátum).
    val courseEndMillis: Long? = null
) {
    fun speakTime(): String {
        val hourWord = hour.toString().padStart(2, '0')
        val minuteWord = minute.toString().padStart(2, '0')
        return "$hourWord óra $minuteWord perc"
    }

    /** Van-e megadva kúra-vég (alkalmi/időszakos gyógyszer). */
    fun isCourse(): Boolean = courseEndMillis != null

    /** Lejárt-e már a kúra (a záró dátum elmúlt). */
    fun isCourseExpired(nowMillis: Long = System.currentTimeMillis()): Boolean =
        courseEndMillis != null && nowMillis > courseEndMillis

    fun speakCourse(): String = when {
        courseEndMillis == null -> "folyamatos"
        else -> {
            val cal = java.util.Calendar.getInstance().apply { timeInMillis = courseEndMillis }
            val y = cal.get(java.util.Calendar.YEAR)
            val mo = cal.get(java.util.Calendar.MONTH) + 1
            val d = cal.get(java.util.Calendar.DAY_OF_MONTH)
            "kúra eddig: $y. $mo. hó $d."
        }
    }

    fun speakCycle(): String = when (cycleType) {
        MedicationCycleType.DAILY -> cycleType.label
        MedicationCycleType.WEEKLY,
        MedicationCycleType.CUSTOM -> {
            val days = weekDays.map { MedicationWeekdays.labelFor(it) }.sorted()
            if (days.isEmpty()) cycleType.label else "${cycleType.label}: ${days.joinToString(", ")}"
        }
    }

    fun speakSummary(): String {
        val base = "$name, ${speakTime()}, ${speakCycle()}"
        return if (isCourse()) "$base, ${speakCourse()}" else base
    }

    fun shouldFireOn(dayOfWeek: Int): Boolean = when (cycleType) {
        MedicationCycleType.DAILY -> true
        MedicationCycleType.WEEKLY,
        MedicationCycleType.CUSTOM -> dayOfWeek in weekDays
    }

    fun shouldFireToday(): Boolean = shouldFireOn(Calendar.getInstance().get(Calendar.DAY_OF_WEEK))
}

data class WeekdayOption(
    val dayOfWeek: Int,
    val label: String
)

object MedicationWeekdays {
    val all: List<WeekdayOption> = listOf(
        WeekdayOption(Calendar.MONDAY, "Hétfő"),
        WeekdayOption(Calendar.TUESDAY, "Kedd"),
        WeekdayOption(Calendar.WEDNESDAY, "Szerda"),
        WeekdayOption(Calendar.THURSDAY, "Csütörtök"),
        WeekdayOption(Calendar.FRIDAY, "Péntek"),
        WeekdayOption(Calendar.SATURDAY, "Szombat"),
        WeekdayOption(Calendar.SUNDAY, "Vasárnap")
    )

    fun labelFor(dayOfWeek: Int): String =
        all.firstOrNull { it.dayOfWeek == dayOfWeek }?.label ?: "Ismeretlen nap"
}

data class MedicationIngestionLog(
    val reminderId: Int,
    val medicationName: String,
    val takenAtMillis: Long
)