package com.superdl.launcher.calendar

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.core.app.NotificationCompat
import com.superdl.launcher.feedback.AlertSoundCategory
import com.superdl.launcher.feedback.AlertSoundPlayer

class CalendarAlarmService : Service() {

    companion object {
        const val CHANNEL_ID = "CALENDAR_ALARM_CHANNEL"
        const val NOTIFICATION_ID = 7101
        const val EXTRA_TITLE = "calendar_alarm_title"
        private const val AUTO_STOP_MS = 10 * 60_000L

        fun stop(context: Context) {
            context.stopService(Intent(context, CalendarAlarmService::class.java))
        }
    }

    private val handler = Handler(Looper.getMainLooper())
    private var stopAlarmSound: (() -> Unit)? = null
    private val autoStopRunnable = Runnable { stopSelf() }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val title = intent?.getStringExtra(EXTRA_TITLE)?.takeIf { it.isNotBlank() } ?: "Program"
        val eventId = intent?.getLongExtra(CalendarAlarmReceiver.EXTRA_EVENT_ID, -1L) ?: -1L
        val beginMs = intent?.getLongExtra(CalendarAlarmReceiver.EXTRA_BEGIN_MS, 0L) ?: 0L
        val endMs = intent?.getLongExtra(CalendarAlarmReceiver.EXTRA_END_MS, 0L) ?: 0L
        startForeground(NOTIFICATION_ID, buildNotification(title, eventId, beginMs, endMs))
        startContinuousAlarm()
        startVibration()
        handler.postDelayed(autoStopRunnable, AUTO_STOP_MS)
        return START_STICKY
    }

    override fun onDestroy() {
        handler.removeCallbacks(autoStopRunnable)
        stopContinuousAlarm()
        stopVibration()
        super.onDestroy()
    }

    private fun startContinuousAlarm() {
        stopContinuousAlarm()
        stopAlarmSound = AlertSoundPlayer.startLooping(this, AlertSoundCategory.CALENDAR)
    }

    private fun stopContinuousAlarm() {
        stopAlarmSound?.invoke()
        stopAlarmSound = null
    }

    private var vibrator: Vibrator? = null

    private fun startVibration() {
        val pattern = longArrayOf(0, 700, 300, 700, 300)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vm = getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager
                vibrator = vm.defaultVibrator
                vibrator?.vibrate(VibrationEffect.createWaveform(pattern, -1))
            } else {
                @Suppress("DEPRECATION")
                val v = getSystemService(VIBRATOR_SERVICE) as Vibrator
                vibrator = v
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    v.vibrate(VibrationEffect.createWaveform(pattern, -1))
                } else {
                    @Suppress("DEPRECATION")
                    v.vibrate(pattern, -1)
                }
            }
        } catch (_: Exception) {
        }
    }

    private fun stopVibration() {
        try {
            vibrator?.cancel()
        } catch (_: Exception) {
        }
        vibrator = null
    }

    private fun buildNotification(
        title: String,
        eventId: Long,
        beginMs: Long,
        endMs: Long
    ): Notification {
        val fullScreenIntent = Intent(this, CalendarAlertActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra(CalendarAlarmReceiver.EXTRA_EVENT_ID, eventId)
            putExtra(CalendarAlarmReceiver.EXTRA_TITLE, title)
            putExtra(CalendarAlarmReceiver.EXTRA_BEGIN_MS, beginMs)
            putExtra(CalendarAlarmReceiver.EXTRA_END_MS, endMs)
        }
        val fullScreenPendingIntent = PendingIntent.getActivity(
            this,
            (eventId xor beginMs).toInt(),
            fullScreenIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Naptár program")
            .setContentText("$title – program ideje!")
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
            "Naptár program emlékeztető",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "Naptár program indulási idejének jelzése"
            setBypassDnd(true)
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }
}