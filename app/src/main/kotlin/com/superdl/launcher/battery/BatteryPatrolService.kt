package com.superdl.launcher.battery

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
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat
import com.superdl.launcher.info.InfoHelper
import com.superdl.launcher.patrol.PatrolAnnouncer
import com.superdl.launcher.patrol.PatrolStore
import com.superdl.launcher.security.LockSession
import java.util.Calendar

class BatteryPatrolService : Service() {

    companion object {
        private const val CHANNEL_ID = "BATTERY_PATROL_CHANNEL"
        private const val NOTIFICATION_ID = 7200
    }

    private val handler = Handler(Looper.getMainLooper())
    private var batteryReceiver: BroadcastReceiver? = null
    private var screenReceiver: BroadcastReceiver? = null
    private var lastScreenOnAnnounceAt = 0L
    private var lastIntervalAnnounceKey = ""

    private val timeCheckRunnable = object : Runnable {
        override fun run() {
            maybeAnnounceIntervalTime()
            handler.postDelayed(this, 20_000L)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildPatrolNotification())
        registerBatteryReceiver()
        registerScreenReceiver()
        handler.post(timeCheckRunnable)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!PatrolStore.isMasterEnabled(this)) {
            stopSelf()
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    override fun onDestroy() {
        handler.removeCallbacks(timeCheckRunnable)
        batteryReceiver?.let { unregisterReceiver(it) }
        screenReceiver?.let { unregisterReceiver(it) }
        batteryReceiver = null
        screenReceiver = null
        super.onDestroy()
    }

    private fun registerBatteryReceiver() {
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                if (intent.action != Intent.ACTION_BATTERY_CHANGED) return
                val level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
                val scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, 100)
                if (level < 0 || scale <= 0) return
                val percent = (level * 100f / scale).toInt().coerceIn(0, 100)
                val status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
                val charging = status == BatteryManager.BATTERY_STATUS_CHARGING ||
                    status == BatteryManager.BATTERY_STATUS_FULL
                handleBatteryLevel(percent, charging)
            }
        }
        batteryReceiver = receiver
        val filter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(receiver, filter)
        }
        @Suppress("DEPRECATION")
        val sticky = registerReceiver(null, filter)
        if (sticky != null) {
            receiver.onReceive(this, sticky)
        }
    }

    private fun registerScreenReceiver() {
        val filter = IntentFilter(Intent.ACTION_SCREEN_ON)
        screenReceiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                if (intent.action != Intent.ACTION_SCREEN_ON) return
                if (LockSession.needsUnlock(context)) return
                if (!PatrolStore.isMasterEnabled(context)) return
                if (!PatrolStore.isPowerButtonTimeEnabled(context)) return
                if (PatrolStore.isQuietNow(context)) return
                val now = System.currentTimeMillis()
                if (now - lastScreenOnAnnounceAt < 1800L) return
                lastScreenOnAnnounceAt = now
                // Feloldáskor a képernyő-bekapcsolás hangja már szól (DeviceStateTonePlayer),
                // ezért itt beep nélkül, csak az idő – nincs dupla pittyegés.
                PatrolAnnouncer.announce(
                    context,
                    InfoHelper.speakDateTime(),
                    withBeep = false
                )
            }
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(screenReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(screenReceiver, filter)
        }
    }

    private fun handleBatteryLevel(level: Int, isCharging: Boolean) {
        if (!PatrolStore.isMasterEnabled(this)) return
        if (!PatrolStore.isBatteryEnabled(this)) return
        if (PatrolStore.isQuietNow(this)) return

        if (BatteryPatrolLogic.shouldReset(level, isCharging)) {
            PatrolStore.resetAlertState(this)
            return
        }

        val lastAlerted = PatrolStore.getLastAlertedThreshold(this)
        val threshold = BatteryPatrolLogic.thresholdToAlert(level, lastAlerted) ?: return

        PatrolStore.setLastAlertedThreshold(this, threshold)
        BatteryAlertHelper.alert(this, level, threshold)
    }

    private fun maybeAnnounceIntervalTime() {
        if (!PatrolStore.isMasterEnabled(this)) return
        if (!PatrolStore.isTimeAnnounceEnabled(this)) return
        if (PatrolStore.isQuietNow(this)) return

        val interval = PatrolStore.getTimeIntervalMinutes(this)
        val now = Calendar.getInstance()
        val minute = now.get(Calendar.MINUTE)
        val second = now.get(Calendar.SECOND)
        if (minute % interval != 0 || second > 25) return

        val key = "${now.get(Calendar.DAY_OF_YEAR)}-${now.get(Calendar.HOUR_OF_DAY)}-$minute"
        if (key == lastIntervalAnnounceKey) return
        lastIntervalAnnounceKey = key
        // Óránkénti/periodikus időbemondás: egyetlen rövid, lágy csendülés + idő.
        PatrolAnnouncer.announce(
            this,
            InfoHelper.speakDateTime(),
            withBeep = false,
            softChime = true
        )
    }

    private fun buildPatrolNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Teljes őrség")
            .setContentText("Akkumulátor, idő, értesítés és képernyő figyelés aktív.")
            .setSmallIcon(android.R.drawable.ic_lock_idle_low_battery)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Teljes őrség",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Háttérben futó akkumulátor, idő és értesítés figyelés"
            setShowBadge(false)
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }
}