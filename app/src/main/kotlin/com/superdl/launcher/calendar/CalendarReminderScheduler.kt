package com.superdl.launcher.calendar

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent

object CalendarReminderScheduler {

    private const val LOOKAHEAD_DAYS = 21

    fun rescheduleUpcoming(context: Context) {
        if (!CalendarHelper.hasReadPermission(context)) return
        val now = System.currentTimeMillis()
        val end = now + LOOKAHEAD_DAYS * 86_400_000L
        CalendarHelper.getInstancesBetween(context, now, end).forEach { event ->
            if (!CalendarReminderStore.isCompleted(context, event.eventId, event.begin)) {
                scheduleInstance(context, event)
            }
        }
    }

    fun scheduleForEvent(context: Context, event: CalendarEvent) {
        if (event.begin > System.currentTimeMillis()) {
            scheduleInstance(context, event)
        }
        rescheduleUpcoming(context)
    }

    fun scheduleInstance(
        context: Context,
        event: CalendarEvent,
        triggerAtMs: Long = event.begin
    ): Boolean {
        if (triggerAtMs <= System.currentTimeMillis()) return false
        if (!CalendarHelper.hasReadPermission(context)) return false
        if (CalendarReminderStore.isCompleted(context, event.eventId, event.begin)) return false

        val intent = Intent(context, CalendarAlarmReceiver::class.java).apply {
            action = CalendarAlarmReceiver.ACTION_CALENDAR_ALARM
            putExtra(CalendarAlarmReceiver.EXTRA_EVENT_ID, event.eventId)
            putExtra(CalendarAlarmReceiver.EXTRA_TITLE, event.title)
            putExtra(CalendarAlarmReceiver.EXTRA_BEGIN_MS, event.begin)
            putExtra(CalendarAlarmReceiver.EXTRA_END_MS, event.end)
            putExtra(CalendarAlarmReceiver.EXTRA_TRIGGER_MS, triggerAtMs)
        }
        val requestCode = CalendarReminderStore.reminderRequestCode(event.eventId, event.begin)
        val pendingIntent = PendingIntent.getBroadcast(
            context,
            requestCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return com.superdl.launcher.alarm.AlarmScheduler.setExactAlarm(context, triggerAtMs, pendingIntent)
    }

    fun scheduleSnoozeOneHour(
        context: Context,
        eventId: Long,
        title: String,
        beginMs: Long,
        endMs: Long
    ) {
        cancelInstance(context, eventId, beginMs)
        val triggerAt = System.currentTimeMillis() + 60 * 60_000L
        scheduleInstance(
            context,
            CalendarEvent(eventId, title, beginMs, endMs),
            triggerAtMs = triggerAt
        )
    }

    fun cancelInstance(context: Context, eventId: Long, beginMs: Long) {
        val intent = Intent(context, CalendarAlarmReceiver::class.java).apply {
            action = CalendarAlarmReceiver.ACTION_CALENDAR_ALARM
        }
        val requestCode = CalendarReminderStore.reminderRequestCode(eventId, beginMs)
        val pendingIntent = PendingIntent.getBroadcast(
            context,
            requestCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        context.getSystemService(AlarmManager::class.java)?.cancel(pendingIntent)
    }

    fun cancelAllForEvent(context: Context, eventId: Long) {
        val now = System.currentTimeMillis()
        val end = now + LOOKAHEAD_DAYS * 86_400_000L
        CalendarHelper.getInstancesBetween(context, now, end)
            .filter { it.eventId == eventId }
            .forEach { cancelInstance(context, it.eventId, it.begin) }
    }
}