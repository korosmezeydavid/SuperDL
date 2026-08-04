package com.superdl.launcher.dictaphone

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat

class DictaphoneService : Service() {

    companion object {
        private const val CHANNEL_ID = "DICTAPHONE_CHANNEL"
        private const val NOTIFICATION_ID = 7500
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!DictaphoneStore.isRecording) {
            stopSelf()
            return START_NOT_STICKY
        }
        val notification = buildNotification()
        startForeground(NOTIFICATION_ID, notification)
        return START_STICKY
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Profi Diktafon",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Hangfelvétel folyamatban"
            setShowBadge(false)
        }
        getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
    }

    private fun buildNotification(): Notification {
        val paused = DictaphoneStore.isPaused
        val elapsed = DictaphoneSpeech.speakElapsed(DictaphoneStore.elapsedMillis(), paused)
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Profi Diktafon")
            .setContentText(if (paused) "Szünetel" else "Felvétel")
            .setSubText(elapsed)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }
}