package com.superdl.launcher.calendar

import android.Manifest
import android.content.ContentUris
import android.content.ContentValues
import android.content.Context
import android.content.pm.PackageManager
import android.provider.CalendarContract
import androidx.core.content.ContextCompat
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone

object CalendarHelper {

    fun hasReadPermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CALENDAR) ==
            PackageManager.PERMISSION_GRANTED

    fun hasWritePermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.WRITE_CALENDAR) ==
            PackageManager.PERMISSION_GRANTED

    fun getTodayEvents(context: Context): List<CalendarEvent> =
        getEventsForDay(context, 0)

    fun getTomorrowEvents(context: Context): List<CalendarEvent> =
        getEventsForDay(context, 1)

    fun getWeekEvents(context: Context): List<CalendarDayGroup> {
        val groups = mutableListOf<CalendarDayGroup>()
        for (offset in 0..6) {
            val events = getEventsForDay(context, offset)
            if (events.isNotEmpty()) {
                groups.add(CalendarDayGroup(dayLabel(offset), events))
            }
        }
        return groups
    }

    fun getInstancesBetween(context: Context, startMs: Long, endMs: Long): List<CalendarEvent> =
        queryEvents(context, startMs, endMs, limit = 200)

    fun getEventById(context: Context, eventId: Long): CalendarEvent? {
        if (!hasReadPermission(context)) return null
        val projection = arrayOf(
            CalendarContract.Events._ID,
            CalendarContract.Events.TITLE,
            CalendarContract.Events.DTSTART,
            CalendarContract.Events.DTEND,
            CalendarContract.Events.RRULE,
            CalendarContract.Events.DURATION
        )
        context.contentResolver.query(
            ContentUris.withAppendedId(CalendarContract.Events.CONTENT_URI, eventId),
            projection,
            null,
            null,
            null
        )?.use { cursor ->
            if (!cursor.moveToFirst()) return null
            val title = cursor.getString(cursor.getColumnIndexOrThrow(CalendarContract.Events.TITLE))
                ?.trim().orEmpty()
            val begin = cursor.getLong(cursor.getColumnIndexOrThrow(CalendarContract.Events.DTSTART))
            val end = cursor.getLong(cursor.getColumnIndexOrThrow(CalendarContract.Events.DTEND))
            val rrule = cursor.getString(cursor.getColumnIndexOrThrow(CalendarContract.Events.RRULE))
            val resolvedEnd = if (end > 0L) end else begin + 60 * 60_000L
            return CalendarEvent(eventId, title, begin, resolvedEnd, CalendarRecurrence.fromRRule(rrule))
        }
        return null
    }

    private fun getEventsForDay(context: Context, dayOffset: Int): List<CalendarEvent> {
        val startCal = Calendar.getInstance().apply {
            add(Calendar.DAY_OF_YEAR, dayOffset)
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val endCal = Calendar.getInstance().apply {
            timeInMillis = startCal.timeInMillis
            set(Calendar.HOUR_OF_DAY, 23)
            set(Calendar.MINUTE, 59)
            set(Calendar.SECOND, 59)
            set(Calendar.MILLISECOND, 999)
        }
        return queryEvents(context, startCal.timeInMillis, endCal.timeInMillis)
    }

    private fun queryEvents(
        context: Context,
        start: Long,
        end: Long,
        limit: Int = 20
    ): List<CalendarEvent> {
        if (!hasReadPermission(context)) return emptyList()
        val events = mutableListOf<CalendarEvent>()
        val uri = CalendarContract.Instances.CONTENT_URI.buildUpon()
            .appendPath(start.toString())
            .appendPath(end.toString())
            .build()

        val projection = arrayOf(
            CalendarContract.Instances.EVENT_ID,
            CalendarContract.Instances.TITLE,
            CalendarContract.Instances.BEGIN,
            CalendarContract.Instances.END
        )

        context.contentResolver.query(
            uri,
            projection,
            null,
            null,
            "${CalendarContract.Instances.BEGIN} ASC"
        )?.use { cursor ->
            val eventIdIdx = cursor.getColumnIndex(CalendarContract.Instances.EVENT_ID)
            val titleIdx = cursor.getColumnIndex(CalendarContract.Instances.TITLE)
            val beginIdx = cursor.getColumnIndex(CalendarContract.Instances.BEGIN)
            val endIdx = cursor.getColumnIndex(CalendarContract.Instances.END)
            while (cursor.moveToNext() && events.size < limit) {
                val eventId = cursor.getLong(eventIdIdx)
                val title = cursor.getString(titleIdx)?.trim().orEmpty()
                val begin = cursor.getLong(beginIdx)
                val endTime = cursor.getLong(endIdx)
                if (title.isNotBlank()) {
                    events.add(CalendarEvent(eventId, title, begin, endTime))
                }
            }
        }
        return events
    }

    private fun dayLabel(dayOffset: Int): String {
        val cal = Calendar.getInstance().apply { add(Calendar.DAY_OF_YEAR, dayOffset) }
        val fmt = SimpleDateFormat("EEEE, MMMM d.", Locale("hu", "HU"))
        return when (dayOffset) {
            0 -> "Ma, ${fmt.format(cal.time)}"
            1 -> "Holnap, ${fmt.format(cal.time)}"
            else -> fmt.format(cal.time)
        }
    }

    fun speakEvent(event: CalendarEvent): String {
        val timeFmt = SimpleDateFormat("H:mm", Locale("hu", "HU"))
        val start = timeFmt.format(Date(event.begin))
        val endTime = timeFmt.format(Date(event.end))
        val recurrence = if (event.recurrence != CalendarRecurrence.NONE) {
            ", ${event.recurrence.speakSummary()}"
        } else {
            ""
        }
        return "$start-től $endTime-ig: ${event.title}$recurrence"
    }

    fun speakAllEvents(events: List<CalendarEvent>): String {
        if (events.isEmpty()) return "Ma nincs bejegyzés a naptárban."
        val intro = if (events.size == 1) "Ma 1 programod van." else "Ma ${events.size} programod van."
        val body = events.joinToString(". ") { speakEvent(it) }
        return "$intro $body"
    }

    /** Egy naptár adatai a választáshoz és az állapot-felolvasáshoz. */
    data class CalendarInfo(
        val id: Long,
        val displayName: String,
        val accountName: String,
        val accountType: String,
        val isPrimary: Boolean
    ) {
        /** Szinkronizál-e a felhővel (Google, Exchange stb.)? */
        val syncs: Boolean get() = !accountType.equals("LOCAL", true)

        fun speakSummary(): String {
            val where = if (syncs) "szinkronizál: $accountName" else "csak ezen a telefonon"
            return "$displayName, $where"
        }
    }

    /**
     * Az ÍRHATÓ naptárak listája.
     * A szinkronizálók (Google) kerülnek előre, mert azokat várja a felhasználó.
     */
    fun getWritableCalendars(context: Context): List<CalendarInfo> {
        val out = mutableListOf<CalendarInfo>()
        val projection = arrayOf(
            CalendarContract.Calendars._ID,
            CalendarContract.Calendars.CALENDAR_DISPLAY_NAME,
            CalendarContract.Calendars.ACCOUNT_NAME,
            CalendarContract.Calendars.ACCOUNT_TYPE,
            CalendarContract.Calendars.IS_PRIMARY
        )
        val selection = "${CalendarContract.Calendars.CALENDAR_ACCESS_LEVEL} >= ?"
        val args = arrayOf(CalendarContract.Calendars.CAL_ACCESS_CONTRIBUTOR.toString())
        try {
            context.contentResolver.query(
                CalendarContract.Calendars.CONTENT_URI, projection, selection, args, null
            )?.use { c ->
                while (c.moveToNext()) {
                    out.add(
                        CalendarInfo(
                            id = c.getLong(0),
                            displayName = c.getString(1) ?: "Névtelen naptár",
                            accountName = c.getString(2) ?: "",
                            accountType = c.getString(3) ?: "",
                            isPrimary = c.getInt(4) == 1
                        )
                    )
                }
            }
        } catch (e: Exception) {
            android.util.Log.w("SDL_CALENDAR", "naptar-lista hiba: ${e.message}")
        }
        // A szinkronizáló (felhős) naptárak előre; azon belül az elsődleges.
        return out.sortedWith(
            compareByDescending<CalendarInfo> { it.syncs }
                .thenByDescending { it.isPrimary }
        )
    }

    fun getWritableCalendarId(context: Context): Long? {
        // 1. A FELHASZNÁLÓ választása mindent felülír.
        CalendarPreferenceStore.getChosenCalendarId(context)?.let { chosen ->
            if (getWritableCalendars(context).any { it.id == chosen }) return chosen
        }
        // 2. Különben a SZINKRONIZÁLÓ naptárat választjuk — enélkül a program a
        //    helyi "PC Sync" naptárba írna, ami sehova nem szinkronizál, és a
        //    felvett események nem jelennének meg a Google Naptárban.
        getWritableCalendars(context).firstOrNull { it.syncs }?.let { return it.id }
        // 3. Végső tartalék: a régi logika (bármelyik írható naptár).
        return legacyWritableCalendarId(context)
    }

    private fun legacyWritableCalendarId(context: Context): Long? {
        val projection = arrayOf(
            CalendarContract.Calendars._ID,
            CalendarContract.Calendars.CALENDAR_ACCESS_LEVEL,
            CalendarContract.Calendars.IS_PRIMARY
        )
        val selection = "${CalendarContract.Calendars.VISIBLE} = 1 AND " +
            "${CalendarContract.Calendars.CALENDAR_ACCESS_LEVEL} >= ?"
        val args = arrayOf(CalendarContract.Calendars.CAL_ACCESS_CONTRIBUTOR.toString())

        var primaryId: Long? = null
        var fallbackId: Long? = null

        context.contentResolver.query(
            CalendarContract.Calendars.CONTENT_URI,
            projection,
            selection,
            args,
            null
        )?.use { cursor ->
            val idIdx = cursor.getColumnIndex(CalendarContract.Calendars._ID)
            val primaryIdx = cursor.getColumnIndex(CalendarContract.Calendars.IS_PRIMARY)
            while (cursor.moveToNext()) {
                val id = cursor.getLong(idIdx)
                val isPrimary = primaryIdx >= 0 && cursor.getInt(primaryIdx) == 1
                if (isPrimary) {
                    primaryId = id
                    break
                }
                if (fallbackId == null) fallbackId = id
            }
        }
        return primaryId ?: fallbackId
    }

    fun insertEvent(
        context: Context,
        title: String,
        beginMs: Long,
        endMs: Long,
        recurrence: CalendarRecurrence = CalendarRecurrence.NONE
    ): Long? {
        val calendarId = getWritableCalendarId(context) ?: return null
        val values = ContentValues().apply {
            put(CalendarContract.Events.CALENDAR_ID, calendarId)
            put(CalendarContract.Events.TITLE, title.trim())
            put(CalendarContract.Events.DTSTART, beginMs)
            put(CalendarContract.Events.DTEND, endMs)
            put(CalendarContract.Events.EVENT_TIMEZONE, TimeZone.getDefault().id)
            put(CalendarContract.Events.EVENT_END_TIMEZONE, TimeZone.getDefault().id)
            put(CalendarContract.Events.HAS_ALARM, 0)
            recurrence.rrule?.let { put(CalendarContract.Events.RRULE, it) }
        }
        val uri = context.contentResolver.insert(CalendarContract.Events.CONTENT_URI, values) ?: return null
        val eventId = ContentUris.parseId(uri)
        val event = CalendarEvent(eventId, title.trim(), beginMs, endMs, recurrence)
        CalendarReminderScheduler.scheduleForEvent(context, event)
        return eventId
    }

    fun updateEvent(
        context: Context,
        eventId: Long,
        title: String,
        beginMs: Long,
        endMs: Long,
        recurrence: CalendarRecurrence
    ): Boolean {
        val values = ContentValues().apply {
            put(CalendarContract.Events.TITLE, title.trim())
            put(CalendarContract.Events.DTSTART, beginMs)
            put(CalendarContract.Events.DTEND, endMs)
            put(CalendarContract.Events.EVENT_TIMEZONE, TimeZone.getDefault().id)
            put(CalendarContract.Events.EVENT_END_TIMEZONE, TimeZone.getDefault().id)
            if (recurrence == CalendarRecurrence.NONE) {
                putNull(CalendarContract.Events.RRULE)
            } else {
                put(CalendarContract.Events.RRULE, recurrence.rrule)
            }
        }
        val updated = context.contentResolver.update(
            ContentUris.withAppendedId(CalendarContract.Events.CONTENT_URI, eventId),
            values,
            null,
            null
        )
        if (updated <= 0) return false
        CalendarReminderScheduler.cancelAllForEvent(context, eventId)
        CalendarReminderStore.clearCompletedForEvent(context, eventId)
        val event = CalendarEvent(eventId, title.trim(), beginMs, endMs, recurrence)
        CalendarReminderScheduler.scheduleForEvent(context, event)
        return true
    }

    fun deleteEvent(context: Context, eventId: Long): Boolean {
        CalendarReminderScheduler.cancelAllForEvent(context, eventId)
        CalendarReminderStore.clearCompletedForEvent(context, eventId)
        val deleted = context.contentResolver.delete(
            ContentUris.withAppendedId(CalendarContract.Events.CONTENT_URI, eventId),
            null,
            null
        )
        return deleted > 0
    }

    fun buildEventTimes(
        dayStartMs: Long,
        startHour: Int,
        startMinute: Int,
        endHour: Int,
        endMinute: Int
    ): Pair<Long, Long> {
        val beginCal = Calendar.getInstance().apply {
            timeInMillis = dayStartMs
            set(Calendar.HOUR_OF_DAY, startHour)
            set(Calendar.MINUTE, startMinute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val endCal = Calendar.getInstance().apply {
            timeInMillis = dayStartMs
            set(Calendar.HOUR_OF_DAY, endHour)
            set(Calendar.MINUTE, endMinute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        if (endCal.timeInMillis <= beginCal.timeInMillis) {
            endCal.add(Calendar.DAY_OF_YEAR, 1)
        }
        return beginCal.timeInMillis to endCal.timeInMillis
    }

    fun buildEventTimesWithDuration(
        dayStartMs: Long,
        startHour: Int,
        startMinute: Int,
        durationMinutes: Int
    ): Pair<Long, Long> {
        val beginCal = Calendar.getInstance().apply {
            timeInMillis = dayStartMs
            set(Calendar.HOUR_OF_DAY, startHour)
            set(Calendar.MINUTE, startMinute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val endMs = beginCal.timeInMillis + durationMinutes.coerceAtLeast(15) * 60_000L
        return beginCal.timeInMillis to endMs
    }

    fun speakDayLabel(dayStartMs: Long): String {
        val today = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val target = Calendar.getInstance().apply { timeInMillis = dayStartMs }
        val fmt = SimpleDateFormat("EEEE, MMMM d.", Locale("hu", "HU"))
        val diff = ((dayStartMs - today.timeInMillis) / 86_400_000L).toInt()
        return when (diff) {
            0 -> "Ma, ${fmt.format(target.time)}"
            1 -> "Holnap, ${fmt.format(target.time)}"
            else -> fmt.format(target.time)
        }
    }

    fun speakEventConfirm(
        title: String,
        beginMs: Long,
        endMs: Long,
        recurrence: CalendarRecurrence
    ): String {
        val dayLabel = speakDayLabel(
            Calendar.getInstance().apply {
                timeInMillis = beginMs
                set(Calendar.HOUR_OF_DAY, 0)
                set(Calendar.MINUTE, 0)
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
            }.timeInMillis
        )
        val event = CalendarEvent(0L, title, beginMs, endMs, recurrence)
        val recurrenceText = if (recurrence == CalendarRecurrence.NONE) {
            ""
        } else {
            " Ismétlés: ${recurrence.speakSummary()}."
        }
        return "Új program: $dayLabel. ${speakEvent(event)}.$recurrenceText Mentem a naptárba? Söpörj jobbra a mentéshez, söprés balra a mégsehez."
    }

    fun speakEditEventConfirm(
        title: String,
        beginMs: Long,
        endMs: Long,
        recurrence: CalendarRecurrence
    ): String {
        val event = CalendarEvent(0L, title, beginMs, endMs, recurrence)
        val recurrenceText = if (recurrence == CalendarRecurrence.NONE) {
            "Nincs ismétlés."
        } else {
            "Ismétlés: ${recurrence.speakSummary()}."
        }
        return "Módosított program: ${speakEvent(event)}. $recurrenceText Mentem? Söpörj jobbra a mentéshez, söprés balra a mégsehez."
    }

    fun speakAlarmPrompt(event: CalendarEvent): String =
        "Program ideje! ${speakEvent(event)}. Válassz műveletet."
}