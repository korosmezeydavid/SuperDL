package com.superdl.launcher.medication

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.PowerManager
import com.superdl.launcher.feedback.AlertLaunchHelper

class MedicationAlarmReceiver : BroadcastReceiver() {

    companion object {
        const val EXTRA_REMINDER_ID = "medication_reminder_id"
        const val EXTRA_REMINDER_IDS = "medication_reminder_ids"
        const val EXTRA_HOUR = "medication_hour"
        const val EXTRA_MINUTE = "medication_minute"
        const val EXTRA_SNOOZE = "medication_snooze"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val hour = intent.getIntExtra(EXTRA_HOUR, -1)
        val minute = intent.getIntExtra(EXTRA_MINUTE, -1)
        if (hour < 0 || minute < 0) return

        val pendingResult = goAsync()
        val appContext = context.applicationContext
        val wakeLock = acquireWakeLock(appContext)

        val due = loadDueReminders(appContext, intent)
        if (due.isEmpty()) {
            val reminderId = intent.getIntExtra(EXTRA_REMINDER_ID, -1)
            if (reminderId >= 0) {
                MedicationStore.getById(appContext, reminderId)?.let {
                    MedicationScheduler.schedule(appContext, it)
                }
            }
            releaseWakeLock(wakeLock)
            pendingResult.finish()
            return
        }

        if (!intent.getBooleanExtra(EXTRA_SNOOZE, false)) {
            due.forEach { MedicationScheduler.schedule(appContext, it) }
        }

        if (MedicationAlertService.isAlertActive(hour, minute)) {
            releaseWakeLock(wakeLock)
            pendingResult.finish()
            return
        }

        val ids = due.map { it.id }.toIntArray()

        AlertLaunchHelper.launchStaged(
            onAfterWakeBeep = {
                val serviceIntent = Intent(appContext, MedicationAlertService::class.java).apply {
                    putExtra(MedicationAlertService.EXTRA_HOUR, hour)
                    putExtra(MedicationAlertService.EXTRA_MINUTE, minute)
                    putExtra(MedicationAlertService.EXTRA_REMINDER_IDS, ids)
                }
                try {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        appContext.startForegroundService(serviceIntent)
                    } else {
                        appContext.startService(serviceIntent)
                    }
                } catch (_: Exception) {
                }
            },
            onShowAlertUi = {
                val launch = Intent(appContext, MedicationAlertActivity::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or
                        Intent.FLAG_ACTIVITY_CLEAR_TOP or
                        Intent.FLAG_ACTIVITY_SINGLE_TOP
                    putExtra(MedicationAlertActivity.EXTRA_HOUR, hour)
                    putExtra(MedicationAlertActivity.EXTRA_MINUTE, minute)
                    putExtra(MedicationAlertActivity.EXTRA_REMINDER_IDS, ids)
                }
                try {
                    appContext.startActivity(launch)
                } catch (_: Exception) {
                }
            },
            onComplete = {
                releaseWakeLock(wakeLock)
                pendingResult.finish()
            }
        )
    }

    private fun loadDueReminders(context: Context, intent: Intent): List<MedicationReminder> {
        val ids = intent.getIntArrayExtra(EXTRA_REMINDER_IDS)
        if (ids != null && ids.isNotEmpty()) {
            return ids.toList().mapNotNull { id -> MedicationStore.getById(context, id) }
                .filter { reminder -> reminder.enabled }
        }
        val hour = intent.getIntExtra(EXTRA_HOUR, -1)
        val minute = intent.getIntExtra(EXTRA_MINUTE, -1)
        if (hour < 0 || minute < 0) return emptyList()
        return MedicationStore.getDueAt(context, hour, minute)
    }

    private fun acquireWakeLock(context: Context): PowerManager.WakeLock? =
        try {
            val pm = context.getSystemService(Context.POWER_SERVICE) as PowerManager
            pm.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP,
                "SuperDL:MedicationAlarm"
            ).apply {
                setReferenceCounted(false)
                acquire(90_000L)
            }
        } catch (_: Exception) {
            null
        }

    private fun releaseWakeLock(wakeLock: PowerManager.WakeLock?) {
        try {
            if (wakeLock?.isHeld == true) wakeLock.release()
        } catch (_: Exception) {
        }
    }
}