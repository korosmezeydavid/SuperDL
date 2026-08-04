package com.superdl.launcher.hearingaid

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.superdl.launcher.R

class HearingAidService : Service() {

    private var engine: HearingAidEngine? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
        engine = HearingAidEngine(applicationContext)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopEngine()
                stopSelf()
                return START_NOT_STICKY
            }
            ACTION_UPDATE -> {
                val settings = HearingAidStore.load(this)
                engine?.updateSettings(settings)
                updateNotification(settings)
                return START_STICKY
            }
            else -> {
                val settings = HearingAidStore.load(this)
                startForeground(NOTIFICATION_ID, buildNotification(settings, running = false))
                val started = engine?.start(settings) == true
                if (!started) {
                    stopSelf()
                    return START_NOT_STICKY
                }
                updateNotification(settings)
                return START_STICKY
            }
        }
    }

    override fun onDestroy() {
        stopEngine()
        super.onDestroy()
    }

    private fun stopEngine() {
        engine?.stop()
        HearingAidStore.isRunning = false
    }

    private fun updateNotification(settings: HearingAidSettings) {
        val manager = getSystemService(NotificationManager::class.java) ?: return
        manager.notify(NOTIFICATION_ID, buildNotification(settings, running = true))
    }

    private fun buildNotification(settings: HearingAidSettings, running: Boolean): Notification {
        val status = if (running) "Fut – ${settings.balance.speakHu()}" else "Indítás…"
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle(getString(R.string.hearing_aid_notification_title))
            .setContentText(status)
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }

    private fun createChannel() {
        val manager = getSystemService(NotificationManager::class.java) ?: return
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.hearing_aid_notification_channel),
            NotificationManager.IMPORTANCE_LOW
        )
        manager.createNotificationChannel(channel)
    }

    companion object {
        private const val CHANNEL_ID = "HEARING_AID_CHANNEL"
        private const val NOTIFICATION_ID = 7400
        const val ACTION_STOP = "com.superdl.launcher.hearingaid.STOP"
        const val ACTION_UPDATE = "com.superdl.launcher.hearingaid.UPDATE"

        fun start(context: Context) {
            val intent = Intent(context, HearingAidService::class.java)
            context.startForegroundService(intent)
        }

        fun stop(context: Context) {
            val intent = Intent(context, HearingAidService::class.java).apply {
                action = ACTION_STOP
            }
            context.startService(intent)
        }

        fun updateSettings(context: Context) {
            if (!HearingAidStore.isRunning) return
            val intent = Intent(context, HearingAidService::class.java).apply {
                action = ACTION_UPDATE
            }
            context.startService(intent)
        }
    }
}