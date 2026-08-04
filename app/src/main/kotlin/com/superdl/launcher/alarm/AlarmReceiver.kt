package com.superdl.launcher.alarm

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build

/**
 * Az ébresztő időpontjában elindítja a valódi ébresztőhangot (AlarmService)
 * és a riasztási képernyőt (AlarmAlertActivity), majd gondoskodik a
 * következő alkalom beütemezéséről (ismétlődő ébresztőnél).
 */
class AlarmReceiver : BroadcastReceiver() {

    companion object {
        const val EXTRA_ALARM_ID = "alarm_id"
        const val EXTRA_LABEL = "label"
        const val EXTRA_HOUR = "hour"
        const val EXTRA_MINUTE = "minute"
        const val EXTRA_TONE_URI = "tone_uri"
        const val EXTRA_SNOOZE_ENABLED = "snooze_enabled"
        const val EXTRA_IS_SNOOZE = "is_snooze"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val appContext = context.applicationContext
        val alarmId = intent.getIntExtra(EXTRA_ALARM_ID, -1)
        val label = intent.getStringExtra(EXTRA_LABEL)?.takeIf { it.isNotBlank() } ?: "Ébresztő"
        val toneUri = intent.getStringExtra(EXTRA_TONE_URI)
        val snoozeEnabled = intent.getBooleanExtra(EXTRA_SNOOZE_ENABLED, true)
        val isSnooze = intent.getBooleanExtra(EXTRA_IS_SNOOZE, false)

        // 0) KIHAGYÁS: ha erre az ébresztőre van érvényben kihagyás, most NEM
        // szólalunk meg — csak "elhasználunk" egyet a számlálóból, és
        // beütemezzük a következő alkalmat. Így nem kell kézzel ki-, majd
        // visszakapcsolni az ébresztőt (pl. ha pénteken és hétfőn nem kell
        // dolgozni). A számláló magától elfogy, és utána újra megszólal.
        if (!isSnooze && alarmId >= 0) {
            val entry = AlarmStore.getAll(appContext).firstOrNull { it.id == alarmId }
            if (entry != null && entry.skipRemaining > 0) {
                val left = AlarmStore.consumeSkip(appContext, alarmId)
                android.util.Log.i(
                    "SDL_ALARM",
                    "Ebreszto KIHAGYVA (id=$alarmId), hatralevo kihagyas: $left"
                )
                AlarmScheduler.scheduleNextOccurrence(
                    appContext,
                    entry.copy(skipRemaining = left)
                )
                return
            }
        }

        // 1) Valódi, fokozódó ébresztőhang indítása (foreground service).
        val soundIntent = Intent(appContext, AlarmService::class.java).apply {
            putExtra(AlarmService.EXTRA_ALARM_ID, alarmId)
            putExtra(AlarmService.EXTRA_LABEL, label)
            putExtra(AlarmService.EXTRA_TONE_URI, toneUri)
        }
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                appContext.startForegroundService(soundIntent)
            } else {
                appContext.startService(soundIntent)
            }
        } catch (_: Exception) {
        }

        // 2) Riasztási képernyő (bemondja a nevet, szundi/leállítás gesztusok).
        val alertIntent = Intent(appContext, AlarmAlertActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            putExtra(AlarmAlertActivity.EXTRA_ALARM_ID, alarmId)
            putExtra(AlarmAlertActivity.EXTRA_LABEL, label)
            putExtra(AlarmAlertActivity.EXTRA_TONE_URI, toneUri)
            putExtra(AlarmAlertActivity.EXTRA_SNOOZE_ENABLED, snoozeEnabled)
        }
        try {
            appContext.startActivity(alertIntent)
        } catch (_: Exception) {
        }

        // 3) A következő alkalom beütemezése (szundi-riasztásnál nem kell).
        if (!isSnooze && alarmId >= 0) {
            AlarmStore.getAll(appContext).firstOrNull { it.id == alarmId }?.let { entry ->
                AlarmScheduler.scheduleNextOccurrence(appContext, entry)
            }
        }
    }
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            Intent.ACTION_BOOT_COMPLETED,
            Intent.ACTION_MY_PACKAGE_REPLACED -> {
                AlarmScheduler.rescheduleAll(context)
                com.superdl.launcher.medication.MedicationScheduler.rescheduleAll(context)
                com.superdl.launcher.calendar.CalendarReminderScheduler.rescheduleUpcoming(context)
                com.superdl.launcher.timer.TimerManager.resumeIfNeeded(context)
                com.superdl.launcher.battery.BatteryPatrolManager.start(context)
                com.superdl.launcher.feedback.DeviceStateSoundManager.start(context)
                com.superdl.launcher.contacts.ContactSyncScheduler.reschedule(context)
                com.superdl.launcher.contacts.ContactSyncHelper.syncIfNeeded(context)
            }
        }
    }
}
