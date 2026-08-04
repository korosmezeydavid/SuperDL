package com.superdl.launcher.calendar

data class CalendarEvent(
    val eventId: Long,
    val title: String,
    val begin: Long,
    val end: Long,
    val recurrence: CalendarRecurrence = CalendarRecurrence.NONE
)

data class CalendarDayGroup(
    val dayLabel: String,
    val events: List<CalendarEvent>
) {
    fun speakPreview(): String {
        val count = if (events.size == 1) "1 program" else "${events.size} program"
        return "$dayLabel. $count."
    }

    fun speakFull(): String {
        val body = events.joinToString(". ") { CalendarHelper.speakEvent(it) }
        return "$dayLabel. $body"
    }
}