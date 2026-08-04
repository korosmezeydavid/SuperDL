package com.superdl.launcher.medication

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import com.superdl.launcher.alarm.AlarmScheduler
import java.util.Calendar

object MedicationScheduler {

    const val ALARM_REQUEST_BASE = 30_000
    private const val SNOOZE_REQUEST_BASE = 40_000

    fun canScheduleExact(context: Context): Boolean = AlarmScheduler.canScheduleExact(context)

    fun schedule(context: Context, entry: MedicationReminder) {
        scheduleAndReport(context, entry)
    }

    fun scheduleAndReport(context: Context, entry: MedicationReminder): Boolean {
        if (!entry.enabled) return false
        if (!isSchedulable(entry)) return false
        // Ha a kúra (pl. antibiotikum 7 nap) már lejárt, nem ütemezünk többet,
        // és kikapcsoljuk az emlékeztetőt, hogy magától leálljon.
        if (entry.isCourseExpired()) {
            MedicationStore.setEnabled(context, entry.id, false)
            cancel(context, entry.id)
            return false
        }
        val triggerAt = nextTriggerMillis(entry)
        if (triggerAt <= 0L) return false
        // A következő riasztás túllépné a kúra végét? Akkor ez volt az utolsó.
        if (entry.courseEndMillis != null && triggerAt > entry.courseEndMillis) {
            MedicationStore.setEnabled(context, entry.id, false)
            cancel(context, entry.id)
            return false
        }
        val intent = Intent(context, MedicationAlarmReceiver::class.java).apply {
            putExtra(MedicationAlarmReceiver.EXTRA_REMINDER_ID, entry.id)
            putExtra(MedicationAlarmReceiver.EXTRA_HOUR, entry.hour)
            putExtra(MedicationAlarmReceiver.EXTRA_MINUTE, entry.minute)
        }
        val pendingIntent = PendingIntent.getBroadcast(
            context,
            ALARM_REQUEST_BASE + entry.id,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return AlarmScheduler.setExactAlarm(context, triggerAt, pendingIntent)
    }

    fun isSchedulable(entry: MedicationReminder): Boolean =
        entry.cycleType == MedicationCycleType.DAILY || entry.weekDays.isNotEmpty()

    fun cancel(context: Context, reminderId: Int) {
        val intent = Intent(context, MedicationAlarmReceiver::class.java)
        val pendingIntent = PendingIntent.getBroadcast(
            context,
            ALARM_REQUEST_BASE + reminderId,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val manager = context.getSystemService(AlarmManager::class.java) ?: return
        manager.cancel(pendingIntent)
    }

    fun rescheduleAll(context: Context) {
        MedicationStore.getEnabled(context).forEach { schedule(context, it) }
    }

    fun rescheduleAfterTrigger(context: Context, reminders: List<MedicationReminder>) {
        reminders.forEach { schedule(context, it) }
    }

    fun scheduleSnoozeOneHour(context: Context, reminders: List<MedicationReminder>): Boolean {
        if (reminders.isEmpty()) return false
        reminders.forEach { cancel(context, it.id) }
        val triggerAt = System.currentTimeMillis() + 60 * 60_000L
        val cal = Calendar.getInstance().apply { timeInMillis = triggerAt }
        val hour = cal.get(Calendar.HOUR_OF_DAY)
        val minute = cal.get(Calendar.MINUTE)
        val ids = reminders.map { it.id }.toIntArray()
        val intent = Intent(context, MedicationAlarmReceiver::class.java).apply {
            putExtra(MedicationAlarmReceiver.EXTRA_REMINDER_IDS, ids)
            putExtra(MedicationAlarmReceiver.EXTRA_HOUR, hour)
            putExtra(MedicationAlarmReceiver.EXTRA_MINUTE, minute)
            putExtra(MedicationAlarmReceiver.EXTRA_SNOOZE, true)
        }
        val requestCode = SNOOZE_REQUEST_BASE + ids.contentHashCode()
        val pendingIntent = PendingIntent.getBroadcast(
            context,
            requestCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return AlarmScheduler.setExactAlarm(context, triggerAt, pendingIntent)
    }

    fun nextTriggerMillis(entry: MedicationReminder): Long {
        val cal = Calendar.getInstance().apply {
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
            set(Calendar.HOUR_OF_DAY, entry.hour)
            set(Calendar.MINUTE, entry.minute)
        }
        if (cal.timeInMillis <= System.currentTimeMillis()) {
            cal.add(Calendar.DAY_OF_YEAR, 1)
        }
        if (entry.cycleType != MedicationCycleType.DAILY) {
            if (entry.weekDays.isEmpty()) return -1L
            var safety = 0
            while (!entry.shouldFireOn(cal.get(Calendar.DAY_OF_WEEK)) && safety < 14) {
                cal.add(Calendar.DAY_OF_YEAR, 1)
                safety++
            }
            if (!entry.shouldFireOn(cal.get(Calendar.DAY_OF_WEEK))) return -1L
        }
        return cal.timeInMillis
    }

    fun millisUntil(entry: MedicationReminder): Long =
        nextTriggerMillis(entry) - System.currentTimeMillis()
}