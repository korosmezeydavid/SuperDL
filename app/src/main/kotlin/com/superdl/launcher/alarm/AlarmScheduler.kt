package com.superdl.launcher.alarm

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import com.superdl.launcher.settings.PermissionGuideTexts
import com.superdl.launcher.settings.PermissionGuideType
import java.util.Calendar

object AlarmScheduler {

    fun canScheduleExact(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return true
        val manager = context.getSystemService(AlarmManager::class.java) ?: return false
        return manager.canScheduleExactAlarms()
    }

    fun exactAlarmGuideSpeech(): String =
        PermissionGuideTexts.sections(PermissionGuideType.EXACT_ALARM)
            .joinToString(" ") { it.body }

    fun schedule(context: Context, entry: AlarmEntry) {
        if (!entry.enabled) return
        val triggerAt = nextTriggerMillisForEntry(entry)
        val intent = Intent(context, AlarmReceiver::class.java).apply {
            putExtra(AlarmReceiver.EXTRA_ALARM_ID, entry.id)
            putExtra(AlarmReceiver.EXTRA_LABEL, entry.label)
            putExtra(AlarmReceiver.EXTRA_HOUR, entry.hour)
            putExtra(AlarmReceiver.EXTRA_MINUTE, entry.minute)
            putExtra(AlarmReceiver.EXTRA_TONE_URI, entry.toneUri)
            putExtra(AlarmReceiver.EXTRA_SNOOZE_ENABLED, entry.snoozeEnabled)
        }
        val pendingIntent = PendingIntent.getBroadcast(
            context,
            entry.id,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        setExactAlarm(context, triggerAt, pendingIntent)
    }

    /** A következő alkalom beütemezése egy megszólalás után (ismétlődő ébresztő). */
    fun scheduleNextOccurrence(context: Context, entry: AlarmEntry) {
        if (entry.isOneTime()) {
            // Egyszeri ébresztő: a megszólalás után kikapcsoljuk.
            AlarmStore.setEnabled(context, entry.id, false)
            return
        }
        schedule(context, entry)
    }

    /** Szundi: az adott ébresztőt 10 perc múlva újra megszólaltatja. */
    fun scheduleSnooze(
        context: Context,
        alarmId: Int,
        label: String,
        toneUri: String?,
        snoozeEnabled: Boolean
    ) {
        val triggerAt = System.currentTimeMillis() + SNOOZE_MINUTES * 60_000L
        val intent = Intent(context, AlarmReceiver::class.java).apply {
            putExtra(AlarmReceiver.EXTRA_ALARM_ID, alarmId)
            putExtra(AlarmReceiver.EXTRA_LABEL, label)
            putExtra(AlarmReceiver.EXTRA_TONE_URI, toneUri)
            putExtra(AlarmReceiver.EXTRA_SNOOZE_ENABLED, snoozeEnabled)
            putExtra(AlarmReceiver.EXTRA_IS_SNOOZE, true)
        }
        // Külön requestCode a szundinak, hogy ne ütközzön a fő ébresztővel.
        val pendingIntent = PendingIntent.getBroadcast(
            context,
            SNOOZE_REQUEST_BASE + alarmId,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        setExactAlarm(context, triggerAt, pendingIntent)
    }

    /** Az ébresztő leállításakor: egyszerinél kikapcsol; ismétlődőnél marad a következő. */
    fun onAlarmDismissed(context: Context, alarmId: Int) {
        val entry = AlarmStore.getAll(context).firstOrNull { it.id == alarmId } ?: return
        if (entry.isOneTime()) {
            AlarmStore.setEnabled(context, alarmId, false)
        }
    }

    fun setExactAlarm(context: Context, triggerAt: Long, pendingIntent: PendingIntent): Boolean {
        val manager = context.getSystemService(AlarmManager::class.java) ?: return false
        return try {
            if (canScheduleExact(context)) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    manager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pendingIntent)
                } else {
                    @Suppress("DEPRECATION")
                    manager.setExact(AlarmManager.RTC_WAKEUP, triggerAt, pendingIntent)
                }
                true
            } else {
                scheduleInexactAlarm(manager, triggerAt, pendingIntent)
                false
            }
        } catch (_: SecurityException) {
            try {
                scheduleInexactAlarm(manager, triggerAt, pendingIntent)
                false
            } catch (_: Exception) {
                false
            }
        }
    }

    private fun scheduleInexactAlarm(
        manager: AlarmManager,
        triggerAt: Long,
        pendingIntent: PendingIntent
    ) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pendingIntent)
        } else {
            @Suppress("DEPRECATION")
            manager.set(AlarmManager.RTC_WAKEUP, triggerAt, pendingIntent)
        }
    }

    fun cancel(context: Context, alarmId: Int) {
        val intent = Intent(context, AlarmReceiver::class.java)
        val pendingIntent = PendingIntent.getBroadcast(
            context,
            alarmId,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val manager = context.getSystemService(AlarmManager::class.java) ?: return
        manager.cancel(pendingIntent)
    }

    fun rescheduleAll(context: Context) {
        AlarmStore.getEnabled(context).forEach { schedule(context, it) }
    }

    fun nextTriggerMillis(hour: Int, minute: Int): Long {
        val cal = Calendar.getInstance().apply {
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
            set(Calendar.HOUR_OF_DAY, hour)
            set(Calendar.MINUTE, minute)
            if (timeInMillis <= System.currentTimeMillis()) {
                add(Calendar.DAY_OF_YEAR, 1)
            }
        }
        return cal.timeInMillis
    }

    /**
     * A következő megszólalás időpontja az ismétlés figyelembevételével:
     * megkeresi a legközelebbi napot, amelyen az ébresztő aktív.
     */
    fun nextTriggerMillisForEntry(entry: AlarmEntry): Long {
        val cal = Calendar.getInstance().apply {
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
            set(Calendar.HOUR_OF_DAY, entry.hour)
            set(Calendar.MINUTE, entry.minute)
            if (timeInMillis <= System.currentTimeMillis()) {
                add(Calendar.DAY_OF_YEAR, 1)
            }
        }
        // Legfeljebb egy hetet előre keresünk egy aktív napot.
        var guard = 0
        while (guard < 8 && !entry.isActiveOnDay(cal.get(Calendar.DAY_OF_WEEK))) {
            cal.add(Calendar.DAY_OF_YEAR, 1)
            guard++
        }
        return cal.timeInMillis
    }

    fun millisUntil(entry: AlarmEntry): Long =
        nextTriggerMillisForEntry(entry) - System.currentTimeMillis()

    private const val SNOOZE_MINUTES = 10
    private const val SNOOZE_REQUEST_BASE = 90000
}