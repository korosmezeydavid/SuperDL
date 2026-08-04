package com.superdl.launcher.sos

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.superdl.launcher.R
import com.superdl.launcher.call.CallHelper
import kotlinx.coroutines.*

class SosService : Service() {

    companion object {
        const val CHANNEL_ID = "SOS_CHANNEL"
        const val EXTRA_NUMBERS = "sos_numbers"
        private const val CALL_TIMEOUT_MS = 20_000L  // 20 másodperc számonként
    }

    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(1, buildNotification())
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val numbers = intent?.getStringArrayListExtra(EXTRA_NUMBERS) ?: return START_NOT_STICKY

        scope.launch {
            callSequentially(numbers)
            stopSelf()
        }

        return START_NOT_STICKY
    }

    private suspend fun callSequentially(numbers: List<String>) {
        for (number in numbers) {
            if (number.isBlank()) continue
            Log.d("SOS", "Hívás: $number")
            CallHelper.launchInCall(this, number, "S.O.S.")
            delay(CALL_TIMEOUT_MS)
        }
    }

    private fun buildNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Super DL S.O.S.")
            .setContentText("Vészjelzés folyamatban...")
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .build()
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID, "S.O.S. Vészjelzés",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "S.O.S. vészhívás értesítések"
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }
}
