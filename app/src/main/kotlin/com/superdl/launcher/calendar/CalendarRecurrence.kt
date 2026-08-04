package com.superdl.launcher.calendar

enum class CalendarRecurrence(
    val label: String,
    val rrule: String?
) {
    NONE("Nincs ismétlés", null),
    DAILY("Naponta", "FREQ=DAILY"),
    WEEKLY("Hetente", "FREQ=WEEKLY"),
    BIWEEKLY("Kéthetente", "FREQ=WEEKLY;INTERVAL=2"),
    MONTHLY("Havonta", "FREQ=MONTHLY"),
    YEARLY("Évente", "FREQ=YEARLY");

    fun speakSummary(): String = label

    companion object {
        val selectable: List<CalendarRecurrence> = entries.toList()

        fun fromRRule(rrule: String?): CalendarRecurrence {
            if (rrule.isNullOrBlank()) return NONE
            val normalized = rrule.removePrefix("RRULE:").trim()
            return entries.firstOrNull { it.rrule == normalized } ?: NONE
        }
    }
}