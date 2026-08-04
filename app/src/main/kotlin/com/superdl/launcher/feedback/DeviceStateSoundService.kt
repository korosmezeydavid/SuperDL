package com.superdl.launcher.feedback

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat

class DeviceStateSoundService : Service() {

    companion object {
        private const val CHANNEL_ID = "DEVICE_STATE_SOUND_CHANNEL"
        private const val NOTIFICATION_ID = 7300
    }

    private var screenReceiver: BroadcastReceiver? = null
    private var batteryReceiver: BroadcastReceiver? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        registerReceivers()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!DeviceStateStore.isEnabled(this)) {
            stopSelf()
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    override fun onDestroy() {
        screenReceiver?.let { unregisterReceiver(it) }
        batteryReceiver?.let { unregisterReceiver(it) }
        screenReceiver = null
        batteryReceiver = null
        super.onDestroy()
    }

    private fun registerReceivers() {
        val screenFilter = IntentFilter().apply {
            addAction(Intent.ACTION_SCREEN_ON)
            addAction(Intent.ACTION_SCREEN_OFF)
        }
        screenReceiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                if (!DeviceStateStore.isEnabled(context)) return
                when (intent.action) {
                    Intent.ACTION_SCREEN_ON -> DeviceStateTonePlayer.play(DeviceStateEvent.SCREEN_ON, context)
                    Intent.ACTION_SCREEN_OFF -> DeviceStateTonePlayer.play(DeviceStateEvent.SCREEN_OFF, context)
                }
            }
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(screenReceiver, screenFilter, RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(screenReceiver, screenFilter)
        }

        val batteryFilter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        batteryReceiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                if (!DeviceStateStore.isEnabled(context)) return
                val status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
                val plugged = intent.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0)
                if (status == BatteryManager.BATTERY_STATUS_FULL && plugged != 0) {
                    if (!DeviceStateStore.isFullAnnounced(context)) {
                        DeviceStateStore.setFullAnnounced(context, true)
                        DeviceStateTonePlayer.play(DeviceStateEvent.BATTERY_FULL, context)
                    }
                } else if (plugged == 0) {
                    DeviceStateStore.setFullAnnounced(context, false)
                }
            }
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(batteryReceiver, batteryFilter, RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(batteryReceiver, batteryFilter)
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Rendszerállapot hangok",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Töltő, akkumulátor és képernyő hangos jelzései"
                setShowBadge(false)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_silent_mode_off)
            .setContentTitle("Super DL – rendszerállapot hangok")
            .setContentText("Töltő, teljes töltés és képernyő jelzések aktívak")
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .build()
}