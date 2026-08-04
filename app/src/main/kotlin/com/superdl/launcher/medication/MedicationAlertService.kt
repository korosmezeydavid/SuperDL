package com.superdl.launcher.medication

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.superdl.launcher.feedback.AlertSoundCategory
import com.superdl.launcher.feedback.AlertSoundPlayer

class MedicationAlertService : Service() {

    companion object {
        const val CHANNEL_ID = "MEDICATION_ALERT_CHANNEL"
        const val NOTIFICATION_ID = 7203
        const val EXTRA_HOUR = "medication_alert_hour"
        const val EXTRA_MINUTE = "medication_alert_minute"
        const val EXTRA_REMINDER_IDS = "medication_alert_reminder_ids"

        @Volatile
        private var activeHour: Int = -1

        @Volatile
        private var activeMinute: Int = -1

        fun isAlertActive(hour: Int, minute: Int): Boolean =
            activeHour == hour && activeMinute == minute

        fun markActive(hour: Int, minute: Int) {
            activeHour = hour
            activeMinute = minute
        }

        fun clearActive() {
            activeHour = -1
            activeMinute = -1
        }

        fun stop(context: Context) {
            clearActive()
            context.stopService(Intent(context, MedicationAlertService::class.java))
        }
    }

    private var stopAlarmSound: (() -> Unit)? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val hour = intent?.getIntExtra(EXTRA_HOUR, -1) ?: -1
        val minute = intent?.getIntExtra(EXTRA_MINUTE, -1) ?: -1
        val ids = intent?.getIntArrayExtra(EXTRA_REMINDER_IDS)
        val due = loadDueReminders(hour, minute, ids)
        val title = due.joinToString(", ") { it.name }.ifBlank { "Patika Őrangyal" }
        markActive(hour, minute)
        startForeground(NOTIFICATION_ID, buildNotification(title, hour, minute, ids))
        startDistinctChime()
        return START_STICKY
    }

    override fun onDestroy() {
        clearActive()
        stopDistinctChime()
        super.onDestroy()
    }

    private fun loadDueReminders(hour: Int, minute: Int, ids: IntArray?): List<MedicationReminder> {
        if (ids != null && ids.isNotEmpty()) {
            return ids.toList().mapNotNull { id -> MedicationStore.getById(this, id) }
                .filter { reminder -> reminder.enabled }
        }
        if (hour < 0 || minute < 0) return emptyList()
        return MedicationStore.getDueAt(this, hour, minute)
    }

    private fun startDistinctChime() {
        stopDistinctChime()
        stopAlarmSound = AlertSoundPlayer.startLooping(this, AlertSoundCategory.MEDICATION)
    }

    private fun stopDistinctChime() {
        stopAlarmSound?.invoke()
        stopAlarmSound = null
    }

    private fun buildNotification(
        title: String,
        hour: Int,
        minute: Int,
        ids: IntArray?
    ): Notification {
        val fullScreenIntent = Intent(this, MedicationAlertActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra(MedicationAlertActivity.EXTRA_HOUR, hour)
            putExtra(MedicationAlertActivity.EXTRA_MINUTE, minute)
            if (ids != null) putExtra(MedicationAlertActivity.EXTRA_REMINDER_IDS, ids)
        }
        val requestCode = (hour * 100 + minute) xor (ids?.contentHashCode() ?: 0)
        val fullScreenPendingIntent = PendingIntent.getActivity(
            this,
            requestCode,
            fullScreenIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Patika Őrangyal")
            .setContentText("$title – gyógyszer ideje!")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setOngoing(true)
            .setContentIntent(fullScreenPendingIntent)
            .setFullScreenIntent(fullScreenPendingIntent, true)
            .build()
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Patika Őrangyal emlékeztető",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "Gyógyszer bevételi emlékeztető hangjelzése"
            setBypassDnd(true)
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }
}